import os
import time
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
import uuid
import cv2
import numpy as np
import json
import math
from pathlib import Path
from sqlalchemy import inspect, text
from alerts import dispatch_weapon_alert
from video_evidence import collect_camera_frame, has_pending_clip, save_evidence_video

# Import db from database.py instead of creating it here
from database import db
from evaluate import run_evaluation

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "development_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///weapon_detection.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Configure upload settings
UPLOAD_FOLDER = 'static/uploads'
RESULTS_FOLDER = 'static/results'
VIDEO_FOLDER = os.path.join(RESULTS_FOLDER, 'videos')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULTS_FOLDER'] = RESULTS_FOLDER
app.config['VIDEO_FOLDER'] = VIDEO_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Initialize the app with the extension
db.init_app(app)

# Create upload and results directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Import models AFTER db is initialized
from models import Detection

# Create tab~les
with app.app_context():
    db.create_all()
    detection_columns = {
        column['name'] for column in inspect(db.engine).get_columns(Detection.__tablename__)
    }
    pending_columns = {
        'source': "source VARCHAR(20) NOT NULL DEFAULT 'upload'",
        'weapon_classes': "weapon_classes TEXT NOT NULL DEFAULT '[]'",
        'face_matches': "face_matches TEXT NOT NULL DEFAULT '[]'",
        'red_zone_count': 'red_zone_count INTEGER NOT NULL DEFAULT 0',
        'green_zone_count': 'green_zone_count INTEGER NOT NULL DEFAULT 0',
        'video_filename': 'video_filename VARCHAR(255)',
    }
    for column_name, column_definition in pending_columns.items():
        if column_name not in detection_columns:
            with db.engine.begin() as connection:
                connection.execute(text(
                    f'ALTER TABLE {Detection.__tablename__} ADD COLUMN {column_definition}'
                ))

# Import other components
from detection import detect_weapons
from utils import save_detection_image

def weapon_zone(class_name):
    normalized_name = ''.join(character for character in str(class_name).lower() if character.isalnum())
    dangerous_types = ('gun', 'pistol', 'firearm', 'rifle', 'bomb', 'explosion', 'explosive', 'grenade')
    return 'red' if any(kind in normalized_name for kind in dangerous_types) else 'green'


@app.route('/')
def index():
    if 'camera_buffer_id' not in session:
        session['camera_buffer_id'] = uuid.uuid4().hex
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    # Check if the post request has the file part
    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(request.url)
    
    file = request.files['file']
    
    # If user does not select file, browser also submits an empty part without filename
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        try:
            # Create unique filename to prevent overwriting
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            
            # Run weapon detection
            detections, confidence_scores, output_image, face_matches = detect_weapons(filepath)
            
            # Save result image
            result_filename = f"result_{unique_filename}"
            result_path = os.path.join(app.config['RESULTS_FOLDER'], result_filename)
            save_detection_image(output_image, result_path)
            
            # Create detection record
            detection_count = len(detections)
            has_weapons = detection_count > 0
            for detection in detections:
                detection['zone'] = weapon_zone(detection['class'])
            red_zone_count = sum(detection['zone'] == 'red' for detection in detections)
            green_zone_count = detection_count - red_zone_count
            alert_level = 'HIGH' if red_zone_count else 'LOW' if green_zone_count else None

            # Get highest confidence if weapons detected
            highest_confidence = max(confidence_scores) if confidence_scores else 0
            face_names = [
                match.get('name', 'Unknown') for match in face_matches
                if match.get('name') and match.get('name') != 'Unknown'
            ]
            
            # Save to database
            new_detection = Detection(
                original_filename=filename,
                stored_filename=unique_filename,
                result_filename=result_filename,
                timestamp=datetime.now(),
                weapon_detected=has_weapons,
                weapon_count=detection_count,
                confidence=highest_confidence,
                source='upload',
                weapon_classes=json.dumps([detection['class'] for detection in detections]),
                face_matches=json.dumps(face_matches),
                red_zone_count=red_zone_count,
                green_zone_count=green_zone_count
            )
            db.session.add(new_detection)
            db.session.commit()

            if has_weapons:
                dispatch_weapon_alert(
                    'image upload',
                    detection_count,
                    highest_confidence,
                    priority='RED ZONE' if alert_level == 'HIGH' else 'LOW ZONE',
                    photo_path=result_path,
                    timestamp=new_detection.timestamp,
                    face_names=face_names,
                )
            
            # Save detection ID in session for immediate access
            session['last_detection_id'] = new_detection.id
            
            # Flash success message
            if has_weapons:
                flash(f'Detection complete: {detection_count} gun(s) detected', 'danger')
            else:
                flash('No guns detected in the image', 'success')
                
            return redirect(url_for('index'))
            
        except Exception as e:
            logger.error(f"Error during detection: {str(e)}")
            flash(f'Error processing image: {str(e)}', 'danger')
            return redirect(url_for('index'))
    else:
        flash('File type not allowed. Please upload JPG, JPEG, or PNG files only.', 'warning')
        return redirect(url_for('index'))

@app.route('/detect-frame', methods=['POST'])
def detect_frame():
    frame_file = request.files.get('frame')
    if not frame_file:
        return jsonify({'error': 'Camera frame is missing'}), 400

    frame_bytes = frame_file.read()
    frame = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return jsonify({'error': 'Could not read camera frame'}), 400
    start_time = time.time() 

    try:
        detections, confidence_scores, output_frame, face_matches = detect_weapons(frame)
    except Exception:
        logger.exception("Live camera frame detection failed")
        return jsonify({'error': 'Could not analyze camera frame'}), 500
    inference_time_ms = (time.time() - start_time) * 1000 

    red_zone_detected = False
    green_zone_detected = False
    for detection in detections:
        detection['zone'] = weapon_zone(detection['class'])
        red_zone_detected = red_zone_detected or detection['zone'] == 'red'
        green_zone_detected = green_zone_detected or detection['zone'] == 'green'

    alert_level = 'HIGH' if red_zone_detected else 'LOW' if green_zone_detected else None
    zone_state = 'RED' if red_zone_detected else 'LOW' if green_zone_detected else 'CLEAR'
    red_zone_count = sum(detection['zone'] == 'red' for detection in detections)
    green_zone_count = sum(detection['zone'] == 'green' for detection in detections)

    camera_scan_id = request.form.get('scan_id') or session.get('camera_scan_id') or uuid.uuid4().hex
    is_new_scan = camera_scan_id != session.get('camera_scan_id')
    previously_detected = session.get('camera_weapon_detected', False) if not is_new_scan else False
    previous_alert_level = session.get('camera_alert_level') if not is_new_scan else None
    record_event = bool(detections) and (
        not previously_detected
        or (alert_level is not None and alert_level != previous_alert_level)
    )

    history_record = None
    if detections and record_event:
        stored_filename = f"live_{uuid.uuid4().hex}.jpg"
        result_filename = f"result_{stored_filename}"
        stored_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_filename)
        result_path = os.path.join(app.config['RESULTS_FOLDER'], result_filename)

        if not save_detection_image(frame, stored_path) or not save_detection_image(output_frame, result_path):
            for image_path in (stored_path, result_path):
                if os.path.exists(image_path):
                    os.remove(image_path)
            return jsonify({'error': 'Could not save detected camera frame'}), 500

        face_names = [
            match.get('name', 'Unknown') for match in face_matches
            if match.get('name') and match.get('name') != 'Unknown'
        ]
        history_record = Detection(
            original_filename='Live camera frame',
            stored_filename=stored_filename,
            result_filename=result_filename,
            timestamp=datetime.now(),
            weapon_detected=True,
            weapon_count=len(detections),
            confidence=max(confidence_scores) if confidence_scores else 0,
            source='live',
            weapon_classes=json.dumps([detection['class'] for detection in detections]),
            face_matches=json.dumps(face_matches),
            red_zone_count=red_zone_count,
            green_zone_count=green_zone_count
        )
        try:
            db.session.add(history_record)
            db.session.commit()
            session['last_detection_id'] = history_record.id
        except Exception:
            db.session.rollback()
            for image_path in (stored_path, result_path):
                if os.path.exists(image_path):
                    os.remove(image_path)
            logger.exception("Could not save live detection to history")
            return jsonify({'error': 'Could not save detection to history'}), 500

        alert_channels = dispatch_weapon_alert(
            'live camera',
            len(detections),
            max(confidence_scores) if confidence_scores else 0,
            priority='RED ZONE' if alert_level == 'HIGH' else 'LOW ZONE',
            photo_path=result_path,
            timestamp=history_record.timestamp,
            face_names=face_names,
        )
    else:
        alert_channels = []

    session['camera_scan_id'] = camera_scan_id
    session['camera_weapon_detected'] = bool(detections)
    session['camera_alert_level'] = alert_level

    camera_id = session.get('camera_buffer_id')
    if not camera_id:
        camera_id = uuid.uuid4().hex
        session['camera_buffer_id'] = camera_id
    completed_clips = collect_camera_frame(
        camera_id,
        frame,
        event_id=history_record.id if history_record else None,
    )
    completed_event_ids = []
    video_error = False
    for clip in completed_clips:
        try:
            video_name = save_evidence_video(clip, app.config['VIDEO_FOLDER'])
            video_record = db.session.get(Detection, clip['event_id'])
            if video_record:
                video_record.video_filename = f'videos/{video_name}'
                db.session.commit()
                completed_event_ids.append(video_record.id)
        except Exception:
            db.session.rollback()
            video_error = True
            logger.exception("Could not save evidence video for detection %s", clip['event_id'])

    return jsonify({
        'weapon_detected': bool(detections),
        'weapon_count': len(detections),
        'boxes': detections,
        'face_matches': face_matches,
        'zone_state': zone_state,
        'history_saved': history_record is not None,
        'history_id': history_record.id if history_record else None,
        'alerts_queued': bool(alert_channels),
        'alert_level': alert_level,
        'evidence_pending': has_pending_clip(camera_id),
        'evidence_saved': bool(completed_event_ids),
        'evidence_error': video_error,
        'frame_width': int(frame.shape[1]),
        'frame_height': int(frame.shape[0]),
        'inference_time_ms': round(inference_time_ms, 2),
    })

@app.route('/history')
def history():
    detections = Detection.query.order_by(Detection.timestamp.desc()).all()
    return render_template('history.html', detections=detections)

def remove_detection_file(directory, filename):
    if not filename:
        return

    storage_root = Path(directory).resolve()
    file_path = (storage_root / filename).resolve()
    try:
        file_path.relative_to(storage_root)
    except ValueError:
        logger.warning("Refusing to delete a file outside detection storage: %s", filename)
        return

    if file_path.is_file():
        file_path.unlink()

@app.route('/history/<int:detection_id>/delete', methods=['POST'])
def delete_detection(detection_id):
    detection = db.session.get(Detection, detection_id)
    if detection is None:
        flash('Detection record was not found.', 'warning')
        return redirect(url_for('history'))

    stored_filename = detection.stored_filename
    result_filename = detection.result_filename
    video_filename = detection.video_filename
    db.session.delete(detection)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Could not delete detection record %s", detection_id)
        flash('Could not delete the detection record.', 'danger')
        return redirect(url_for('history'))

    if session.get('last_detection_id') == detection_id:
        session.pop('last_detection_id', None)

    cleanup_failed = False
    for directory, filename in (
        (app.config['UPLOAD_FOLDER'], stored_filename),
        (app.config['RESULTS_FOLDER'], result_filename),
        (app.config['RESULTS_FOLDER'], video_filename),
    ):
        try:
            remove_detection_file(directory, filename)
        except OSError:
            cleanup_failed = True
            logger.exception("Could not remove file for detection %s", detection_id)

    if cleanup_failed:
        flash('Detection deleted, but one or more evidence files could not be removed.', 'warning')
    else:
        flash('Detection and its evidence files deleted.', 'success')
    return redirect(url_for('history'))

@app.route('/analytics')
def analytics():
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    first_day = today_start - timedelta(days=29)

    rows = db.session.query(
        Detection.timestamp,
        Detection.weapon_count,
        Detection.weapon_classes,
        Detection.red_zone_count,
        Detection.green_zone_count,
    ).filter(
        Detection.weapon_detected.is_(True),
        Detection.timestamp >= first_day,
        Detection.timestamp <= now,
    ).all()

    def total_since(start):
        return sum(row.weapon_count for row in rows if row.timestamp >= start)

    daily_dates = [first_day + timedelta(days=offset) for offset in range(30)]
    daily_totals = [
        sum(row.weapon_count for row in rows if row.timestamp.date() == day.date())
        for day in daily_dates
    ]
    hourly_totals = [
        sum(row.weapon_count for row in rows if row.timestamp.hour == hour)
        for hour in range(24)
    ]

    gun_count = 0
    knife_count = 0
    other_count = 0
    unclassified_count = 0
    red_count = sum(row.red_zone_count for row in rows)
    green_count = sum(row.green_zone_count for row in rows)
    for row in rows:
        try:
            classes = json.loads(row.weapon_classes or '[]')
        except (TypeError, json.JSONDecodeError):
            classes = []
        for weapon_class in classes:
            normalized_class = str(weapon_class).strip().lower()
            if normalized_class == 'gun':
                gun_count += 1
            elif normalized_class == 'knife':
                knife_count += 1
            else:
                other_count += 1
        unclassified_count += max(0, row.weapon_count - len(classes))

    return render_template(
        'analytics.html',
        today_total=total_since(today_start),
        week_total=total_since(week_start),
        month_total=total_since(month_start),
        daily_labels=[day.strftime('%d %b') for day in daily_dates],
        daily_values=daily_totals,
        class_values=[gun_count, knife_count, other_count, unclassified_count],
        zone_values=[red_count, green_count, max(0, total_since(first_day) - red_count - green_count)],
        hour_labels=[f'{hour:02d}:00' for hour in range(24)],
        hour_values=hourly_totals,
        window_label=f'{first_day:%d %b} - {today_start:%d %b %Y}',
    )

@app.route('/evaluation', methods=['GET', 'POST'])
def evaluation():
    if request.method == 'POST':
        try:
            payload = run_evaluation()
            return jsonify({'status': 'success', 'message': 'Evaluation complete.', 'results': payload}), 200
        except Exception as exc:
            logger.exception('Model evaluation failed')
            return jsonify({'status': 'error', 'message': str(exc)}), 500

    results = {}
    results_file = Path(__file__).resolve().parent / 'evaluation_results.json'
    if results_file.exists():
        try:
            with open(results_file, 'r', encoding='utf-8') as handle:
                results = json.load(handle)
        except json.JSONDecodeError:
            results = {}

    confusion_matrix = None
    static_confusion = Path(__file__).resolve().parent / 'static' / 'evaluation' / 'confusion_matrix.png'
    if static_confusion.exists():
        confusion_matrix = url_for('static', filename='evaluation/confusion_matrix.png')

    return render_template(
        'evaluation.html',
        results=results,
        confusion_matrix=confusion_matrix,
    )

@app.route('/latest')
def latest_detection():
    detection_id = session.get('last_detection_id')
    if detection_id:
        detection = Detection.query.get(detection_id)
        if detection:
            return jsonify({
                'id': detection.id,
                'original_filename': detection.original_filename,
                'stored_filename': detection.stored_filename,
                'result_filename': detection.result_filename,
                'timestamp': detection.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'weapon_detected': detection.weapon_detected,
                'weapon_count': detection.weapon_count,
                'confidence': detection.confidence,
                'source': detection.source,
                'video_filename': detection.video_filename
            })
    return jsonify({}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)