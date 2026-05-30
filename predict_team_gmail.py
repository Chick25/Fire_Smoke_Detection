import os
# Ép OpenCV sử dụng giao thức TCP cho RTSP để tránh timeout mạng
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

import cv2
import time
import base64
from email.mime.text import MIMEText
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
# Thay thế bằng danh sách Gmail thật của các thành viên trong nhóm bạn
TEAM_GMAILS = [
    "lytieuhan547@gmail.com",
    "minhnguyetdang2304@gmail.com",
    "nvt21092005@gmail.com",
    "oituanday444@gmail.com",
    "vutruclam1202@gmail.com"
]

def get_gmail_service():
    """Hàm tự động xác thực OAuth2 và trả về dịch vụ kết nối Gmail API"""
    creds = None
    # File token.json tự sinh ra sau lần đăng nhập đầu tiên để duy trì phiên làm việc
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

def send_gmail_alert_to_team(service, time_str):
    """Hàm gửi email cảnh báo hỏa hoạn đồng loạt tới danh sách team"""
    if service is None:
        print("❌ Chưa cấu hình dịch vụ Gmail API thành công.")
        return

    # Gộp danh sách email thành chuỗi cách nhau bởi dấu phẩy để gửi cùng lúc (CC)
    to_recipients = ", ".join(TEAM_GMAILS)
    
    # NỘI DUNG EMAIL (Hỗ trợ định dạng HTML để in đậm, in đỏ rõ ràng)
    email_content = f"""
    <html>
      <body>
        <h2 style="color: red;">🚨 [CẢNH BÁO HỎA HOẠN KHẨN CẤP - SOS TEAM ALERT]</h2>
        <p>Xin chào các thành viên trong đội dự án,</p>
        <p>Hệ thống camera giám sát AI thông minh vừa phát hiện dấu hiệu nguy hiểm có <b>LỬA / KHÓI</b> tại khu vực quản lý.</p>
        <ul>
          <li><b>⏱ Thời gian ghi nhận:</b> {time_str}</li>
          <li><b>⚠️ Trạng thái hệ thống:</b> Kích hoạt báo động khẩn cấp cấp độ 1</li>
        </ul>
        <p><i>Vui lòng truy cập hệ thống và kiểm tra ngay luồng camera mạng RTSP để xác minh!</i></p>
        <br>
        <p>--<br>Hệ thống giám sát Fire Detection AI Bot</p>
      </body>
    </html>
    """
    
    message = MIMEText(email_content, 'html', 'utf-8')
    message['to'] = to_recipients
    message['subject'] = '🚨 [SOS] CẢNH BÁO PHÁT HIỆN HỎA HOẠN QUA CAMERA GIÁM SÁT'
    
    # Mã hóa email sang dạng base64 theo chuẩn quy định của Gmail API
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    create_message = {'raw': raw_message}
    
    try:
        service.users().messages().send(userId="me", body=create_message).execute()
        print(f"📧 Đã bắn Email cảnh báo khẩn cấp thành công tới {len(TEAM_GMAILS)} thành viên!")
    except Exception as e:
        print(f"❌ Gặp lỗi khi gọi Gmail API gửi thư: {e}")

# =========================================================================
# 2. KHỞI TẠO AI VÀ LUỒNG CAMERA RTSP
# =========================================================================
# Khởi tạo dịch vụ Gmail trước khi vào luồng camera
print("🔐 Đang xác thực dịch vụ Google API...")
gmail_service = get_gmail_service()

model = YOLO("fire_smoke_model/best.pt")
# RTSP_URL = "rtsp://admin:L28DF769@192.168.1.119:554/cam/realmonitor?channel=1&subtype=0"
VIDEO_PATH = "vid2.mp4"
cap = cv2.VideoCapture(VIDEO_PATH)
# cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
if cap.isOpened():
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

fire_frame_counter = 0
FRAME_THRESHOLD = 45  
last_alert_time = 0
ALERT_COOLDOWN = 90   # Giãn cách 90 giây giữa các lần gửi mail để tránh spam hòm thư của team

if not cap.isOpened():
    print(f"❌ Không thể kết nối tới luồng RTSP của Camera.")
    exit()

print("🌐 Hệ thống AI bắt đầu giám sát và sẵn sàng gửi Email cảnh báo...")

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        time.sleep(2)
        continue

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

    # KÍCH HOẠT GỬI EMAIL KHI ĐẠT NGƯỠNG NGUY HIỂM
    if fire_frame_counter >= FRAME_THRESHOLD:
        current_time = time.time()
        cv2.putText(annotated_frame, "!!! EMERGENCY: FIRE DETECTED !!!", (20, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)
        
        if current_time - last_alert_time > ALERT_COOLDOWN:
            string_now = time.strftime('%H:%M:%S - %d/%m/%Y')
            
            # Thực hiện hàm gửi Mail đồng loạt
            send_gmail_alert_to_team(gmail_service, string_now)
            
            last_alert_time = current_time

    cv2.putText(annotated_frame, f"Risk Level: {fire_frame_counter}/{FRAME_THRESHOLD}", (20, 90), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    # Thu nhỏ màn hình hiển thị camera mạng về 640x480 để chạy mượt mà
    resized_frame = cv2.resize(annotated_frame, (640, 480))
    cv2.imshow("RTSP Team Monitor - Gmail API Integrated", resized_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()