from database import db
from datetime import datetime

class Detection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    result_filename = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    weapon_detected = db.Column(db.Boolean, default=False)
    weapon_count = db.Column(db.Integer, default=0)
    confidence = db.Column(db.Float, default=0.0)
    source = db.Column(db.String(20), nullable=False, default='upload', server_default='upload')
    weapon_classes = db.Column(db.Text, nullable=False, default='[]', server_default='[]')
    face_matches = db.Column(db.Text, nullable=False, default='[]', server_default='[]')
    red_zone_count = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    green_zone_count = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    video_filename = db.Column(db.String(255), nullable=True)
    
    def __repr__(self):
        return f'<Detection {self.id} - Weapons: {self.weapon_count}>'