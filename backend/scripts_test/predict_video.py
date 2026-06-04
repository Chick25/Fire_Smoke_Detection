import cv2
import time
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO

# Hàm bổ trợ để vẽ chữ tiếng Việt có dấu lên frame OpenCV
def put_vietnamese_text(img, text, position, font_size, color):
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    draw = ImageDraw.Draw(pil_img)
    
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()
        
    draw.text(position, text, font=font, fill=color)
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

# 1. Tự động xử lý đường dẫn tuyệt đối
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "fire_smoke_model", "best_new.pt")

model = YOLO(MODEL_PATH)

# 2. Đường dẫn tới file video thử nghiệm
VIDEO_PATH = os.path.join(BASE_DIR, "test2.mp4") 
cap = cv2.VideoCapture(VIDEO_PATH)

# 3. Các tham số cấu hình bộ đệm logic chống nhiễu
fire_frame_counter = 0
FRAME_THRESHOLD = 25  
last_alert_time = 0
ALERT_COOLDOWN = 15   

print(f"=== Hệ thống kiểm định kép (Lửa + Khói) chạy trên Video: {VIDEO_PATH} ===")

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        print("Đã chạy hết video hoặc không thể đọc được file video.")
        break

    # Dự đoán vật thể với ngưỡng chính xác 30%
    results = model(frame, conf=0.30, verbose=False)
    
    # Lấy frame đã vẽ sẵn các hộp bounding box của YOLO làm nền gốc
    annotated_frame = results[0].plot()
    
    # Tính toán diện tích khung hình
    frame_h, frame_w, _ = frame.shape
    total_frame_area = frame_h * frame_w
    
    is_danger_detected = False
    has_fire = False
    has_smoke = False
    max_area_percentage = 0.0

    # Quét tất cả các box nhận diện được trong frame
    for box in results[0].boxes:
        class_id = int(box.cls[0])
        # Ép tên nhãn về chữ thường hoàn toàn để tránh lỗi chữ hoa/chữ thường (Fire/fire)
        label = model.names[class_id].lower()
        
        if label == 'fire' or label == 'smoke':
            is_danger_detected = True
            
            # Đánh dấu trạng thái xuất hiện riêng biệt
            if label == 'fire': 
                has_fire = True
            if label == 'smoke': 
                has_smoke = True
            
            # Tính toán diện tích vùng bao phủ
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            box_area = (x2 - x1) * (y2 - y1)
            area_percentage = (box_area / total_frame_area) * 100
            if area_percentage > max_area_percentage:
                max_area_percentage = area_percentage
            
    # Thuật toán bộ đệm thời gian (Buffer) chống nhiễu ánh sáng
    if is_danger_detected:
        fire_frame_counter += 1
    else:
        fire_frame_counter = max(0, fire_frame_counter - 1)

    # ĐƯA LỆNH VẼ THỜI GIAN TÍCH LŨY LÊN TRƯỚC (Để không bị đè mất các text cảnh báo nguy hiểm)
    annotated_frame = put_vietnamese_text(annotated_frame, f"Thời gian tích lũy: {fire_frame_counter}/{FRAME_THRESHOLD}", (20, 75), 18, (0, 255, 255))

    # ĐÁNH GIÁ MỨC ĐỘ NGUY HIỂM KHI VƯỢT NGƯỠNG BÁO ĐỘNG
    if fire_frame_counter >= FRAME_THRESHOLD:
        current_time = time.time()
        
        danger_level = "THẤP (LOW)"
        rgb_color = (0, 255, 255) # Màu vàng BGR cho OpenCV (vẽ bằng PIL cần đổi sang hệ RGB)
        pil_color = (255, 255, 0) # Màu vàng chuẩn hệ RGB
        
        # KIỂM TRA ĐIỀU KIỆN KÉP ĐỂ LÊN MỨC CAO (Có cả lửa + khói)
        if has_fire and has_smoke and (max_area_percentage >= 5.0 or fire_frame_counter > 60):
            danger_level = "CAO (HIGH) !!!"
            pil_color = (255, 0, 0) # Màu đỏ rực nguy hiểm
            
        # MỨC TRUNG BÌNH
        elif has_fire or max_area_percentage >= 2.0 or fire_frame_counter > 100:
            danger_level = "TRUNG BÌNH (MEDIUM)"
            pil_color = (255, 165, 0) # Màu cam cảnh báo
            
        # MỨC THẤP
        else:
            danger_level = "THẤP (LOW)"
            pil_color = (255, 255, 0)

        # Tiến hành vẽ đè các lớp chữ UI báo động lên trên cùng
        annotated_frame = put_vietnamese_text(annotated_frame, f"ALERT: {danger_level}", (20, 25), 26, pil_color)
        annotated_frame = put_vietnamese_text(annotated_frame, f"Diện tích vùng cháy: {max_area_percentage:.2f}%", (20, 115), 16, (255, 255, 255))
        
        status_text = f"Trạng thái: {'Có Lửa' if has_fire else 'Không Lửa'} | {'Có Khói' if has_smoke else 'Không Khói'}"
        annotated_frame = put_vietnamese_text(annotated_frame, status_text, (20, 145), 14, (200, 200, 200))
        
        if current_time - last_alert_time > ALERT_COOLDOWN:
            print(f"🚨 [{danger_level}] - Lửa: {has_fire} | Khói: {has_smoke} | Diện tích: {max_area_percentage:.2f}%")
            last_alert_time = current_time

    # Xuất kết quả màn hình hiển thị trực quan
    cv2.imshow("Video Test - Fire Monitoring System", annotated_frame)

    if cv2.waitKey(25) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Đã đóng chương trình test video.")