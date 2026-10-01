# Weapon Detection System #
A **real-time AI-powered weapon detection system** designed to enhance security and safety in various environments through live camera feeds and image analysis.
The application provides a unified system for detecting **weapons (guns, knives, explosives, grenades)**, with **automatic zone classification, Telegram alerts, face recognition, video evidence, and comprehensive analytics**.

## Project Overview
Weapon Detection System combines **Artificial Intelligence, Computer Vision, and Full-Stack Web Development** to provide a smart and efficient security monitoring platform.
The main objective of this project is to reduce manual surveillance, organize detection data, improve threat response time, simplify security monitoring, and provide an easy-to-use interface for security personnel, administrators, and law enforcement.

## Key Features

### AI-Powered Detection
- Real-time weapon detection using YOLOv5
- Multi-class detection: Gun, Knife, Explosion, Grenade
- Image upload detection
- Confidence scores for each detection
- Bounding boxes with class labels

### Auto Zone Classification
- **RED ZONE** (High Alert): Gun, Explosion, Grenade
- **GREEN ZONE** (Low Alert): Knife
- **CLEAR ZONE**: No weapon detected
- Visual indicator lights on camera view
- Auto-color-coded detection boxes

### Telegram Alerts
- Real-time notifications with annotated images
- Zone-based priority (RED ZONE / LOW ZONE)
- Weapon count + confidence + timestamp
- Face recognition results (if known face detected)

### Face Detection & Recognition
- Face detection using OpenCV YuNet
- Face recognition using OpenCV SFace
- Known persons database (`known_faces/` folder)
- Name displayed on detection + Telegram alert

### Detection History
- Complete record of all detections
- Original + annotated images
- Video evidence (10-second clips)
- Source tracking (Live Camera / Upload)
- Delete individual records

### Video Evidence
- Auto-recording 5 seconds before + 5 seconds after detection
- 10-second evidence clips
- Playable in browser
- Download option

### Analytics Dashboard
- Total detections (daily, weekly, monthly)
- Weapon type distribution (pie chart)
- Zone-wise detection counts
- Hourly detection trends
- 30-day detection timeline

### Performance Metrics
- Real-time FPS counter
- Inference time (ms/frame)
- Model evaluation (Precision, Recall, F1-Score)
- Confusion Matrix visualization
- mAP@0.5 and mAP@0.5:0.95

### User Management
- Secure authentication
- Session management
- HTTPS support (for mobile camera access)

## Technology Stack

### Frontend
- HTML5
- CSS3
- JavaScript
- Bootstrap 5
- Chart.js

### Backend
- Python 3.10+
- Flask
- REST APIs
- SQLAlchemy ORM

### AI & Computer Vision
- YOLOv5 (Ultralytics)
- OpenCV (YuNet + SFace)
- NumPy

### Database
- SQLite
- SQLAlchemy ORM

### Tools
- Git
- GitHub
- VS Code
- PowerShell

## System Architecture
Weapon Detection UI
(HTML / CSS / JavaScript / Bootstrap)
              │
              ▼
       Flask Backend
    (REST APIs, Business Logic)
              │
              ▼
    ┌─────────┴─────────┐
    │                   │
    ▼                   ▼
YOLOv5 Model      Face Recognition
(Detection)       (OpenCV SFace)
    │                   │
    └─────────┬─────────┘
              │
              ▼
       SQLite Database
     (SQLAlchemy ORM)
              │
              ▼
      Telegram Alerts
```


## Project Structure
Weapon-Detection-System/
├── app.py                          # Main Flask application
├── detection.py                    # Weapon detection logic
├── face_recognition_module.py      # Face recognition logic
├── alerts.py                       # Telegram/Email/SMS alerts
├── models.py                       # Database models
├── database.py                     # Database initialization
├── video_evidence.py               # Video recording logic
├── utils.py                        # Utility functions
├── evaluate.py                     # Model evaluation script
├── convert_dataset.py              # Dataset conversion script
├── main.py                         # Entry point
├── best.pt                         # Trained YOLOv5 model
├── evaluation_results.json         # Evaluation metrics
├── .env                            # Environment variables
├── .gitignore                      # Git ignore file
├── pyproject.toml                  # Python project config
├── ALERTS.md                       # Alert setup guide
├── README.md                       # This file
│
├── dataset_yolo/                   # YOLO format dataset
│   ├── data.yaml
│   ├── images/
│   └── labels/
│
├── known_faces/                    # Known persons photos
│
├── static/
│   ├── css/styles.css
│   ├── js/detection.js
│   ├── uploads/
│   ├── results/
│   │   └── videos/
│   └── evaluation/
│
├── templates/
│   ├── layout.html
│   ├── index.html
│   ├── history.html
│   ├── analytics.html
│   └── evaluation.html
│
└── evaluation_runs/


## Installation
1. Clone the Repository
```bash
git clone https://github.com/YOUR-GITHUB-USERNAME/YOUR-REPOSITORY.git

2. Open the Project Folder
cd Weapon-Detection-System

3. Create a Virtual Environment
python -m venv .venv

4. Activate the Virtual Environment
.venv\Scripts\activate

5. Install Required Packages
pip install -r requirements.txt
Ya manually:
   pip install flask opencv-python opencv-contrib-python ultralytics
   pip install numpy sqlalchemy python-dotenv requests huggingface_hub


Known Faces Setup
known_faces/ folder me known persons ki photos daalo:
known_faces/
├── Aditya_Prasad.jpg


Usage
Live Camera Detection
Home page kholo
"Start Scan" button dabao
Camera permission allow karo
Weapon dikhao camera ke saamne
Auto detection hoga:
  Red/Green/Clear indicator jalega
  Telegram alert jayega
  History me save hoga

Image Upload Detection
Home page par jao
"Select image for analysis" section me jao
Image choose karo (JPG/PNG, max 16MB)
"Upload & Analyze" dabao
Result dikhega with bounding boxes

View History
Navigation bar me "History" dabao
Saare detections dikhenge

Analytics Dashboard
Navigation bar me "Analytics" dabao
Charts dikhenge

Model Evaluation
Navigation bar me "Evaluation" dabao
"Run Evaluation" button dabao
Metrics dikhenge

Model Details
Detection Model
Architecture: YOLOv5 (Ultralytics)
Classes: 5 (Gun, knife, explosion, grenade, background)
Input Size: 640x640
Confidence Threshold: 0.65
Model File: best.pt (auto-downloaded)

Face Detection Model
Detector: OpenCV YuNet
Recognizer: OpenCV SFace
Embedding Size: 128-D
Match Threshold: 0.6

Performance Metrics
Real-time Performance
Metric	Value
Inference Time	~84-240 ms/frame (CPU)
Practical FPS	0.8-2.2 FPS
Face Detection	+20 ms/frame

Model Evaluation
Metric	Value
Test Images	472
Precision	35.7%
Recall	1.8%
F1-Score	3.5%
mAP@0.5	0.3%

Publisher Metrics (YOLOv5)
Metric	Value
Precision	81.5%
Recall	83.0%
F1-Score	82.2%
mAP@0.5	81.1%

Project Objectives
The major objectives of this project are:
Detect weapons in real-time from live camera
Classify weapons into danger zones automatically
Send instant alerts via Telegra
Recognize known persons using face recognition
Maintain detection history with video evidence
Provide analytics dashboard for monitoring
Evaluate model performance with metrics
Reduce manual surveillance efforts
Improve threat response time
Centralize security-related information

Learning Outcomes
Working on this project helped me gain practical experience in:
Python Programmin
Flask Framework
REST API Development
Computer Vision (OpenCV)
YOLOv5 Object Detectio
Face Detection & Recognition
SQLite Database & SQLAlchemy ORM
Database Design
CRUD Operation
Frontend Development (HTML/CSS/JS)
Backend Development
AI Integration
Git & GitHub
Software Architecture
Debugging and Problem Solving

Future Improvements
Future versions of this project may include:
Advanced weapon type classification (Pistol vs Rifle vs Shotgun)
Blade classification (Knife vs Sword vs Machete)
Cloud deployment (AWS/GCP/Azure)
Mobile application (React Native / Flutter)
Multi-camera support
Email/SMS alerts
PDF report generator
Edge deployment (Raspberry Pi / Jetson Nano)
Custom model training
Privacy mode (face blurring)

Developer
Aditya Prasad
Python Developer | Full-Stack Developer | AI Enthusiast

Technologies:
Python • Flask • YOLOv5 • OpenCV • SQLite • SQLAlchemy • JavaScript • HTML • CSS • Bootstrap • Chart.js • Git • GitHub • AI

Course: BTech CSE (AIML)
Semester: 6th / 3rd Year
University: Jaipur National University
RID: R41516
Project Guide: Gaurav Sir

Contributing
If you find this project useful or interesting, feel free to fork the repository.

License
This project is developed for educational, learning, and portfolio purposes.

Made with ❤️ by Aditya Prasad

