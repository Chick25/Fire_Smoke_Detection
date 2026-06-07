# 🔥 Fire & Smoke Detection System

A real-time fire and smoke monitoring system leveraging computer vision (YOLOv8) to provide early warnings and risk analysis. The system features a modern web dashboard and multi-channel alerting capabilities.

## 🚀 Features

*   **Real-time Detection:** High-speed object detection for fire and smoke using YOLOv8.
*   **FSI (Fire Severity Index):** Advanced risk calculation based on:
    *   Fire/Smoke surface area.
    *   Color intensity (HSV analysis).
    *   Spread rate calculation.
*   **Live Dashboard:** Real-time video streaming over WebSockets (Socket.IO).
*   **Multi-Channel Alerts:**
    *   **Messenger:** Automated alerts to group chats.
    *   **Gmail:** Email alerts with incident snapshots attached via Google API.
    *   **SMS Simulation:** Automated SMS notifications through webhooks.
*   **RTSP Support:** Connects directly to IP Cameras or processes local video files.
*   **False Alarm Prevention:** Risk accumulation logic requiring consistent detection across multiple frames before triggering alerts.

## 🛠️ Technology Stack

### Backend
- **Language:** Python 3.10+
- **Framework:** Flask & Flask-SocketIO
- **AI Model:** YOLOv8 (Ultralytics)
- **Vision:** OpenCV

### Frontend
- **Framework:** React 19 (TypeScript)
- **Styling:** Tailwind CSS
- **Real-time:** Socket.IO Client

## 📦 Installation

### 1. Prerequisites
- Python installed (3.10 or higher recommended)
- Node.js and npm installed

### 2. Backend Setup
Navigate to the root directory and install Python dependencies:
```bash
pip install -r requirements.txt
```
*Note: Ensure you have your trained YOLO model at `fire_smoke_model/best_final.pt`.*

### 3. Frontend Setup
Navigate to the `frontend` folder and install dependencies:
```bash
cd frontend
npm install
```

## 📦 Test Media (Sample Videos for Testing)

Due to GitHub's file size limits, the `.mp4` video files used for fire detection testing cannot be uploaded directly to the source code.

1. Access this Google Drive link to download the test videos: [https://drive.google.com/drive/folders/1Ahss7h3gB7LgQrbUMtYr5wMY430kz-fk]
2. Download the video files and place them in the `media/` folder within the project’s root directory.
3. Configure the video path in the `main.py` file to point to the downloaded files to run the system.

## 🚦 Usage

### 1. Start the Backend
Run the Flask server from the root:
```bash
python backend/main.py
```
The server will start on `http://localhost:5000`.

### 2. Start the Frontend
In a new terminal, navigate to the `frontend` folder and start the dev server:
```bash
cd frontend
npm start
```
The dashboard will be available at `http://localhost:3000`.

## ⚙️ Configuration

- **Camera Source:** Change the `current_video_source` in `backend/main.py` to your RTSP link or a local file path.
- **Emergency Contacts:** Update `EMERGENCY_PHONES` in `backend/main.py`.
- **API Keys:** Configure Google OAuth2 for Gmail alerts in the `src/services` directory.

## 📊 System Logic

The system uses a **Risk Accumulation Buffer** (default 15 frames) to prevent false positives. Once the threshold is met, it triggers a `CRITICAL` alert session. Alerting channels are only re-enabled once the system confirms the area is safe (Risk Level returns to 0).

---
Developed as part of the AI project for residential safety monitoring.
