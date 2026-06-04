import os
import cv2
import time
import requests  # Thư viện để gọi API gửi tin nhắn sang Facebook Messenger
from ultralytics import YOLO

# =====================================================================
# CẤU HÌNH THÔNG TIN KẾT NỐI FACEBOOK MESSENGER (NHIỀU NGƯỜI DÙNG)
# =====================================================================
# 1. Dán mã Token lấy từ nút "Tạo" màu xám ở trang cấu hình Facebook Developers vào đây
PAGE_ACCESS_TOKEN = "EAAOOBY49IP0BRn7rSMnP6FDkinxZChUm5ufSfXjjK5miagO43ddSfQIBgfYjN6ZCc4suYSW2EPf3GaRGZBhZCLsQQHkX7HOn6wTz0UZBiINi3WEIHKgrviFUmyfkil6QHTbT39VDFEMQ2OUVrp92CbaByDlsFmramTV88tKxEfJWXbMAsfPQUwo9GsZAxbfOrbmfAEBAZDZD"

# 2. Danh sách các mã số định danh USER_PSID thu được từ file get_id.py
# Bạn có thể thêm bao nhiêu ID tùy ý (ID của bạn, Hân, Nguyệt, Lam, Thắng, Oanh...), ngăn cách bằng dấu phẩy
LIST_USER_PSID = [
    "36106495948995752",
    "27028300910159101"
]

def send_messenger_alert_to_all(message_text):
    """Hàm duyệt qua danh sách LIST_USER_PSID để tự động bắn tin nhắn về từng máy"""
    url = f"https://graph.facebook.com/v21.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    
    print(f"\n🚀 [Hệ thống] Bắt đầu kích hoạt tiến trình gửi thông báo đến {len(LIST_USER_PSID)} người dùng...")
    
    for psid in LIST_USER_PSID:
        payload = {
            "recipient": {"id": psid},
            "message": {"text": message_text}
        }
        try:
            response = requests.post(url, json=payload)
            res_data = response.json()
            if response.status_code == 200:
                print(f"  ✅ [Messenger] Gửi thành công đến thành viên có ID: {psid}")
            else:
                print(f"  ❌ [Messenger Lỗi API] ID {psid} thất bại: {res_data.get('error', {}).get('message')}")
        except Exception as e:
            print(f"  ❌ Khuyết tật kết nối mạng khi gửi đến ID {psid}: {e}")

# =====================================================================
# KHIỂN TRÌNH KHỞI CHẠY MÔ HÌNH AI & KIỂM TRA VIDEO ĐẦU VÀO
# =====================================================================
MODEL_PATH = "fire_smoke_model/best.pt"
VIDEO_PATH = "vid2.mp4" 

print("\n=== HỆ THỐNG GIÁM SÁT HỎA HOẠN KHU DÂN CƯ ===")
print(f"🔄 [Hệ thống] Đang kiểm tra file video: {VIDEO_PATH}")

# Kiểm tra file trên ổ đĩa trước khi gọi OpenCV để tránh lỗi ngầm
if not os.path.exists(VIDEO_PATH):
    print(f"❌ LỖI KHẨN CẤP: Không tìm thấy file tên là '{VIDEO_PATH}' trong thư mục này!")
    print(f"📂 Các file hiện đang có trong thư mục của bạn gồm: {os.listdir('.')}")
    print("-> Hãy copy file video bỏ chung vào cùng thư mục chứa file code Python này nhé!")
else:
    print("✅ Đã tìm thấy file video trên ổ đĩa. Đang nạp vào OpenCV...")

# Nạp mô hình YOLOv8 và luồng đọc video
model = YOLO(MODEL_PATH)
cap = cv2.VideoCapture(VIDEO_PATH)

# Kiểm tra tính toàn vẹn xem OpenCV có mở được video không
if not cap.isOpened():
    print("❌ LỖI KHẨN CẤP: OpenCV không thể mở được file video này. File có thể bị lỗi định dạng hoặc trống.")
else:
    print("✅ NẠP VIDEO THÀNH CÔNG! Bắt đầu chạy vòng lặp xử lý AI...")

# ---------------------------------------------------------------------
# CÁC THAM SỐ CẤU HÌNH BỘ ĐỆM LOGIC CHỐNG NHIỄU VÀ COOLDOWN
# ---------------------------------------------------------------------
fire_frame_counter = 0
FRAME_THRESHOLD = 25  # Phải phát hiện khói/lửa liên tục 25 frames (~1 giây) mới kích hoạt trạng thái nguy hiểm
last_alert_time = 0
ALERT_COOLDOWN = 15   # Khoảng cách tối thiểu giữa các lần nhắn tin là 15 giây để tránh spam mạng

print("\n🎥 Luồng video đang chạy. Nhấn phím 'q' tại cửa sổ video để thoát sớm...")

while cap.isOpened():
    success, frame = cap.read()
    
    # Nếu không đọc được frame tiếp theo (hết video hoặc lỗi luồng) thì thoát vòng lặp an toàn
    if not success:
        print("\n🏁 Đã chạy hết video hoặc luồng video bị ngắt.")
        break

    # Dự đoán vật thể bằng mô hình YOLOv8 (conf=0.45 để cân bằng độ nhạy và chống bắt nhầm)
    results = model(frame, conf=0.45, verbose=False)
    
    # Vẽ các bounding box nhận diện (Lửa/Khói) lên khung hình video hiện tại
    annotated_frame = results[0].plot()
    
    is_danger_detected = False
    
    # Duyệt qua các vật thể quét được để kiểm tra nhãn lớp (label)
    for box in results[0].boxes:
        class_id = int(box.cls[0])
        label = model.names[class_id]
        
        # Nếu frame hiện tại bắt được nhãn lửa (fire) hoặc khói (smoke)
        if label in ['fire', 'smoke']:
            is_danger_detected = True
            break 
            
    # Thuật toán bộ đệm tích lũy nguy cơ (Buffer Risk Level) bảo vệ hệ thống tránh báo động sai
    if is_danger_detected:
        fire_frame_counter += 1
    else:
        fire_frame_counter = max(0, fire_frame_counter - 1)

    # Khi mức độ rủi ro vượt ngưỡng thiết lập (Xác định đám cháy bùng phát ổn định)
    if fire_frame_counter >= FRAME_THRESHOLD:
        current_time = time.time()
        
        # Vẽ dòng chữ cảnh báo nguy hiểm màu đỏ chớp nháy đè trực tiếp lên giao diện video
        cv2.putText(annotated_frame, "!!! EMERGENCY: FIRE / SMOKE DETECTED !!!", (20, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)
        
        # Kiểm tra thời gian hồi (Cooldown) để tiến hành kích hoạt API gửi tin nhắn
        if current_time - last_alert_time > ALERT_COOLDOWN:
            alert_msg = f"🚨 [CẢNH BÁO HOẢ HOẠN] Hệ thống phát hiện dấu hiệu CHÁY/KHÓI trong video thử nghiệm lúc: {time.strftime('%H:%M:%S')}!"
            print(f"\n{alert_msg}")
            
            # GỌI HÀM BẮN TIN NHẮN ĐỒNG LOẠT SANG MESSENGER
            send_messenger_alert_to_all(alert_msg)
            
            last_alert_time = current_time

    # Hiển thị thanh trạng thái mức độ rủi ro tích lũy hiện tại lên màn hình video
    cv2.putText(annotated_frame, f"Risk Level: {fire_frame_counter}/{FRAME_THRESHOLD}", (20, 90), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    # Hiển thị cửa sổ đồ họa luồng video kết quả lên màn hình Windows
    cv2.imshow("Video Test - Fire Monitoring System", annotated_frame)

    # Lắng nghe phím bấm từ hệ điều hành (Sửa đổi giúp cửa sổ không bị tắt ngầm)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        print("\n👋 Đã chủ động ngắt chương trình bằng phím 'q'.")
        break
    
    # Tạo độ trễ siêu nhỏ để CPU/GPU xử lý frame mượt mà
    time.sleep(0.01)

# Giải phóng bộ nhớ của camera/video và đóng các cửa sổ đồ họa Windows
cap.release()
cv2.destroyAllWindows()
print("=== HỆ THỐNG ĐÃ ĐÓNG HOÀN TOÀN AN TOÀN ===")