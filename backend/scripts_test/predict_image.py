import cv2
from ultralytics import YOLO

# 1. Đường dẫn tới file trọng số tốt nhất
MODEL_PATH = "fire_smoke_model/best.pt"
model = YOLO(MODEL_PATH)

# 2. Đường dẫn tới bức ảnh tĩnh bạn muốn kiểm tra (thay tên file ảnh thực tế của bạn vào)
IMAGE_PATH = "pic1.jpg"

# 3. Đọc ảnh bằng thư viện OpenCV
frame = cv2.imread(IMAGE_PATH)

if frame is None:
    print(f"❌ Lỗi: Không thể tìm thấy hoặc đọc được file ảnh tại đường dẫn: {IMAGE_PATH}")
else:
    print(f"=== Đang quét và phân tích bức ảnh: {IMAGE_PATH} ===")
    
    # 4. Dự đoán bằng mô hình YOLO (Đặt ngưỡng conf = 0.45)
    results = model(frame, conf=0.45, verbose=False)
    
    # Vẽ các khung bounding box và nhãn lên ảnh
    annotated_frame = results[0].plot()
    
    has_fire_or_smoke = False
    
    # Kiểm tra danh sách vật thể quét được trong ảnh
    for box in results[0].boxes:
        label = model.names[int(box.cls[0])]
        if label in ['fire', 'smoke']:
            has_fire_or_smoke = True
            break
            
    # 5. In kết quả phân tích ra Terminal và vẽ chữ thông báo lên màn hình ảnh
    if has_fire_or_smoke:
        print("🚨 KẾT QUẢ PHÂN TÍCH: PHÁT HIỆN DẤU HIỆU HỎA HOẠN TRONG ẢNH!")
        cv2.putText(annotated_frame, "DANGER: FIRE/SMOKE DETECTED!", (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    else:
        print("✅ KẾT QUẢ PHÂN TÍCH: Khu vực an toàn - Không phát hiện hỏa hoạn.")
        cv2.putText(annotated_frame, "SAFE: NO HAZARD", (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # 6. Hiển thị cửa sổ giao diện ảnh kết quả
    cv2.imshow("Image Test - Fire Detection Result", annotated_frame)
    
    print("\n[INFO] Đang hiển thị ảnh. Bấm một phím bất kỳ trên bàn phím để thoát hoàn toàn...")
    cv2.waitKey(0)  # Truyền số 0 để cửa sổ ảnh đứng im chờ người dùng bấm nút mới tắt
    cv2.destroyAllWindows()