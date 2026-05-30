import cv2
import time
from ultralytics import YOLO

# 1. Đường dẫn tới file trọng số tốt nhất đã train của bạn
MODEL_PATH = "fire_smoke_model/best.pt"
model = YOLO(MODEL_PATH)

# 2. Đường dẫn tới file video thử nghiệm của bạn (thay tên file video thực tế vào đây)
# Ví dụ bạn có file video đặt tên là 'test_chay.mp4'
VIDEO_PATH = "vid1.mp4" 
cap = cv2.VideoCapture(VIDEO_PATH)

# 3. Các tham số cấu hình bộ đệm logic chống nhiễu
fire_frame_counter = 0
FRAME_THRESHOLD = 25  # Phải phát hiện liên tục 25 frames (~1 giây video) mới báo động
last_alert_time = 0
ALERT_COOLDOWN = 15   # Giới hạn khoảng cách giữa các lần cảnh báo là 15 giây

print(f"=== Đang chạy thử nghiệm hệ thống bằng Video: {VIDEO_PATH} ===")

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        print("Đã chạy hết video hoặc không thể đọc được file video.")
        break

    # Dự đoán vật thể (conf=0.45 để cân bằng độ nhạy)
    results = model(frame, conf=0.45, verbose=False)
    
    # Vẽ các bounding box nhận diện lên khung hình video
    annotated_frame = results[0].plot()
    
    is_danger_detected = False
    
    # Duyệt qua các object quét được trong frame hiện tại để kiểm tra nhãn
    for box in results[0].boxes:
        class_id = int(box.cls[0])
        label = model.names[class_id]
        
        if label in ['fire', 'smoke']:
            is_danger_detected = True
            break 
            
    # Xử lý thuật toán bộ đệm thời gian (Buffer Risk Level)
    if is_danger_detected:
        fire_frame_counter += 1
    else:
        fire_frame_counter = max(0, fire_frame_counter - 1)

    # Khi mức độ rủi ro vượt ngưỡng thiết lập
    if fire_frame_counter >= FRAME_THRESHOLD:
        current_time = time.time()
        
        # In chữ cảnh báo nguy hiểm màu đỏ chớp nháy đè lên luồng video
        cv2.putText(annotated_frame, "!!! EMERGENCY: FIRE / SMOKE DETECTED !!!", (20, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)
        
        if current_time - last_alert_time > ALERT_COOLDOWN:
            print(f"🚨 [CẢNH BÁO HOẢ HOẠN] Phát hiện dấu hiệu cháy nổ trong video lúc: {time.strftime('%H:%M:%S')}")
            last_alert_time = current_time

    # Hiển thị thanh trạng thái mức độ rủi ro hiện tại lên màn hình video
    cv2.putText(annotated_frame, f"Risk Level: {fire_frame_counter}/{FRAME_THRESHOLD}", (20, 90), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    # Hiển thị luồng video kết quả
    cv2.imshow("Video Test - Fire Monitoring System", annotated_frame)

    # Điều chỉnh waitKey(25) để video chạy mượt đúng tốc độ thông thường, nhấn 'q' để thoát sớm
    if cv2.waitKey(25) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Đã đóng chương trình test video.")