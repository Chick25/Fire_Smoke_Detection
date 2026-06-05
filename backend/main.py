import base64
import sys
import cv2
import time

import os  
import threading  
import os  # Thêm thư viện os để kiểm tra đường dẫn file
import threading  # ĐÃ THAY THẾ: Dùng thư viện luồng chuẩn của Python thay cho eventlet
import requests
from flask import Flask, request, jsonify  
from flask_socketio import SocketIO
from flask_cors import CORS
from ultralytics import YOLO
from werkzeug.utils import secure_filename  


# Khởi tạo cấu hình Flask và Socket.IO
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Nạp mô hình YOLOv8
MODEL_PATH = "fire_smoke_model/best_new.pt"
model = YOLO(MODEL_PATH)

# Ép YOLO thực hiện fuse ngay trên luồng chính để chống lỗi AttributeError
import numpy as np
from collections import deque
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.services.send_mess import send_messenger_alert_to_all# Hàm gửi tin nhắn đã được tách riêng vào file send_mess.py để dễ quản lý và tái sử dụng
from src.services.predict_team_gmail import get_gmail_service, send_gmail_alert_to_team
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
# Khởi tạo cấu hình Flask và Socket.IO (Bỏ async_mode='eventlet' để chạy ổn định trên Windows)
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Nạp mô hình YOLOv8 từ thư mục của bạn
# MODEL_PATH = "..\\fire_smoke_model\\best_final.pt"
MODEL_PATH = os.path.join(BASE_DIR, '..', 'fire_smoke_model', 'best_final.pt')
model = YOLO(MODEL_PATH)

print("🔐 Đang xác thực dịch vụ Google API OAuth2...")
gmail_service = get_gmail_service()

EMERGENCY_PHONES = ["0823679193", "0773616537", "0795577525"]

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

# --- BIẾN TOÀN CỤC & CẤU HÌNH ---
is_streaming = False
current_video_source = "media/vid2.mp4" 
video_speed_delay = 0.04  # Tốc độ x1 mặc định

# SỬA LỖI: Thêm danh sách số điện thoại khẩn cấp bị thiếu
EMERGENCY_PHONES = ["0823679193","0773616537","0795577525"] 

# Khóa Thread để bảo vệ các biến toàn cục khi đọc/ghi từ nhiều luồng
data_lock = threading.Lock()

thread_active = False
# current_video_source = "media/vid2.mp4" 
current_video_source = "rtsp://admin:L2E1EB60@192.168.1.120:554/cam/realmonitor?channel=1&subtype=0"
print(f"📷 [MẶC ĐỊNH KHỞI ĐỘNG] Đã thiết lập nguồn camera IP: {current_video_source}")
video_speed_delay = 0.04  # Delay mặc định ban đầu cho tốc độ x1


UPLOAD_FOLDER = 'media'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- THÊM HÀM NÀY VÀO TRƯỚC @app.route('/upload') ---
def send_sms_simulation(phone_number, message):
    """Hàm gửi SMS giả lập qua Webhook kết hợp in Console của Tuấn"""
    print("\n================================================")
    print("📱 SMS CẢNH BÁO KHẨN CẤP")
    print(f"📞 Người nhận : {phone_number}")
    print(f"🕒 Thời gian  : {time.strftime('%H:%M:%S %d/%m/%Y')}")
    print(f"📩 Nội dung   : {message}")
    print("================================================\n")
    try:
        requests.post(
            "https://webhook.site/239cd0e6-cde7-4e22-9951-601ee61d6084",
            json={
                "phone": phone_number,
                "message": message,
                "time": time.strftime('%H:%M:%S %d/%m/%Y')
            },
            timeout=5
        )
        print(f"✅ Đã gửi webhook thành công cho số {phone_number}")
    except Exception as e:
        print(f"❌ Lỗi gửi webhook tới số {phone_number}: {e}")


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


def generate_frames():
    global is_streaming, current_video_source, video_speed_delay, thread_active
    
    thread_active = True
    cap = cv2.VideoCapture(current_video_source)
    if cap.isOpened():
    # Nếu đang đọc luồng mạng RTSP, ép bộ đệm lưu trữ về 1 khung hình duy nhất
        if isinstance(current_video_source, str) and "rtsp" in current_video_source:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)


    fire_frame_counter = 0
    FRAME_THRESHOLD = 15
    last_alert_time = 0
    ALERT_COOLDOWN = 20   

    
    while cap.isOpened():
        # Kiểm tra trạng thái streaming an toàn với Lock
        with data_lock:
            if not is_streaming:
                break

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
        

        is_fire_detected = False   
        is_smoke_detected = False  
        
        for box in results[0].boxes:
            class_id = int(box.cls[0])
            label = model.names[class_id].lower() # Chuyển về chữ thường để tránh sót nhãn 'Fire'/'fire'
            
            print(f"🔍 [YOLO DETECT] Tìm thấy nhãn: '{label}' với độ tự tin: {float(box.conf[0]):.2f}")
            if label == 'fire':
                is_fire_detected = True
                break  # Thấy lửa ưu tiên cao nhất, thoát vòng lặp luôn
            elif label == 'smoke':
                is_smoke_detected = True
                
        # --- LOGIC TÍNH TOÁN RISK LEVEL & ĐỊNH DẠNG KHẨN CẤP ---

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
        elif is_smoke_detected:
            # Nếu chỉ có khói, vẫn tăng hoặc giữ mức độ rủi ro tùy bạn chọn, 
            # ở đây giữ logic tăng counter nếu có khói, nhưng ưu tiên gọi tên khói
            fire_frame_counter = min(FRAME_THRESHOLD, fire_frame_counter + 1)
            detected_type = 'smoke'
        else:
            fire_frame_counter = max(0, fire_frame_counter - 1)

            detected_type = 'Bình thường'
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


        # 3. BẮN SỰ KIỆN 3: Kích hoạt thông báo lên kênh 'new_alert'
        if fire_frame_counter >= FRAME_THRESHOLD and (detected_type in ['fire', 'smoke']):

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
                alert_message = (
                    f"CẢNH BÁO HỎA HOẠN! "
                    f"Phát hiện {detected_type.upper()} tại khu dân cư "
                    f"lúc {time.strftime('%H:%M:%S %d/%m/%Y')}"
                )

                socketio.emit('new_alert', {
                    'type': detected_type,
                    'message': f"Cảnh báo nguy hiểm! Phát hiện đám {'LỬA' if detected_type == 'fire' else 'KHÓI'} lớn xuất hiện tại Khu dân cư!"
                })


                # SMS GIẢ LẬP (Đã hết lỗi nhờ có EMERGENCY_PHONES toàn cục)
                for phone in EMERGENCY_PHONES:
                    send_sms_simulation(phone, alert_message)

                # Gửi trạng thái SMS sang FE
                socketio.emit('sms_sent', {
                    'phones': EMERGENCY_PHONES,
                    'message': alert_message
                })

                print(f"🚨 [HỆ THỐNG] Đã bắn sự kiện 'new_alert' sang FE lúc: {time.strftime('%H:%M:%S')}")
                last_alert_time = current_time

        # Đọc thời gian delay an toàn từ Lock
        with data_lock:
            current_delay = video_speed_delay
            
        time.sleep(current_delay)

                
                alert_msg = f"🚨 [CẢNH BÁO NGUY HIỂM] Phát hiện {'LỬA' if detected_type == 'fire' else 'KHÓI'} tại khu vực camera giám sát vào lúc: {time.strftime('%H:%M:%S')}"
                string_now = time.strftime('%H:%M:%S - %d/%m/%Y')
                image_name = f"fire_{int(current_time)}.jpg"
                
                cv2.imwrite(image_name, frame)

                # Hàm xử lý chạy ngầm cảnh báo
                def send_async_alerts():
                    global gmail_service # Khai báo global giúp loại bỏ hoàn toàn lỗi NameError
                    
                    # 1. Gửi tin nhắn tới Messenger nhóm công việc
                    try:
                        send_messenger_alert_to_all(alert_msg)
                    except Exception as e:
                        print("❌ Lỗi luồng gửi Messenger:", e)
                    
                    # 2. Gửi email cảnh báo qua Gmail API kèm ảnh hiện trường vừa lưu
                    if gmail_service:
                        try:
                            send_gmail_alert_to_team(gmail_service, string_now, image_name)
                        except Exception as e:
                            print("❌ Lỗi luồng gọi hàm send_gmail_alert_to_team:", e)

                    try:
                        # Định dạng lại nội dung tin nhắn có dấu thời gian giống như commit của Tuấn
                        alert_message_sms = f"CẢNH BÁO HỎA HOẠN! Phát hiện {detected_type.upper()} tại khu dân cư lúc {time.strftime('%H:%M:%S %d/%m/%Y')}"
                        
                        # Duyệt gửi cho từng số điện thoại
                        for phone in EMERGENCY_PHONES:
                            send_sms_simulation(phone, alert_message_sms)
                        
                        # Bắn thông báo trạng thái SMS đã gửi về giao diện Front-End
                        socketio.emit('sms_sent', {
                            'phones': EMERGENCY_PHONES,
                            'message': alert_message_sms
                        })
                    except Exception as e:
                        print("❌ Lỗi luồng xử lý SMS giả lập:", e)

                    else:
                        print("⚠️ Dịch vụ Gmail chưa được cấu hình hoặc xác thực thành công.")

                # Kích hoạt tiểu luồng chạy nền (Giữ nguyên cấu trúc Thread cũ của bạn)
                alert_thread = threading.Thread(target=send_async_alerts)
                alert_thread.daemon = True
                alert_thread.start()



                # messenger_thread = threading.Thread(target=send_messenger_alert_to_all, args=(alert_msg,))
                # messenger_thread.daemon = True
                # messenger_thread.start()

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



def send_sms_simulation(phone_number, message):
    print("\n================================================")
    print("📱 SMS CẢNH BÁO KHẨN CẤP")
    print(f"📞 Người nhận : {phone_number}")
    print(f"🕒 Thời gian  : {time.strftime('%H:%M:%S %d/%m/%Y')}")
    print(f"📩 Nội dung   : {message}")
    print("================================================\n")

    try:
        requests.post(
            "https://webhook.site/239cd0e6-cde7-4e22-9951-601ee61d6084",
            json={
                "phone": phone_number,
                "message": message,
                "time": time.strftime('%H:%M:%S %d/%m/%Y')
            },
            timeout=5
        )
        print("✅ Đã gửi webhook thành công")
    except Exception as e:
        print(f"❌ Lỗi gửi webhook: {e}")


# @socketio.on('start_stream') 


@socketio.on('start_stream') 
def handle_start_stream(data=None): 
    global is_streaming, current_video_source, thread_active
    
    print(f"\n📥 [SOCKET] Nhận lệnh start_stream mới từ FE. Dữ liệu thô: {data}")

    # =================================================================
    # BƯỚC 1: RA LỆNH NGẮT TUYỆT ĐỐI LUỒNG CŨ ĐỂ GIẢI PHÓNG CAMERA/FILE VŨ
    # =================================================================
    if is_streaming or thread_active:
        print("🛑 [HỆ THỐNG] Phát hiện luồng cũ đang chạy. Tiến hành ngắt để giải phóng tài nguyên...")
        is_streaming = False  # Đánh dấu sai để vòng lặp while trong generate_frames dừng lại
        
        timeout_counter = 0
        # Đợi luồng cũ chạy hết block code và gọi lệnh cap.release() sạch sẽ
        while thread_active and timeout_counter < 30:  # Chờ tối đa 3 giây (30 * 0.1s)
            time.sleep(0.1)
            timeout_counter += 1
        print("✅ [HỆ THỐNG] Luồng cũ đã được giải phóng hoàn toàn.")

    # Mặc định liên kết Camera IP nhà bạn
    camera_rtsp = "rtsp://admin:L2E1EB60@192.168.1.120:554/cam/realmonitor?channel=1&subtype=0"

    # =================================================================
    # BƯỚC 2: PHÂN TÍCH VÀ ĐỊNH TUYẾN NGUỒN PHÁT MỚI TRÊN NỀN SẠCH
    # =================================================================
    if data and isinstance(data, dict):
        video_name = data.get('video_name')
        
        # Nếu Front-End truyền lên tên video và chuỗi đó không rỗng
        if video_name and str(video_name).strip() != "":
            custom_source = f"media/{video_name}"
            
            # Kiểm tra file video test có tồn tại thực tế hay không
            if os.path.exists(custom_source):
                current_video_source = custom_source
                print(f"📁 [CHẾ ĐỘ VIDEO] Đã chuyển nguồn sang file: {current_video_source} (Đã ngắt Cam)")
            else:
                # Nếu file không tồn tại, quay về Camera IP mặc định
                current_video_source = camera_rtsp
                print(f"⚠️ [CẢNH BÁO] Không tìm thấy file {custom_source}. Quay lại nguồn Cam IP.")
        else:
            # Nếu object rỗng {} (Do giao diện React gửi sang khi bấm chọn Camera)
            current_video_source = camera_rtsp
            print(f"📷 [CHẾ ĐỘ CAMERA] Bật Live Camera IP: {current_video_source}")
    else:

        current_video_source = "media/vid2.mp4" 
        
    print("📡 [TÍN HIỆU] Nhận lệnh khởi động luồng stream video từ FE.")
    
    # Dùng Lock để đổi trạng thái streaming an toàn
    with data_lock:
        if is_streaming:
            is_streaming = False
            time.sleep(0.3)  # Đợi luồng cũ giải phóng xong
        is_streaming = True
    
    # Khởi chạy luồng Thread chuẩn của Python
    thread = threading.Thread(target=generate_frames)
    thread.daemon = True  

        # Trường hợp data là None (Khi vừa tải trang xong)
        current_video_source = camera_rtsp
        print(f"📷 [MẶC ĐỊNH LÀM MỚI TÀI TRANG] Ép chạy Live Camera IP: {current_video_source}")

    # =================================================================
    # BƯỚC 3: KHỞI CHẠY LUỒNG AI MỚI VỚI NGUỒN ĐÃ ĐỔI
    # =================================================================
    is_streaming = True
    
    thread = threading.Thread(target=generate_frames)
    thread.daemon = True  # Tự hủy luồng khi server tắt hẳn
 
    thread.start()
    print("🚀 [HỆ THỐNG] Đã kích hoạt luồng AI xử lý nguồn mới thành công!")


@socketio.on('change_speed')
def handle_change_speed(data):
    global video_speed_delay
    if data and 'speed' in data:
        user_speed = float(data['speed'])
        with data_lock:
            video_speed_delay = 0.04 / user_speed
        print(f"⏱️ [CẤU HÌNH] Người dùng đổi tốc độ sang: {user_speed}x (Delay: {video_speed_delay}s)")


@socketio.on('disconnect')
def handle_disconnect():
    global is_streaming
    print("❌ [TÍN HIỆU] Front-End đã ngắt kết nối.")
    with data_lock:
        is_streaming = False


if __name__ == '__main__':
    print("=== Hệ thống giám sát hỏa hoạn khu dân cư đã sẵn sàng ===")
    print("📡 Đang mở cổng 5000 và đợi tín hiệu kết nối từ FE...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)