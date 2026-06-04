import base64
import cv2
import time
import eventlet
from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS
from ultralytics import YOLO

# Khởi tạo cấu hình Flask và Socket.IO
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Nạp mô hình YOLOv8 từ thư mục của bạn
MODEL_PATH = "models/best_final.pt"
model = YOLO(MODEL_PATH)

is_streaming = False

def generate_frames():
    global is_streaming
    
    # Sử dụng file video demo trong folder media
    VIDEO_SOURCE = "media/vid2.mp4"
    cap = cv2.VideoCapture(VIDEO_SOURCE)

    # Khởi tạo thuật toán bộ đệm chống báo động giả theo chuẩn FE (0 -> 25)
    fire_frame_counter = 0
    FRAME_THRESHOLD = 25  # Đồng bộ với FE là 25 frames
    last_alert_time = 0
    ALERT_COOLDOWN = 20   
    
    while is_streaming and cap.isOpened():
        success, frame = cap.read()
        if not success:
            # Tự động lặp lại video khi chạy hết file demo
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        # Dự đoán vật thể (Giữ nguyên conf=0.45 xịn mịn của bạn)
        results = model(frame, conf=0.45, verbose=False)
        
        # Lấy khung hình đã vẽ sẵn bounding box từ kết quả của YOLO
        annotated_frame = results[0].plot()
        
        is_danger_detected = False
        detected_type = 'fire' # Mặc định nhãn nguy hiểm
        
        # Duyệt qua các object quét được
        for box in results[0].boxes:
            class_id = int(box.cls[0])
            label = model.names[class_id]
            
            if label in ['fire', 'smoke']:
                is_danger_detected = True
                detected_type = label # 'fire' hoặc 'smoke'
                break
                
        # Thuật toán tính toán mức độ rủi ro (Risk Level Buffer)
        if is_danger_detected:
            fire_frame_counter = min(FRAME_THRESHOLD, fire_frame_counter + 1)
        else:
            fire_frame_counter = max(0, fire_frame_counter - 1)

        # 1. BẮN SỰ KIỆN 1: Luồng ảnh mã hóa Base64 về kênh 'video_frame'
        _, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        socketio.emit('video_frame', {'image': frame_base64}) # Khớp với data: { image: string } bên FE

        # 2. BẮN SỰ KIỆN 2: Cập nhật chỉ số rủi ro về kênh 'risk_update' để chạy Progress Bar
        socketio.emit('risk_update', {'level': fire_frame_counter})

        # 3. BẮN SỰ KIỆN 3: Kích hoạt thông báo chính thức lên kênh 'new_alert'
        if fire_frame_counter >= FRAME_THRESHOLD:
            current_time = time.time()
            if current_time - last_alert_time > ALERT_COOLDOWN:
                # Gửi gói tin thông báo hỏa hoạn chuẩn cấu hình FE nhận
                socketio.emit('new_alert', {
                    'type': detected_type,
                    'message': f"Cảnh báo nguy hiểm! Phát hiện đám {'LỬA' if detected_type == 'fire' else 'KHÓI'} lớn xuất hiện tại Khu dân cư!"
                })
                print(f"🚨 [HỆ THỐNG] Đã bắn sự kiện 'new_alert' sang FE lúc: {time.strftime('%H:%M:%S')}")
                last_alert_time = current_time

        # Giữ tốc độ stream mượt mà ~25 FPS tránh lag nghẽn băng thông mạng
        eventlet.sleep(0.04)
        
    cap.release()

# Lắng nghe sự kiện bắt tay và kích hoạt luồng từ Front-End
@socketio.on('connect')
def handle_connect():
    print("🚀 [TÍN HIỆU] Giao diện Front-End đã kết nối thành công!")

@socketio.on('start_stream') # Khớp với dòng socketInstance.emit('start_stream') bên FE
def handle_start_stream():
    global is_streaming
    print("📡 [TÍN HIỆU] Nhận lệnh khởi động luồng stream video từ FE.")
    if not is_streaming:
        is_streaming = True
        eventlet.spawn(generate_frames)

@socketio.on('disconnect')
def handle_disconnect():
    global is_streaming
    print("❌ [TÍN HIỆU] Front-End đã ngắt kết nối.")
    is_streaming = False

if __name__ == '__main__':
    print("=== Hệ thống giám sát hỏa hoạn khu dân cư đã sẵn sàng ===")
    print("📡 Đang mở cổng 5000 và đợi tín hiệu kết nối từ FE...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)