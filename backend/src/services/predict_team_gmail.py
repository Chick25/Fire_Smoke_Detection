import os
# Ép OpenCV sử dụng giao thức TCP cho RTSP để tránh timeout mạng
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

import cv2
import time
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from playsound import playsound
from ultralytics import YOLO

# Các thư viện xác thực của Google API
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Quyền truy cập: Chỉ xin quyền gửi email (gọn nhẹ và bảo mật)
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# =========================================================================
# 1. CẤU HÌNH DANH SÁCH EMAIL CỦA TEAM
# =========================================================================
TEAM_GMAILS = [
    "lytieuhan547@gmail.com",
    "minhnguyetdang2304@gmail.com",
    "nvt21092005@gmail.com",
    "oituanday444@gmail.com",
    "vutruclam1202@gmail.com",
    "huynhlekimyenn@gmail.com"
]

def get_gmail_service():
    """Hàm tự động xác thực OAuth2 và trả về dịch vụ kết nối Gmail API"""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("❌ Lỗi: Không tìm thấy file 'credentials.json' trong thư mục dự án!")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    return build('gmail', 'v1', credentials=creds)

def send_gmail_alert_to_team(service, time_str, image_path):
    if service is None:
        print("❌ Gmail API chưa sẵn sàng")
        return

    to_recipients = ", ".join(TEAM_GMAILS)
    message = MIMEMultipart()
    message["to"] = to_recipients
    message["subject"] = "🚨 [SOS] CẢNH BÁO HỎA HOẠN"

    html = f"""
    <html>
    <body>
        <h2 style='color:red'>🚨 PHÁT HIỆN LỬA / KHÓI</h2>
        <p><b>Thời gian:</b> {time_str}</p>
        <p>Hệ thống AI đã phát hiện dấu hiệu hỏa hoạn. Ảnh hiện trường được đính kèm bên dưới.</p>
        <p>Vui lòng kiểm tra ngay.</p>
    </body>
    </html>
    """
    message.attach(MIMEText(html, "html", "utf-8"))

    try:
        with open(image_path, "rb") as f:
            img = MIMEImage(f.read())
            img.add_header(
                "Content-Disposition",
                "attachment",
                filename=os.path.basename(image_path)
            )
            message.attach(img)
    except Exception as e:
        print("❌ Không đính kèm được ảnh:", e)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    try:
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        print("📧 Đã gửi email kèm ảnh hiện trường")
    except Exception as e:
        print("❌ Lỗi gửi mail:", e)

# =========================================================================
# 2. KHỞI TẠO AI VÀ LUỒNG CAMERA RTSP
# =========================================================================
if __name__ == '__main__':
    print("🔐 Đang xác thực dịch vụ Google API...")
    gmail_service = get_gmail_service()

    model = YOLO("fire_smoke_model/best.pt")
    VIDEO_PATH = r"vid2.mp4"
    cap = cv2.VideoCapture(VIDEO_PATH)

    if cap.isOpened():
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    fire_frame_counter = 0
    FRAME_THRESHOLD = 5 
    last_alert_time = 0
    ALERT_COOLDOWN = 10   # Giãn cách 90 giây giữa các lần gửi mail để tránh spam

    if not cap.isOpened():
        print(f"❌ Không thể kết nối tới nguồn video/camera.")
        exit()

    print("🌐 Hệ thống AI bắt đầu giám sát và sẵn sàng gửi Email cảnh báo...")

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            # Nếu là video file, hết video thì thoát vòng lặp
            break

        results = model(frame, conf=0.45, verbose=False)
        annotated_frame = results[0].plot()
        
        is_danger_detected = False
        for box in results[0].boxes:
            label = model.names[int(box.cls[0])]
            if label in ['fire', 'smoke']:
                is_danger_detected = True
                break
                
        if is_danger_detected:
            fire_frame_counter += 1
        else:
            fire_frame_counter = max(0, fire_frame_counter - 1)

        # KÍCH HOẠT XỬ LÝ KHI ĐẠT NGƯỠNG NGUY HIỂM
        if fire_frame_counter >= FRAME_THRESHOLD:
            current_time = time.time()
            cv2.putText(annotated_frame, "!!! EMERGENCY: FIRE DETECTED !!!", (20, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)
            
            # KIỂM TRA THỜI GIAN COOLDOWN TRƯỚC KHI GỬI EMAIL VÀ BÁO ĐỘNG
            if current_time - last_alert_time > ALERT_COOLDOWN:
                string_now = time.strftime('%H:%M:%S - %d/%m/%Y')
                image_name = f"fire_{int(current_time)}.jpg"

                # Lưu ảnh hiện trường sạch (hoặc dùng annotated_frame nếu muốn giữ box AI)
                cv2.imwrite(image_name, frame)

                try:
                    playsound(r"mixkit-facility-alarm-sound-999.wav")
                except Exception as e:
                    print("⚠ Không phát được âm thanh alarm.mp3:", e)

                send_gmail_alert_to_team(gmail_service, string_now, image_name)
                last_alert_time = current_time

        # Hiển thị mức độ nguy hiểm hiện tại lên màn hình
        cv2.putText(annotated_frame, f"Risk Level: {fire_frame_counter}/{FRAME_THRESHOLD}", (20, 90), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # Thu nhỏ màn hình hiển thị camera về 640x480 để mượt hơn
        resized_frame = cv2.resize(annotated_frame, (640, 480))
        cv2.imshow("RTSP Team Monitor - Gmail API Integrated", resized_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()