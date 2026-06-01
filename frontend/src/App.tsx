import { useState, useEffect } from 'react';
import { io, Socket } from 'socket.io-client';
import Header from './components/header';
import CameraFeed from './components/camera-feed';
import StatsCards from './components/stats-cards';
import AlertsPanel from './components/alerts-panel';
import { Alert } from './types';
import './App.css';

function App() {
  // 1. Khởi tạo mảng cảnh báo ban đầu (Bỏ qua dữ liệu fake để hứng dữ liệu thật từ Python sạch sẽ hơn)
  const [alerts, setAlerts] = useState<Alert[]>([]);

  // 2. State lưu trữ frame ảnh nhận từ mã hóa Base64 của Python
  const [videoFrame, setVideoFrame] = useState<string>('');

  // 3. BỔ SUNG STATE NHẬN MỨC ĐỘ RỦI RO (RISK LEVEL BUFFER) TỪ OPENCV NGẦM
  const [riskLevel, setRiskLevel] = useState<number>(0);

  useEffect(() => {
    // Khởi tạo socket bên trong useEffect để tránh lỗi SSR (Màn hình trắng Loading)
    const socketInstance: Socket = io('http://127.0.0.1:5000', {
      transports: ['websocket'],
      upgrade: false
    });

    socketInstance.on('connect', () => {
      printConnectLog();
      socketInstance.emit('start_stream'); // Kích hoạt luồng chạy bên Python
    });

    socketInstance.on('connect_error', (err) => {
      console.error(" [SOCKET] Lỗi kết nối đến cổng 5000:", err.message);
    });

    //  Lắng nghe EVENT 1: Luồng ảnh từ predict.py trả về từng frame
    socketInstance.on('video_frame', (data: { image: string }) => {
      setVideoFrame(`data:image/jpeg;base64,${data.image}`);
    });

    // Lắng nghe EVENT 2: Đồng bộ chỉ số tích lũy rủi ro (0 -> 25) để chạy Progress Bar
    socketInstance.on('risk_update', (data: { level: number }) => {
      setRiskLevel(data.level);
    });

    // Lắng nghe EVENT 3: Nhận thông báo hỏa hoạn chính thức khi bộ đệm đạt ngưỡng 25 frames
    socketInstance.on('new_alert', (data: { type: 'fire' | 'smoke'; message: string }) => {
      const newAlert: Alert = {
        id: Date.now().toString(),
        type: data.type,
        severity: data.type === 'fire' ? 'critical' : 'high',
        message: data.message,
        timestamp: new Date()
      };
      
      // Đẩy thông báo mới lên đầu danh sách, loại bỏ các tin cũ có nội dung thông điệp trùng lặp
      setAlerts(prev => [newAlert, ...prev.filter(a => a.message !== data.message)]);
    });

    // Hủy đăng ký lắng nghe và ngắt kết nối khi đóng component / tải lại trang
    return () => {
      socketInstance.off('connect');
      socketInstance.off('connect_error');
      socketInstance.off('video_frame');
      socketInstance.off('risk_update');
      socketInstance.off('new_alert');
      socketInstance.disconnect();
    };
  }, []);

  // Hàm hỗ trợ in log đẹp gọn gàng ngoài console trình duyệt
  const printConnectLog = () => {
    console.log("%c🔌 [SOCKET] Đã thiết lập bắt tay thành công tới Flask Server!", "color: #00ff00; font-weight: bold;");
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white selection:bg-red-600/30">
      {/* Header hệ thống */}
      <Header />

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex flex-col lg:flex-row gap-6">
          
          {/* CỘT TRÁI: HIỂN THỊ CAMERA FEED + THÔNG SỐ THỐNG KÊ */}
          <div className="flex-1 space-y-6">
            {/* Đã đồng bộ: Truyền thêm chỉ số tích lũy rủi ro ngầm vào component Camera */}
            <CameraFeed videoFrame={videoFrame} riskLevel={riskLevel} />
            
            <StatsCards alerts={alerts} />
          </div>

          {/* CỘT PHẢI: BẢNG LƯU TRỮ VÀ XỬ LÝ SỰ KIỆN KHẨN CẤP */}
          <div className="lg:w-[380px] w-full flex-shrink-0">
            <AlertsPanel alerts={alerts} setAlerts={setAlerts} />
          </div>

        </div>
      </main>
    </div>
  );
}

export default App;