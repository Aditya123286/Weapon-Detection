import os
from pathlib import Path
import cv2
import logging
import threading
from functools import lru_cache

from huggingface_hub import hf_hub_download
from ultralytics import YOLO

from face_recognition_module import recognize_face

logger = logging.getLogger(__name__)

MODEL_REPO = 'akhil0238/Weapon_Detection'
MODEL_REVISION = '2c91b7182be3ee090ee641a678187b8523729f41'
MODEL_FILENAME = 'weights/best.pt'
DETECTION_CONFIDENCE = float(os.environ.get('DETECTION_CONFIDENCE', '0.65'))
INFERENCE_LOCK = threading.Lock()
KNOWN_FACES_DIR = Path(__file__).resolve().parent / 'known_faces'


@lru_cache(maxsize=1)
def get_detection_model():
    model_path = hf_hub_download(
        repo_id=MODEL_REPO,
        filename=MODEL_FILENAME,
        revision=MODEL_REVISION,
    )
    return YOLO(model_path)


def detect_weapons(image_source):
    """Detect weapons in an image path or an OpenCV BGR frame."""
    if isinstance(image_source, (str, os.PathLike)):
        image = cv2.imread(os.fspath(image_source))
    else:
        image = image_source

    if image is None:
        raise ValueError("Could not read image for weapon detection")

    output_image = image.copy()
    weapon_detections = []
    confidence_scores = []

    with INFERENCE_LOCK:
        prediction = get_detection_model().predict(
            image,
            conf=DETECTION_CONFIDENCE,
            verbose=False,
        )[0]

    for xyxy, score, class_id in zip(
        prediction.boxes.xyxy.tolist(),
        prediction.boxes.conf.tolist(),
        prediction.boxes.cls.tolist(),
    ):
        x1, y1, x2, y2 = (int(value) for value in xyxy)
        class_name = str(prediction.names[int(class_id)]).title()
        confidence = float(score) * 100
        weapon_detections.append({
            'class': class_name,
            'confidence': confidence,
            'bbox': [x1, y1, x2, y2],
        })
        confidence_scores.append(confidence)
        cv2.rectangle(output_image, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(
            output_image,
            f'{class_name}: {confidence:.0f}%',
            (x1, max(y1 - 8, 18)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2,
        )

    face_matches = []
    if weapon_detections:
        try:
            face_matches = recognize_face(image, str(KNOWN_FACES_DIR))
        except Exception:
            logger.exception("Face recognition failed; continuing with weapon detection")
        for match in face_matches:
            x1, y1, x2, y2 = match.get('bbox', [0, 0, 0, 0])
            if x2 <= x1 or y2 <= y1:
                continue
            cv2.rectangle(output_image, (x1, y1), (x2, y2), (0, 0, 255), 2)
            label = f"{match.get('name', 'Unknown')} ({match.get('confidence', 0.0):.0f}%)"
            cv2.putText(
                output_image,
                label,
                (x1, max(y1 - 8, 18)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255),
                2,
            )

    logger.info("Weapon detection complete: %s found; %s face matches", len(weapon_detections), len(face_matches))
    return weapon_detections, confidence_scores, output_image, face_matches
