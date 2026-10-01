import base64
import json
import logging
import mimetypes
import os
import smtplib
import ssl
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)
_ALERT_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix='weapon-alert')


def _email_is_configured():
    return bool(os.getenv('SMTP_HOST') and os.getenv('ALERT_EMAIL_TO') and (os.getenv('SMTP_FROM') or os.getenv('SMTP_USERNAME')))


def _twilio_is_configured():
    return all(os.getenv(name) for name in (
        'TWILIO_ACCOUNT_SID',
        'TWILIO_AUTH_TOKEN',
        'TWILIO_FROM_NUMBER',
        'ALERT_SMS_TO',
    ))


def _telegram_is_configured():
    return bool(os.getenv('TELEGRAM_BOT_TOKEN') and os.getenv('TELEGRAM_CHAT_ID'))


def _send_email(message):
    host = os.environ['SMTP_HOST']
    username = os.getenv('SMTP_USERNAME', '')
    password = os.getenv('SMTP_PASSWORD', '')
    use_ssl = os.getenv('SMTP_USE_SSL', 'false').lower() == 'true'
    default_port = '465' if use_ssl else '587'
    port = int(os.getenv('SMTP_PORT', default_port))

    if bool(username) != bool(password):
        raise ValueError('SMTP_USERNAME and SMTP_PASSWORD must both be set')

    email = EmailMessage()
    email['Subject'] = 'Weapon detection alert'
    email['From'] = os.getenv('SMTP_FROM') or username
    email['To'] = os.environ['ALERT_EMAIL_TO']
    email.set_content(message)

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=10, context=ssl.create_default_context()) as server:
            if username:
                server.login(username, password)
            server.send_message(email)
    else:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls(context=ssl.create_default_context())
            if username:
                server.login(username, password)
            server.send_message(email)
    logger.info('Email weapon alert sent')


def _send_twilio_sms(message):
    account_sid = os.environ['TWILIO_ACCOUNT_SID']
    auth_token = os.environ['TWILIO_AUTH_TOKEN']
    endpoint = f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json'
    authorization = base64.b64encode(f'{account_sid}:{auth_token}'.encode()).decode()
    request = Request(
        endpoint,
        data=urlencode({
            'From': os.environ['TWILIO_FROM_NUMBER'],
            'To': os.environ['ALERT_SMS_TO'],
            'Body': message,
        }).encode(),
        headers={'Authorization': f'Basic {authorization}'},
        method='POST',
    )
    with urlopen(request, timeout=10) as response:
        response.read()
    logger.info('Twilio SMS weapon alert sent')


def _send_telegram(message, photo_path=None):
    token = os.environ['TELEGRAM_BOT_TOKEN']
    if photo_path:
        endpoint = f'https://api.telegram.org/bot{token}/sendPhoto'
        boundary = f'----WeaponDetection{uuid.uuid4().hex}'
        body = bytearray()

        def add_field(name, value):
            body.extend(f'--{boundary}\r\n'.encode())
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            body.extend(str(value).encode())
            body.extend(b'\r\n')

        add_field('chat_id', os.environ['TELEGRAM_CHAT_ID'])
        add_field('caption', message)
        image_path = Path(photo_path)
        content_type = mimetypes.guess_type(image_path.name)[0] or 'application/octet-stream'
        body.extend(f'--{boundary}\r\n'.encode())
        body.extend(
            f'Content-Disposition: form-data; name="photo"; filename="{image_path.name}"\r\n'.encode()
        )
        body.extend(f'Content-Type: {content_type}\r\n\r\n'.encode())
        body.extend(image_path.read_bytes())
        body.extend(f'\r\n--{boundary}--\r\n'.encode())
        request = Request(
            endpoint,
            data=bytes(body),
            headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
            method='POST',
        )
    else:
        endpoint = f'https://api.telegram.org/bot{token}/sendMessage'
        request = Request(
            endpoint,
            data=json.dumps({
                'chat_id': os.environ['TELEGRAM_CHAT_ID'],
                'text': message,
            }).encode(),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
    with urlopen(request, timeout=10) as response:
        telegram_result = json.loads(response.read().decode('utf-8'))
    if not telegram_result.get('ok'):
        raise RuntimeError('Telegram rejected the alert')
    logger.info('Telegram weapon alert sent')


def _deliver_alert(channel, sender, *args):
    try:
        sender(*args)
    except Exception as error:
        logger.error('%s weapon alert failed (%s)', channel, type(error).__name__)


def dispatch_weapon_alert(source, weapon_count, confidence, priority='ALERT', photo_path=None, timestamp=None, face_names=None):
    detected_at = timestamp or datetime.now()
    if hasattr(detected_at, 'strftime'):
        detected_at = detected_at.strftime('%Y-%m-%d %H:%M:%S')

    cleaned_faces = []
    if face_names:
        seen = set()
        for name in face_names:
            normalized = str(name).strip()
            if not normalized:
                continue
            if normalized.lower() not in seen:
                seen.add(normalized.lower())
                cleaned_faces.append(normalized)

    face_message = ''
    if cleaned_faces:
        face_message = f'\nKnown faces: {", ".join(cleaned_faces)}'

    message = (
        f'{priority} weapon alert.\n'
        f'Source: {source}\n'
        f'Count: {weapon_count}\n'
        f'Time: {detected_at}\n'
        f'Highest confidence: {confidence:.1f}%{face_message}'
    )
    channels = (
        ('email', _email_is_configured(), _send_email),
        ('sms', _twilio_is_configured(), _send_twilio_sms),
        ('telegram', _telegram_is_configured(), _send_telegram),
    )
    queued_channels = []

    for name, is_configured, sender in channels:
        if is_configured:
            sender_args = (message, photo_path) if name == 'telegram' else (message,)
            _ALERT_EXECUTOR.submit(_deliver_alert, name, sender, *sender_args)
            queued_channels.append(name)

    if not queued_channels:
        logger.info('No external weapon alert channels are configured')
    return queued_channels