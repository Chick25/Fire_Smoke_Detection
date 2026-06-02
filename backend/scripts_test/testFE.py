import cv2
import time
import base64
import threading
from flask import Flask
from flask_socketio import SocketIO
from ultralytics import YOLO

# 1. Khởi tạo cấu trúc Flask & SocketIO với cấu hình CORS mở rộng cho phép Frontend kết nối chéo
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 2. Tải mô hình YOLOv8 của bạn
MODEL_PATH = "fire_smoke_model/best.pt"
model = YOLO(MODEL_PATH)

# Biến cờ (Flag) toàn cục để kiểm soát luồng xử lý AI, chống spam luồng khi React F5 trang
is_thread_running = False

def run_video_processing():
    """
    Luồng xử lý AI độc lập chạy ngầm: Đọc video, đẩy YOLO phân tích và truyền phát dữ liệu.
    """
    global is_thread_running
    VIDEO_PATH = "vid2.mp4" 
    cap = cv2.VideoCapture(VIDEO_PATH)

    # Các tham số cấu hình logic chống nhiễu
    fire_frame_counter = 0
    FRAME_THRESHOLD = 25  # Ngưỡng tích lũy (25 frames ~ 1 giây video)
    last_alert_time = 0
    ALERT_COOLDOWN = 15   # Giới hạn khoảng cách phát log cảnh báo (15 giây)

    print(f"=== [AI SYSTEM] Bắt đầu luồng xử lý Video: {VIDEO_PATH} ===")

    while cap.isOpened():
        success, frame = cap.read()
        
        # Nếu chạy hết video, tự động tua lại từ đầu để hệ thống tiếp tục test liên tục
        if not success:
            print("🔄 [AI SYSTEM] Đã chạy hết video. Tự động tua lại từ đầu...")
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        # Dự đoán vật thể bằng YOLOv8 (conf=0.45 để cân bằng độ nhạy)
        results = model(frame, conf=0.45, verbose=False)
        
        # Vẽ các khung nhận diện (Bounding Boxes) lên khung hình
        annotated_frame = results[0].plot()
        
        is_danger_detected = False
        current_type = 'warning'
        
        # Duyệt qua các vật thể quét được để tìm nhãn hỏa hoạn
        for box in results[0].boxes:
            class_id = int(box.cls[0])
            label = model.names[class_id]
            if label in ['fire', 'smoke']:
                is_danger_detected = True
                current_type = label
                break 
                
        # Thuật toán bộ đệm rủi ro (Risk Level Buffer)
        if is_danger_detected:
            fire_frame_counter = min(FRAME_THRESHOLD, fire_frame_counter + 1)
        else:
            fire_frame_counter = max(0, fire_frame_counter - 1)

        # 📊 [EVENT 1]: Bắn mức độ rủi ro (Risk Level) thời gian thực về React Web để chạy Progress Bar
        socketio.emit('risk_update', {'level': fire_frame_counter})

        # Khi mức độ rủi ro chạm hoặc vượt ngưỡng thiết lập
        if fire_frame_counter >= FRAME_THRESHOLD:
            current_time = time.time()
            
            # Vẽ chữ cảnh báo màu đỏ trực tiếp đè lên luồng video stream
            cv2.putText(annotated_frame, "!!! EMERGENCY: FIRE / SMOKE DETECTED !!!", (20, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)
            
            # 🚨 [EVENT 2]: Bắn tin nhắn cảnh báo chính thức lên thanh Sidebar (Có cooldown chống spam tin)
            if current_time - last_alert_time > ALERT_COOLDOWN:
                print(f"🚨 [CẢNH BÁO HOẢ HOẠN] Phát hiện {current_type.upper()} lúc: {time.strftime('%H:%M:%S')}")
                socketio.emit('new_alert', {
                    'type': current_type,
                    'message': f'Phát hiện dấu hiệu hỏa hoạn ({current_type.upper()}) tại khu vực camera chính!'
                })
                last_alert_time = current_time

        # Ghi đè trạng thái Risk level hiện tại lên góc ảnh
        cv2.putText(annotated_frame, f"Risk Level: {fire_frame_counter}/{FRAME_THRESHOLD}", (20, 90), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # 🖼️ [EVENT 3]: Mã hóa ảnh JPG thành dạng chuỗi chuỗi ký tự Base64 để truyền đi qua SocketIO
        _, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        socketio.emit('video_frame', {'image': frame_base64})

        # Giữ nhịp độ luồng tương đương khoảng ~30 FPS, tiết kiệm băng thông mạng
        socketio.sleep(0.03)

    cap.release()
    print("=== [AI SYSTEM] Đã đóng luồng xử lý video ===")
    is_thread_running = False


# 3. Lắng nghe sự kiện bắt tay từ phía React Frontend gửi sang
@socketio.on('start_stream')
def handle_stream():
    global is_thread_running
    
    # Nếu luồng AI đang chạy từ trước rồi, không cho phép tạo thêm luồng mới gây quá tải CPU
    if is_thread_running:
        print("[SOCKET] Tín hiệu kích hoạt gửi lại, luồng AI đã chạy từ trước. Bỏ qua!")
        return

    print("[SOCKET] Nhận lệnh 'start_stream' thành công! Khởi chạy luồng AI xử lý riêng biệt...")
    is_thread_running = True
    
    # Tạo Thread riêng biệt chạy ngầm để không làm nghẽn cổng kết nối mạng chính của Flask
    video_thread = threading.Thread(target=run_video_processing)
    video_thread.daemon = True
    video_thread.start()


# 4. Kích hoạt Server chạy ở port 5000 cục bộ
if __name__ == '__main__':
    print("Khởi động Server Flask-SocketIO thành công tại địa chỉ http://127.0.0.1:5000")
    socketio.run(app, host='127.0.0.1', port=5000, debug=True, use_reloader=False)