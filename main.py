import cv2
import time
from ultralytics import YOLO

# 1. Đường dẫn tới file trọng số tốt nhất đã giải nén của bạn
# Vì file main.py nằm ngoài, ta trỏ đường dẫn vào trong thư mục giải nén
MODEL_PATH = "fire_smoke_model/best.pt"
model = YOLO(MODEL_PATH)

# 2. Nguồn camera giám sát: 
# Số 0 đại diện cho Webcam máy tính/laptop. 
# Nếu lắp camera IP trong khu dân cư, bạn thay số 0 bằng chuỗi link RTSP: "rtsp://username:password@IP_Address:Port/h264"
VIDEO_SOURCE = r"E:\Xử lí ảnh số\video\7883830674410.mp4"
cap = cv2.VideoCapture(VIDEO_SOURCE)

# 3. Các tham số cấu hình bộ đệm logic (Chống báo động giả do đèn xe, hoàng hôn)
fire_frame_counter = 0
FRAME_THRESHOLD = 30  # AI phải nhìn thấy lửa/khói liên tục trong 30 frames (~1.5 giây) thì mới kích hoạt chuông báo
last_alert_time = 0
ALERT_COOLDOWN = 20   # Giới hạn khoảng cách giữa các lần cảnh báo là 20 giây (tránh spam tin nhắn)

print("=== Hệ thống giám sát hỏa hoạn khu dân cư đã sẵn sàng ===")

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        print("Lỗi: Không thể kết nối hoặc đọc luồng video từ Camera.")
        break

    # Dự đoán vật thể (conf=0.45 để cân bằng giữa độ nhạy của khói và độ chính xác của lửa)
    results = model(frame, conf=0.45, verbose=False)
    
    # Vẽ các bounding box nhận diện lên khung hình
    annotated_frame = results[0].plot()
    
    is_danger_detected = False
    
    # Duyệt qua các object quét được trong frame hiện tại để bắt nhãn
    for box in results[0].boxes:
        class_id = int(box.cls[0])
        label = model.names[class_id] # Lấy tên nhãn ('fire' hoặc 'smoke')
        
        if label in ['fire', 'smoke']:
            is_danger_detected = True
            break # Thấy khói hoặc lửa là đủ điều kiện kích hoạt đếm nguy hiểm
            
    # Xử lý thuật toán bộ đệm thời gian (Buffer)
    if is_danger_detected:
        fire_frame_counter += 1
    else:
        # Nếu frame này mất dấu, giảm dần mức độ rủi ro chứ không reset về 0 lập tức (tránh mất dấu tạm thời)
        fire_frame_counter = max(0, fire_frame_counter - 1)

    # Khi mức độ rủi ro vượt ngưỡng thiết lập
    if fire_frame_counter >= FRAME_THRESHOLD:
        current_time = time.time()
        
        # In chữ cảnh báo màu đỏ chớp nháy đè lên luồng màn hình camera giám sát
        cv2.putText(annotated_frame, "!!! EMERGENCY: FIRE / SMOKE DETECTED !!!", (20, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)
        
        # Kích hoạt hành động báo động (In ra Terminal hoặc gửi webhook API về Telegram/Zalo)
        if current_time - last_alert_time > ALERT_COOLDOWN:
            print(f"🚨 [CẢNH BÁO NGUY HIỂM] Phát hiện hỏa hoạn tại khu vực camera giám sát vào lúc: {time.strftime('%H:%M:%S')}")
            # Gợi ý mở rộng: Bạn có thể viết thêm hàm kích hoạt một hồi còi hú tại đây
            last_alert_time = current_time

    # Hiển thị mức độ rủi ro hiện tại lên màn hình để dễ dàng theo dõi, tinh chỉnh
    cv2.putText(annotated_frame, f"Risk Level: {fire_frame_counter}/{FRAME_THRESHOLD}", (20, 90), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    # Hiển thị luồng camera giám sát ra màn hình máy tính
    cv2.imshow("Khu Dan Cu - Fire Monitoring System", annotated_frame)

    # Nhấn phím 'q' trên bàn phím để tắt hệ thống một cách an toàn
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Hệ thống đã dừng hoạt động.")