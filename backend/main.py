import base64
import cv2
import time
import os  
import threading  
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


def generate_frames():
    global is_streaming, current_video_source, video_speed_delay
    
    print(f"🎬 [AI RUN] Bắt đầu nhận diện trên nguồn: {current_video_source}")
    cap = cv2.VideoCapture(current_video_source)

    fire_frame_counter = 0
    FRAME_THRESHOLD = 25  
    last_alert_time = 0
    ALERT_COOLDOWN = 20   
    
    while cap.isOpened():
        # Kiểm tra trạng thái streaming an toàn với Lock
        with data_lock:
            if not is_streaming:
                break

        success, frame = cap.read()
        if not success:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        results = model(frame, conf=0.45, verbose=False)
        annotated_frame = results[0].plot()
        
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

        # 1. BẮN SỰ KIỆN 1: Ảnh mã hóa Base64 về kênh 'video_frame'
        _, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        socketio.emit('video_frame', {'image': frame_base64}) 

        # 2. BẮN SỰ KIỆN 2: Cập nhật chỉ số rủi ro về kênh 'risk_update'
        risk_percentage = int((fire_frame_counter / FRAME_THRESHOLD) * 100)
        socketio.emit('risk_update', {
            'level': fire_frame_counter,       
            'percentage': risk_percentage      
        })

        # 3. BẮN SỰ KIỆN 3: Kích hoạt thông báo lên kênh 'new_alert'
        if fire_frame_counter >= FRAME_THRESHOLD and (detected_type in ['fire', 'smoke']):
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
        
    cap.release()
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


@socketio.on('start_stream') 
def handle_start_stream(data=None): 
    global is_streaming, current_video_source
    
    if data and 'video_name' in data:
        custom_source = f"media/{data['video_name']}"
        if os.path.exists(custom_source):
            current_video_source = custom_source
            print(f"📁 [CẤU HÌNH] Đã chuyển nguồn nhận diện sang file mới: {current_video_source}")
        else:
            print(f"⚠️ [CẢNH BÁO] Không tìm thấy file {custom_source}. Sử dụng nguồn mặc định.")
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
    thread.start()


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