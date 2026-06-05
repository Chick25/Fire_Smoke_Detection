# share_cam.py
import cv2
from flask import Flask, Response

app = Flask(__name__)
# 0 là Webcam, nếu dùng Camera IP thì thay bằng đường dẫn 'rtsp://...'
camera = "rtsp://admin:L2E1EB60@192.168.1.120:554/cam/realmonitor?channel=1&subtype=0" 

def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            # Nén ảnh thành định dạng JPG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            # Cấu hình luồng phản hồi theo chuẩn multipart của HTTP stream
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # Chạy ở cổng 8080
    app.run(host='0.0.0.0', port=8080, threaded=True)