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

# Khởi tạo cấu hình Flask và Socket.IO (Bỏ async_mode='eventlet' để chạy ổn định trên Windows)
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Nạp mô hình YOLOv8 từ thư mục của bạn
MODEL_PATH = "models/best_final.pt"
model = YOLO(MODEL_PATH)

# Ép YOLO thực hiện fuse và compile mô hình ngay trên luồng chính để chống lỗi AttributeError: bn
if hasattr(model.model, 'fuse'):
    model.model.fuse()

is_streaming = False
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


def generate_frames():
    global is_streaming, current_video_source, video_speed_delay
    
    print(f"🎬 [AI RUN] Bắt đầu nhận diện trên nguồn: {current_video_source}")
    cap = cv2.VideoCapture(current_video_source)

    fire_frame_counter = 0
    FRAME_THRESHOLD = 25  
    last_alert_time = 0
    ALERT_COOLDOWN = 20   
    
    while is_streaming and cap.isOpened():
        success, frame = cap.read()
        if not success:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        results = model(frame, conf=0.45, verbose=False)
        annotated_frame = results[0].plot()
        
        # is_danger_detected = False
        is_fire_detected = False   # ĐÃ ĐỔI: Tập trung kiểm tra nhãn lửa
        is_smoke_detected = False  # Theo dõi thêm nhãn khói nếu cần
        detected_type = 'fire' 
        
        for box in results[0].boxes:
            class_id = int(box.cls[0])
            label = model.names[class_id]
            # if label in ['fire', 'smoke']:
            #     is_danger_detected = True
            #     detected_type = label 
            #     break
            print(f"🔍 [YOLO DETECT] Tìm thấy nhãn: '{label}' với độ tự tin: {float(box.conf[0]):.2f}")
            if label in ['fire', 'Fire']:
                is_fire_detected = True
                # detected_type = 'fire'
                break # Ưu tiên lửa cao nhất, thấy lửa là dừng vòng lặp để xử lý ngay
            elif label == 'smoke':
                is_smoke_detected = True
                # detected_type = 'smoke'
                
        if is_fire_detected:
            fire_frame_counter = min(FRAME_THRESHOLD, fire_frame_counter + 1)
            detected_type = 'fire'
        else:
            fire_frame_counter = max(0, fire_frame_counter - 1)
            if is_smoke_detected and fire_frame_counter == 0:
                detected_type = 'smoke'
        # fire_frame_counter = min(FRAME_THRESHOLD, fire_frame_counter + 1)

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
        if fire_frame_counter >= FRAME_THRESHOLD:
            current_time = time.time()
            if current_time - last_alert_time > ALERT_COOLDOWN:
                socketio.emit('new_alert', {
                    'type': detected_type,
                    'message': f"Cảnh báo nguy hiểm! Phát hiện đám {'LỬA' if detected_type == 'fire' else 'KHÓI'} lớn xuất hiện tại Khu dân cư!"
                })
                print(f"🚨 [HỆ THỐNG] Đã bắn sự kiện 'new_alert' sang FE lúc: {time.strftime('%H:%M:%S')}")
                last_alert_time = current_time

        # Sử dụng time.sleep chuẩn của Python, thời gian nghỉ thay đổi linh hoạt theo nút bấm tốc độ
        time.sleep(video_speed_delay)
        
    cap.release()
    print("🛑 [AI STOP] Đã giải phóng luồng xử lý video hiện tại.")


@socketio.on('connect')
def handle_connect():
    print("🚀 [TÍN HIỆU] Giao diện Front-End đã kết nối thành công!")


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
    
    if is_streaming:
        is_streaming = False
        time.sleep(0.3) 
        
    is_streaming = True
    
    # ĐÃ THAY THẾ: Sử dụng Thread chuẩn của Python thay thế cho eventlet.spawn
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