import base64
import cv2
import time
import os  # Thêm thư viện os để kiểm tra đường dẫn file
import threading  # ĐÃ THAY THẾ: Dùng thư viện luồng chuẩn của Python thay cho eventlet
from flask import Flask, request, jsonify  
from flask_socketio import SocketIO
from flask_cors import CORS
from ultralytics import YOLO
from werkzeug.utils import secure_filename  
import numpy as np
from collections import deque
from src.services.send_mess import send_messenger_alert_to_all# Hàm gửi tin nhắn đã được tách riêng vào file send_mess.py để dễ quản lý và tái sử dụng


# Khởi tạo cấu hình Flask và Socket.IO (Bỏ async_mode='eventlet' để chạy ổn định trên Windows)
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Nạp mô hình YOLOv8 từ thư mục của bạn
MODEL_PATH = "..\\fire_smoke_model\\best_final.pt"
model = YOLO(MODEL_PATH)

def get_metrics(frame, fire_boxes, smoke_boxes, prev_fire_area):
    H, W = frame.shape[:2]
    img_area = H * W

    fire_area = sum(
        (x2 - x1) * (y2 - y1)
        for x1, y1, x2, y2 in fire_boxes
    )

    smoke_area = sum(
        (x2 - x1) * (y2 - y1)
        for x1, y1, x2, y2 in smoke_boxes
    )

    fire_percent = min(100.0, fire_area / img_area * 100)
    smoke_percent = min(100.0, smoke_area / img_area * 100)

    intensities = []

    for x1, y1, x2, y2 in fire_boxes:
        roi = frame[y1:y2, x1:x2]

        if roi.size == 0:
            continue

        hsv = cv2.cvtColor(
            roi,
            cv2.COLOR_BGR2HSV
        )

        h = hsv[:, :, 0]
        s = hsv[:, :, 1]
        v = hsv[:, :, 2]

        mask = (
            (
                (h <= 15)
                | (h >= 170)
                | ((h >= 15) & (h <= 35))
            )
            & (s > 80)
            & (v > 80)
        )

        ratio = np.sum(mask) / max(mask.size, 1)

        bright = (
            np.mean(v[mask]) / 255
            if ratio > 0.01
            else 0
        )

        intensities.append(
            (ratio + bright) / 2 * 100
        )

    color_intensity = (
        float(np.mean(intensities))
        if intensities
        else 0
    )

    if prev_fire_area > 0:
        spread_rate = abs(
            fire_area - prev_fire_area
        ) / prev_fire_area * 100
    else:
        spread_rate = 0

    metrics = {
        "fire_area": fire_percent,
        "smoke_area": smoke_percent,
        "intensity": color_intensity,
        "spread_rate": min(100, spread_rate),
    }

    return metrics, fire_area

def score_and_level(metrics):

    score = (
    metrics["fire_area"] * 0.6
    + metrics["smoke_area"] * 0.15
    + metrics["intensity"] * 0.15
    + metrics["spread_rate"] * 0.1
    )

    score = min(score, 100)

    if score < 10:
        level = "SAFE"
    elif score < 30:
        level = "MEDIUM"
    elif score < 50:
        level = "HIGH"
    else:
        level = "CRITICAL"

    return score, level

print("🔥 [AI] Đang làm nóng (Warm-up) mô hình YOLO...")
dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
model(dummy_frame, verbose=False) # Chạy mồi 1 lần duy nhất để nạp bộ nhớ
print("✅ [AI] Mô hình đã sẵn sàng nhận diện tốc độ cao!")

# Ép YOLO thực hiện fuse và compile mô hình ngay trên luồng chính để chống lỗi AttributeError: bn
if hasattr(model.model, 'fuse'):
    model.model.fuse()

is_streaming = False
thread_active = False
current_video_source = "media/vid2.mp4" 
video_speed_delay = 0.04  # Delay mặc định ban đầu cho tốc độ x1

# Định nghĩa thư mục lưu video
UPLOAD_FOLDER = 'media'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload', methods=['POST'])
def upload_video():
    if 'video_file' not in request.files:
        return jsonify({'error': 'Không tìm thấy dữ liệu file'}), 400
        
    file = request.files['video_file']
    if file.filename == '':
        return jsonify({'error': 'Tên file không hợp lệ'}), 400
        
    if file:
        filename = secure_filename(file.filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        print(f"📥 [SERVER] Đã nhận và lưu file thành công: {file_path}")
        return jsonify({'message': 'Upload thành công', 'filename': filename}), 200


# def generate_frames():
#     global is_streaming, current_video_source, video_speed_delay, thread_active
    
#     thread_active = True
#     # print(f"🎬 [STREAM] Khởi động luồng xử lý cho nguồn: {current_video_source}")

#     print(f"🎬 [AI RUN] Bắt đầu nhận diện trên nguồn: {current_video_source}")
#     cap = cv2.VideoCapture(current_video_source)

#     fire_frame_counter = 0
#     FRAME_THRESHOLD =  15
#     last_alert_time = 0
#     ALERT_COOLDOWN = 20   
    
#     total_frames = 0

#     while is_streaming and cap.isOpened():
#         success, frame = cap.read()
#         if not success:
#             cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
#             continue

#         total_frames += 1    

#         # results = model(frame, conf=0.45, verbose=False)
#         # annotated_frame = results[0].plot()
#         # === ĐÃ SỬA: Hạ ngưỡng conf để bắt lửa sớm và tăng iou để cho phép hiện nhiều box chồng lấn ===
#         results = model(frame, conf=0.30, iou=0.7, verbose=False)
        
#         # Tạo một bản sao của khung hình gốc để tự vẽ box lên bằng tay
#         annotated_frame = frame.copy()
        
#         is_fire_detected = False   
        
#         # Duyệt qua từng đối tượng (box) mà mạng AI YOLOv8 quét được trong khung hình
#         for box in results[0].boxes:
#             # 1. Trích xuất tọa độ 4 góc của hộp (x_min, y_min, x_max, y_max)
#             x1, y1, x2, y2 = map(int, box.xyxy[0])
            
#             # 2. Lấy độ tự tin (Confidence) và nhãn lớp (Label)
#             conf = float(box.conf[0])
#             label = str(model.names[int(box.cls[0])]).strip().lower()
            
#             # Kiểm tra xem có phải lửa hoặc khói không để kích hoạt biến trạng thái nguy hiểm
#             if label in ['fire', 'smoke']:
#                 is_fire_detected = True
                
#                 # 3. Định nghĩa màu sắc Bounding Box giống bên Train: 
#                 # Lửa màu Đỏ (độ dày 2), Khói màu Xanh lục hoặc Xanh dương tùy ý bạn
#                 if label == 'fire':
#                     box_color = (0, 0, 255)      # Màu Đỏ (BGR)
#                 else:
#                     box_color = (255, 255, 0)    # Màu Xanh Cyan/Cyan dương cho khói
                
#                 # 4. Vẽ hình chữ nhật bao quanh vùng cháy lên ảnh annotated_frame
#                 cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), box_color, 2)
                
#                 # 5. Viết chữ hiển thị tên lớp và % tự tin ngay trên đầu hộp chữ nhật
#                 caption = f"{label.upper()} {conf:.2f}"
#                 cv2.putText(annotated_frame, caption, (x1, y1 - 8),
#                             cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)
        
#         # is_danger_detected = False
#         is_fire_detected = False   # ĐÃ ĐỔI: Tập trung kiểm tra nhãn lửa
#         is_smoke_detected = False  # Theo dõi thêm nhãn khói nếu cần
#         detected_type = 'fire' 
        
#         for box in results[0].boxes:
#             class_id = int(box.cls[0])
#             label = model.names[class_id]
#             # if label in ['fire', 'smoke']:
#             #     is_danger_detected = True
#             #     detected_type = label 
#             #     break
#             # print(f"🔍 [YOLO DETECT] Tìm thấy nhãn: '{label}' với độ tự tin: {float(box.conf[0]):.2f}")
#             if label in ['fire', 'Fire']:
#                 is_fire_detected = True
#                 # detected_type = 'fire'
#                 break # Ưu tiên lửa cao nhất, thấy lửa là dừng vòng lặp để xử lý ngay
#             elif label == 'smoke':
#                 is_smoke_detected = True
#                 # detected_type = 'smoke'
                
#         if is_fire_detected:
#             fire_frame_counter = min(FRAME_THRESHOLD, fire_frame_counter + 1)
#             detected_type = 'fire'
#         else:
#             fire_frame_counter = max(0, fire_frame_counter - 1)
#             if is_smoke_detected and fire_frame_counter == 0:
#                 detected_type = 'smoke'
#         # fire_frame_counter = min(FRAME_THRESHOLD, fire_frame_counter + 1)

#         # 1. BẮN SỰ KIỆN 1: Ảnh mã hóa Base64 về kênh 'video_frame'
#         _, buffer = cv2.imencode('.jpg', annotated_frame)
#         frame_base64 = base64.b64encode(buffer).decode('utf-8')
#         socketio.emit('video_frame', {'image': frame_base64}) 

#         # 2. BẮN SỰ KIỆN 2: Cập nhật chỉ số rủi ro về kênh 'risk_update'
#         risk_percentage = int((fire_frame_counter / FRAME_THRESHOLD) * 100)
#         socketio.emit('risk_update', {
#             'level': fire_frame_counter,       
#             'percentage': risk_percentage      
#         })

#         # 3. BẮN SỰ KIỆN 3: Kích hoạt thông báo lên kênh 'new_alert'
#         if fire_frame_counter >= FRAME_THRESHOLD:
#             current_time = time.time()
#             if current_time - last_alert_time > ALERT_COOLDOWN:
#                 socketio.emit('new_alert', {
#                     'type': detected_type,
#                     'message': f"Cảnh báo nguy hiểm! Phát hiện đám {'LỬA' if detected_type == 'fire' else 'KHÓI'} lớn xuất hiện tại Khu dân cư!"
#                 })
#                 print(f"🚨 [HỆ THỐNG] Đã bắn sự kiện 'new_alert' sang FE lúc: {time.strftime('%H:%M:%S')}")

#                 alert_msg = f"🚨 [CẢNH BÁO NGUY HIỂM] Phát hiện {'LỬA' if detected_type == 'fire' else 'KHÓI'} tại khu vực camera giám sát vào lúc: {time.strftime('%H:%M:%S')}"
#                 messenger_thread = threading.Thread(target=send_messenger_alert_to_all, args=(alert_msg,))
#                 messenger_thread.daemon = True
#                 messenger_thread.start()


#                 last_alert_time = current_time

#         # Sử dụng time.sleep chuẩn của Python, thời gian nghỉ thay đổi linh hoạt theo nút bấm tốc độ
#         time.sleep(video_speed_delay)
        
#     cap.release()
#     thread_active = False
#     print("🛑 [AI STOP] Đã giải phóng luồng xử lý video hiện tại.")

# def generate_frames():
#     global is_streaming, current_video_source, video_speed_delay, thread_active
    
#     thread_active = True
#     print(f"🎬 [AI RUN] Bắt đầu nhận diện trên nguồn: {current_video_source}")
#     cap = cv2.VideoCapture(current_video_source)

#     fire_frame_counter = 0
#     FRAME_THRESHOLD = 15
#     last_alert_time = 0
#     ALERT_COOLDOWN = 20   
    
#     total_frames = 0

#     while is_streaming and cap.isOpened():
#         success, frame = cap.read()
#         if not success:
#             cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
#             continue

#         total_frames += 1    

#         # Chạy AI với ngưỡng nhạy bén giống môi trường Train
#         results = model(frame, conf=0.30, iou=0.7, verbose=False)
        
#         # Bản sao khung hình gốc để tự vẽ box thủ công
#         annotated_frame = frame.copy()
        
#         # Thiết lập các biến trạng thái chuẩn cho toàn bộ vòng lặp
#         is_fire_detected = False   
#         is_smoke_detected = False
#         detected_type = 'fire' 
        
#         # =================================================================
#         # GỘP CHUNG 1 VÒNG LẶP DUY NHẤT: VỪA VẼ BOX VỪA PHÂN LOẠI TRẠNG THÁI
#         # =================================================================
#         for box in results[0].boxes:
#             x1, y1, x2, y2 = map(int, box.xyxy[0])
#             conf = float(box.conf[0])
#             label = str(model.names[int(box.cls[0])]).strip().lower()
            
#             if label in ['fire', 'smoke']:
#                 # Đánh dấu trạng thái nguy hiểm để xử lý logic tăng/giảm bộ đệm
#                 if label == 'fire':
#                     is_fire_detected = True
#                     box_color = (0, 0, 255)      # Màu Đỏ cho Lửa
#                 else:
#                     is_smoke_detected = True
#                     box_color = (255, 255, 0)    # Màu Xanh Cyan cho Khói
                
#                 # Vẽ hình chữ nhật và text y hệt cấu trúc mong muốn
#                 cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), box_color, 2)
#                 caption = f"{label.upper()} {conf:.2f}"
#                 cv2.putText(annotated_frame, caption, (x1, y1 - 8),
#                             cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)
        
#         # =================================================================
#         # XỬ LÝ BỘ ĐỆM KIỂM ĐỊNH NGUY CƠ (RISK LEVEL BUFFER)
#         # =================================================================
#         if is_fire_detected:
#             fire_frame_counter = min(FRAME_THRESHOLD, fire_frame_counter + 1)
#             detected_type = 'fire'
#         else:
#             fire_frame_counter = max(0, fire_frame_counter - 1)
#             if is_smoke_detected and fire_frame_counter == 0:
#                 detected_type = 'smoke'

#         # =================================================================
#         # TỐI ƯU REAL-TIME: CỨ 3 FRAME THÌ MỚI EMIT ĐẨY ẢNH VÀ RISK LÊN FE
#         # Cách này giúp giải phóng gánh nặng Socket, triệt tiêu lag giật hình!
#         # =================================================================
#         if total_frames % 3 == 0:
#             _, buffer = cv2.imencode('.jpg', annotated_frame)
#             frame_base64 = base64.b64encode(buffer).decode('utf-8')
#             socketio.emit('video_frame', {'image': frame_base64}) 

#             risk_percentage = int((fire_frame_counter / FRAME_THRESHOLD) * 100)
#             socketio.emit('risk_update', {
#                 'level': fire_frame_counter,       
#                 'percentage': risk_percentage      
#             })

#         # =================================================================
#         # KÍCH HOẠT CỔNG NGOẠI VI KHI VƯỢT NGƯỠNG AN TOÀN
#         # =================================================================
#         if fire_frame_counter >= FRAME_THRESHOLD:
#             current_time = time.time()
#             if current_time - last_alert_time > ALERT_COOLDOWN:
#                 socketio.emit('new_alert', {
#                     'type': detected_type,
#                     'message': f"Cảnh báo nguy hiểm! Phát hiện đám {'LỬA' if detected_type == 'fire' else 'KHÓI'} lớn xuất hiện tại Khu dân cư!"
#                 })
#                 print(f"🚨 [HỆ THỐNG] Đã bắn sự kiện 'new_alert' sang FE lúc: {time.strftime('%H:%M:%S')}")

#                 alert_msg = f"🚨 [CẢNH BÁO NGUY HIỂM] Phát hiện {'LỬA' if detected_type == 'fire' else 'KHÓI'} tại khu vực camera giám sát vào lúc: {time.strftime('%H:%M:%S')}"
                
#                 # Luồng chạy ngầm gửi thông báo không ảnh hưởng tốc độ video
#                 messenger_thread = threading.Thread(target=send_messenger_alert_to_all, args=(alert_msg,))
#                 messenger_thread.daemon = True
#                 messenger_thread.start()

#                 last_alert_time = current_time

#         # Ép độ trễ nghỉ cực nhỏ (0.005s) vì việc xử lý thuật toán trên đã đủ tạo độ trễ mượt
#         time.sleep(0.005)
        
#     cap.release()
#     thread_active = False
#     print("🛑 [AI STOP] Đã giải phóng luồng xử lý video hiện tại.")

# def generate_frames():
#     global is_streaming, current_video_source, video_speed_delay, thread_active
    
#     thread_active = True
#     cap = cv2.VideoCapture(current_video_source)

#     # 1. LẤY TỐC ĐỘ FPS GỐC CỦA FILE VIDEO ĐỂ TÍNH THỜI GIAN CHUẨN
#     fps = cap.get(cv2.CAP_PROP_FPS)
#     if fps <= 0 or fps > 60: 
#         fps = 25.0  # Nếu không lấy được, đặt mặc định là 25 FPS
    
#     # Thời gian tiêu chuẩn giữa 2 khung hình (Ví dụ: 25 FPS -> ~0.04 giây = 40ms)
#     frame_duration = 1.0 / fps 

#     fire_frame_counter = 0
#     FRAME_THRESHOLD = 15
#     last_alert_time = 0
#     ALERT_COOLDOWN = 20   
#     total_frames = 0

#     while is_streaming and cap.isOpened():
#         # BẤM ĐỒNG HỒ: Ghi lại thời điểm bắt đầu xử lý khung hình này
#         start_time = time.time()

#         success, frame = cap.read()
#         if not success:
#             cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
#             continue

#         total_frames += 1    

#         # Chạy AI YOLO
#         results = model(frame, conf=0.30, iou=0.7, verbose=False)
        
#         # Logic tự vẽ Bounding Box (Giữ nguyên phần code xử lý vẽ box của bạn ở đây)
#         annotated_frame = frame.copy()
#         is_fire_detected = False   
#         is_smoke_detected = False
#         for box in results[0].boxes:
#             x1, y1, x2, y2 = map(int, box.xyxy[0])
#             conf = float(box.conf[0])
#             label = str(model.names[int(box.cls[0])]).strip().lower()
#             if label in ['fire', 'smoke']:
#                 if label == 'fire': is_fire_detected = True
#                 else: is_smoke_detected = True
#                 box_color = (0, 0, 255) if label == 'fire' else (255, 255, 0)
#                 cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), box_color, 2)
#                 cv2.putText(annotated_frame, f"{label.upper()} {conf:.2f}", (x1, y1 - 8),
#                             cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)
        
#         # Tính toán bộ đệm nguy cơ
#         if is_fire_detected:
#             fire_frame_counter = min(FRAME_THRESHOLD, fire_frame_counter + 1)
#             detected_type = 'fire'
#         else:
#             fire_frame_counter = max(0, fire_frame_counter - 1)
#             if is_smoke_detected and fire_frame_counter == 0:
#                 detected_type = 'smoke'

#         # Đẩy dữ liệu sang Front-End (Cứ 2 hoặc 3 frame tùy bạn chọn, thử mức % 2 xem mượt hơn không)
#         if total_frames % 2 == 0:
#             _, buffer = cv2.imencode('.jpg', annotated_frame)
#             frame_base64 = base64.b64encode(buffer).decode('utf-8')
#             socketio.emit('video_frame', {'image': frame_base64}) 

#             risk_percentage = int((fire_frame_counter / FRAME_THRESHOLD) * 100)
#             socketio.emit('risk_update', {
#                 'level': fire_frame_counter,       
#                 'percentage': risk_percentage      
#             })

#         # Logic kích hoạt thông báo ngoại vi (Giữ nguyên phần còi hú/Messenger của bạn...)
#         if fire_frame_counter >= FRAME_THRESHOLD:
#             current_time = time.time()
#             if current_time - last_alert_time > ALERT_COOLDOWN:
#                 # ... (Đoạn emit 'new_alert' và tạo thread messenger của bạn giữ nguyên) ...
#                 last_alert_time = current_time

#         # =================================================================
#         # TỰ ĐỘNG TÍNH TOÁN ĐỘ TRỄ BÙ TRỪ THỜI GIAN THỰC
#         # =================================================================
#         # Tính xem từ đầu vòng lặp đến giờ máy tính đã xử lý mất bao lâu rồi
#         elapsed_time = time.time() - start_time
        
#         # Thời gian cần phải nghỉ còn lại để đạt đúng tốc độ FPS chuẩn của video
#         sleep_delay = frame_duration - elapsed_time
        
#         # Nếu AI xử lý nhanh hơn tốc độ video, cho ngủ bù phần thời gian thừa
#         if sleep_delay > 0:
#             time.sleep(sleep_delay)
#         else:
#             # Nếu AI xử lý quá nặng vượt mốc FPS, cho nghỉ 1ms cực ngắn để giải phóng CPU tránh đơ máy
#             time.sleep(0.001)
        
#     cap.release()
#     thread_active = False
#     print("🛑 [AI STOP] Đã giải phóng luồng xử lý video hiện tại.")

def generate_frames():
    global is_streaming, current_video_source, video_speed_delay, thread_active
    
    thread_active = True
    cap = cv2.VideoCapture(current_video_source)

    fire_frame_counter = 0
    FRAME_THRESHOLD = 15
    last_alert_time = 0
    ALERT_COOLDOWN = 20   

    prev_fire_area = 0

    fire_area_history = deque(maxlen=10)
    smoke_area_history = deque(maxlen=10)

    fire_duration = 0
    fire_start_time = None

    frame_count = 0

    while is_streaming and cap.isOpened():
        frame_count += 1

        success, frame = cap.read()
        if not success:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        # 1. CHẠY AI TRÊN MỌI KHUNG HÌNH - HẠ CONF XUỐNG 0.25 ĐỂ KHÔNG BỊ NUỐT BOX
        # Ngưỡng conf=0.25 và iou=0.5 là tỷ lệ vàng giúp giữ ô vuông cực kỳ bền vững, không nhấp nháy
        results = model(frame, conf=0.25, iou=0.5, device='cpu', verbose=False)
        
        annotated_frame = frame.copy()
        is_fire_detected = False   
        is_smoke_detected = False
        detected_type = 'fire' 

        fire_boxes = []
        smoke_boxes = []
        # 2. DUYỆT VÀ VẼ LẠI TOÀN BỘ BOX QUÉT ĐƯỢC
        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            label = str(model.names[int(box.cls[0])]).strip().lower()
           
            
            if label in ['fire', 'smoke']:
                if label == 'fire':
                    fire_boxes.append(
                        (x1, y1, x2, y2)
                    )
                    is_fire_detected = True
                    box_color = (0, 0, 255)      # Đỏ cho Lửa
                else:
                    smoke_boxes.append(
                        (x1, y1, x2, y2)
                    )
                    is_smoke_detected = True
                    box_color = (255, 255, 0)    # Xanh Cyan cho Khói
                
                # Vẽ trực tiếp lên khung hình hiện tại
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), box_color, 2)
                caption = f"{label.upper()} {conf:.2f}"
                cv2.putText(annotated_frame, caption, (x1, y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)
        
        metrics, prev_fire_area = get_metrics(
            frame,
            fire_boxes,
            smoke_boxes,
            prev_fire_area
        )

        fsi_score, risk_level = score_and_level(
            metrics
        )

        if len(fire_boxes) > 0 or len(smoke_boxes) > 0:

            if fire_start_time is None:
                fire_start_time = time.time()

            fire_duration = int(
                time.time() - fire_start_time
            )

        else:

            fire_start_time = None
            fire_duration = 0
        
        fire_area_history.append(
            metrics["fire_area"]
        )

        smoke_area_history.append(
            metrics["smoke_area"]
        )

        fire_growth = 0
        smoke_growth = 0

        if len(fire_area_history) > 1:

            fire_growth = (
                fire_area_history[-1]
                - fire_area_history[0]
            )

        if len(smoke_area_history) > 1:

            smoke_growth = (
                smoke_area_history[-1]
                - smoke_area_history[0]
            )
        
        # 3. LOGIC TÍCH LŨY RỦI RO (Giữ nguyên)
        if is_fire_detected:
            fire_frame_counter = min(FRAME_THRESHOLD, fire_frame_counter + 1)
            detected_type = 'fire'
        else:
            fire_frame_counter = max(0, fire_frame_counter - 1)
            if is_smoke_detected and fire_frame_counter == 0:
                detected_type = 'smoke'

        # 4. MÃ HÓA BASE64 VÀ PHÁT SỰ KIỆN LIÊN TỤC (Không bỏ cách frame)
        # Vì bạn cần độ ổn định hiển thị cao nhất, frame nào cũng sẽ được truyền về React
        _, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        socketio.emit('video_frame', {'image': frame_base64}) 

        risk_percentage = int((fire_frame_counter / FRAME_THRESHOLD) * 100)
        socketio.emit('risk_update', {
            'level': fire_frame_counter,       
            'percentage': risk_percentage      
        })

        analysis_data = {
            "fireArea": round(metrics["fire_area"], 2),
            "smokeArea": round(metrics["smoke_area"], 2),
            "fireGrowth": round(fire_growth, 2),
            "smokeGrowth": round(smoke_growth, 2),
            "duration": fire_duration,
            "intensity": round(metrics["intensity"], 2),
            "fsi": round(fsi_score, 2),
            "risk": risk_level
        }
        socketio.emit('analysis_update', analysis_data)

        # 5. LOGIC PHÁT CẢNH BÁO NGOẠI VI (new_alert, Messenger...)
        if fire_frame_counter >= FRAME_THRESHOLD:
            current_time = time.time()
            if current_time - last_alert_time > ALERT_COOLDOWN:
                socketio.emit('new_alert', {
                    'type': detected_type,
                    'message': f"Cảnh báo nguy hiểm! Phát hiện đám {'LỬA' if detected_type == 'fire' else 'KHÓI'} lớn xuất hiện tại Khu dân cư!"
                })
                
                alert_msg = f"🚨 [CẢNH BÁO NGUY HIỂM] Phát hiện {'LỬA' if detected_type == 'fire' else 'KHÓI'} tại khu vực camera giám sát vào lúc: {time.strftime('%H:%M:%S')}"
                messenger_thread = threading.Thread(target=send_messenger_alert_to_all, args=(alert_msg,))
                messenger_thread.daemon = True
                messenger_thread.start()
                last_alert_time = current_time

        # 6. ĐIỀU TỐC CỐ ĐỊNH THEO CẤU HÌNH CŨ CỦA BẠN
        # Sử dụng đúng biến video_speed_delay để bạn kiểm soát tốc độ qua giao diện web
        time.sleep(video_speed_delay)
        
    cap.release()
    thread_active = False
    print("🛑 [AI STOP] Đã giải phóng luồng xử lý video hiện tại.")

@socketio.on('connect')
def handle_connect():
    print("🚀 [TÍN HIỆU] Giao diện Front-End đã kết nối thành công!")


@socketio.on('start_stream') 
# def handle_start_stream(data=None): 
#     global is_streaming, current_video_source, thread_active
    
#     if data and 'video_name' in data:
#         current_video_source = data['video_path']
#         custom_source = f"media/{data['video_name']}"
#         if os.path.exists(custom_source):
#             current_video_source = custom_source
#             print(f"📁 [CẤU HÌNH] Đã chuyển nguồn nhận diện sang file mới: {current_video_source}")
#         else:
#             print(f"⚠️ [CẢNH BÁO] Không tìm thấy file {custom_source}. Sử dụng nguồn mặc định.")
#     else:
#         current_video_source = "media/vid2.mp4" 
        
#     print("📡 [TÍN HIỆU] Nhận lệnh khởi động luồng stream video từ FE.")
    
#     if is_streaming:
#         is_streaming = False
#         time.sleep(0.3) 
        
#     timeout_counter = 0
#     while thread_active and timeout_counter < 20:  # Chờ tối đa 2 giây (20 * 0.1s)
#         time.sleep(0.1)
#         timeout_counter += 1

#     is_streaming = True
    
#     # ĐÃ THAY THẾ: Sử dụng Thread chuẩn của Python thay thế cho eventlet.spawn
#     thread = threading.Thread(target=generate_frames)
#     thread.daemon = True  # Đảm bảo luồng tự hủy khi tắt ứng dụng chính
#     thread.start()

@socketio.on('start_stream') 
def handle_start_stream(data=None): 
    global is_streaming, current_video_source, thread_active
    
    # 1. KIỂM TRA VÀ CẬP NHẬT NGUỒN VIDEO ĐẦU VÀO AN TOÀN
    if data and isinstance(data, dict):
        # Dùng .get() để lấy an toàn, nếu không có key sẽ trả về None chứ không sập Server
        video_name = data.get('video_name')
        
        if video_name:
            custom_source = f"media/{video_name}"
            
            # Kiểm tra xem file video đó thực sự có tồn tại trong thư mục media chưa
            if os.path.exists(custom_source):
                current_video_source = custom_source
                print(f"📁 [CẤU HÌNH] Đã chuyển nguồn nhận diện sang file mới: {current_video_source}")
            else:
                print(f"⚠️ [CẢNH BÁO] Không tìm thấy file {custom_source}. Tiếp tục dùng nguồn cũ: {current_video_source}")
        else:
            print(f"ℹ [HỆ THỐNG] Không nhận được tên video mới. Dùng nguồn hiện tại: {current_video_source}")
    else:
        # Nếu data truyền sang trống rỗng (Ví dụ khi vừa load trang bấm Start mặc định)
        current_video_source = "media/vid2.mp4" 
        print(f"ℹ [HỆ THỐNG] FE không truyền dữ liệu cấu hình. Đặt video mặc định: {current_video_source}")
        
    print("📡 [TÍN HIỆU] Nhận lệnh khởi động luồng stream video từ FE.")
    
    # 2. ĐIỀU PHỐI VÀ CHẶN TRÙNG LUỒNG AN TOÀN
    if is_streaming:
        is_streaming = False
        
    timeout_counter = 0
    # Đợi cho luồng cũ chạy xong xuôi lệnh cap.release() để giải phóng tài nguyên
    while thread_active and timeout_counter < 20:  # Chờ tối đa 2 giây (20 * 0.1s)
        time.sleep(0.1)
        timeout_counter += 1

    # 3. KÍCH HOẠT LUỒNG MỚI TRÊN NỀN SẠCH
    is_streaming = True
    
    thread = threading.Thread(target=generate_frames)
    thread.daemon = True  # Đảm bảo luồng tự hủy khi tắt ứng dụng chính
    thread.start()

@socketio.on('change_speed')
def handle_change_speed(data):
    global video_speed_delay
    if data and 'speed' in data:
        user_speed = float(data['speed'])
        video_speed_delay = 0.04 / user_speed
        print(f"⏱️ [CẤU HÌNH] Người dùng đổi tốc độ sang: {user_speed}x (Delay: {video_speed_delay}s)")


@socketio.on('disconnect')
def handle_disconnect():
    global is_streaming
    print("❌ [TÍN HIỆU] Front-End đã ngắt kết nối.")
    is_streaming = False


if __name__ == '__main__':
    print("=== Hệ thống giám sát hỏa hoạn khu dân cư đã sẵn sàng ===")
    print("📡 Đang mở cổng 5000 và đợi tín hiệu kết nối từ FE...")
    # Tắt chế độ debug=True để tránh xung đột luồng và crash cổng trên Windows
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)