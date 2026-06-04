import os
# Ép OpenCV sử dụng giao thức TCP cho RTSP để tránh hiện tượng timeout/mất gói dữ liệu mạng
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

import cv2
import time
from ultralytics import YOLO

# 1. Tải mô hình YOLOv8 custom của bạn
model = YOLO("fire_smoke_model/best.pt")

# 2. Chuỗi RTSP kết nối trực tiếp đến camera Dahua/Imou thực tế của bạn
#RTSP_URL = "rtsp://admin:L28DF769@192.168.1.119:554/cam/realmonitor?channel=1&subtype=0"

# Cấu hình mở rộng CAP_FFMPEG và giảm tối đa kích thước buffer của luồng stream mạng để triệt tiêu delay
cap = cv2.VideoCapture(0)
if cap.isOpened():
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

# Cấu hình bộ đệm logic chống nhiễu / chống báo động giả
fire_frame_counter = 0
FRAME_THRESHOLD = 45  # Camera phải thấy lửa/khói liên tục ~2 giây mới kích hoạt chuông
last_alert_time = 0
ALERT_COOLDOWN = 30   # Cách 30 giây mới in cảnh báo tiếp

if not cap.isOpened():
    print(f"❌ Không thể kết nối tới luồng RTSP của Camera. Hãy kiểm tra lại IP/Tài khoản.")
    exit()

print("🌐 Đang kết nối và giám sát trực tiếp qua Camera RTSP khu dân cư...")

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        print("⚠️ Mất tín hiệu kết nối tạm thời từ Camera RTSP... Đang thử lại.")
        time.sleep(2) # Đợi 2 giây rồi tiếp tục thử đọc lại luồng
        continue

    # Xử lý dự đoán (Sử dụng verbose=False để terminal không bị tràn log liên tục)
    results = model(frame, conf=0.45, verbose=False)
    annotated_frame = results[0].plot()
    
    is_danger_detected = False
    for box in results[0].boxes:
        label = model.names[int(box.cls[0])]
        if label in ['fire', 'smoke']:
            is_danger_detected = True
            break
            
    # Logic bộ đệm thời gian nguy cơ (Buffer Risk Level)
    if is_danger_detected:
        fire_frame_counter += 1
    else:
        fire_frame_counter = max(0, fire_frame_counter - 1)

    if fire_frame_counter >= FRAME_THRESHOLD:
        current_time = time.time()
        cv2.putText(annotated_frame, "!!! EMERGENCY: FIRE DETECTED !!!", (20, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)
        
        if current_time - last_alert_time > ALERT_COOLDOWN:
            print(f"🚨 [CẢNH BÁO KHẨN CẤP] Phát hiện hỏa hoạn qua camera giám sát hành lang/ngõ phố lúc: {time.strftime('%H:%M:%S')}")
            last_alert_time = current_time

    cv2.putText(annotated_frame, f"Risk Level: {fire_frame_counter}/{FRAME_THRESHOLD}", (20, 90), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    # -------------------------------------------------------------------------
    # CHỈNH KÍCH THƯỚC MÀN HÌNH TẠI ĐÂY
    # Ép khung hình đầu ra thu nhỏ về độ phân giải 640x480 pixel trước khi hiển thị
    resized_frame = cv2.resize(annotated_frame, (640, 480))
    
    # Thay vì truyền annotated_frame gốc, ta truyền resized_frame đã thu nhỏ
    cv2.imshow("RTSP Live Monitor - Fire Detection", resized_frame)
    # -------------------------------------------------------------------------

    # Xử lý frame ngay lập tức khi camera mạng truyền về, nhấn 'q' để thoát
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Hệ thống giám sát đã đóng an toàn.")