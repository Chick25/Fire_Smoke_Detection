'use client';

import { useState, useEffect } from 'react';
import { io, Socket } from 'socket.io-client';

interface Alert {
  id: string;
  type: 'fire' | 'smoke' | 'warning';
  severity: 'critical' | 'high' | 'medium';
  message: string;
  timestamp: Date;
}

export default function DashboardPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [videoFrame, setVideoFrame] = useState<string>('');
  const [riskLevel, setRiskLevel] = useState<number>(0); 

  useEffect(() => {
    // Khởi tạo Socket Client kết nối đến Flask port 5000
    const socketInstance: Socket = io('http://127.0.0.1:5000', {
      transports: ['websocket'],
      upgrade: false
    });

    socketInstance.on('connect', () => {
      console.log(" Đã kết nối thời gian thực đến Python Backend thành công!");
      socketInstance.emit('start_stream'); // Kích hoạt Python chạy luồng AI
    });

    //  LẮNG NGHE EVENT 1: Nhận mức độ rủi ro (Risk Level) từ Python từng khung hình một
    socketInstance.on('risk_update', (data: { level: number }) => {
      setRiskLevel(data.level);
    });

    //  LẮNG NGHE EVENT 2: Nhận luồng ảnh Base64 hiển thị lên thẻ <img>
    socketInstance.on('video_frame', (data: { image: string }) => {
      setVideoFrame(`data:image/jpeg;base64,${data.image}`);
    });

    //  LẮNG NGHE EVENT 3: Nhận thông tin thông báo hỏa hoạn chính thức
    socketInstance.on('new_alert', (data: { type: 'fire' | 'smoke'; message: string }) => {
      const newAlert: Alert = {
        id: Date.now().toString(),
        type: data.type,
        severity: data.type === 'fire' ? 'critical' : 'high',
        message: data.message,
        timestamp: new Date()
      };
      
      setAlerts(prev => [newAlert, ...prev.filter(a => a.message !== data.message)]);
    });

    return () => {
      socketInstance.disconnect(); 
    };
  }, []);

  return (
    <div className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-7xl mx-auto flex flex-col lg:flex-row gap-6">
        
        {/* KHU VỰC CAMERA HIỂN THỊ DỮ LIỆU THỜI GIAN THỰC */}
        <div className="flex-1 bg-gray-900 border border-gray-800 rounded-2xl p-4 space-y-4">
          <div className="relative aspect-video w-full bg-black rounded-xl overflow-hidden flex items-center justify-center">
            {videoFrame ? (
              <img src={videoFrame} alt="Live Stream" className="w-full h-full object-contain" />
            ) : (
              <p className="text-gray-500 animate-pulse">Waiting for real-time video stream...</p>
            )}
          </div>

          {/* THANH TIẾN TRÌNH RỦI RO ĐỒNG BỘ TRỰC TIẾP TỪ PYTHON (EVENT 1) */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs font-mono text-gray-400">
              <span>Độ tích lũy rủi ro AI (Chống báo giả):</span>
              <span className={riskLevel >= 25 ? "text-red-500 font-bold" : "text-yellow-500"}>
                {riskLevel}/25 Frames
              </span>
            </div>
            <div className="w-full bg-gray-950 h-2 rounded-full overflow-hidden border border-gray-800">
              <div 
                style={{ width: `${(riskLevel / 25) * 100}%` }}
                className={`h-full transition-all duration-75 bg-gradient-to-r ${
                  riskLevel >= 25 ? 'from-orange-500 to-red-600' : 'from-yellow-400 to-orange-500'
                }`}
              />
            </div>
          </div>
        </div>

        {/* SIDEBAR BẢNG SỰ KIỆN NHẬN CẢNH BÁO CHÍNH THỨC (EVENT 3) */}
        <div className="w-full lg:w-96 bg-gray-900 border border-gray-800 rounded-2xl p-4">
          <h3 className="font-bold text-lg border-b border-gray-800 pb-3 mb-3">Thông báo khẩn cấp</h3>
          <div className="space-y-3 max-h-[450px] overflow-y-auto">
            {alerts.length === 0 ? (
              <p className="text-gray-600 text-sm text-center py-8">Hệ thống đang quét... Trạng thái an toàn.</p>
            ) : (
              alerts.map(alert => (
                <div key={alert.id} className={`p-3 rounded-xl border bg-gray-950/40 ${
                  alert.severity === 'critical' ? 'border-red-600/40 text-red-200' : 'border-orange-600/40 text-orange-200'
                }`}>
                  <div className="flex justify-between text-[10px] uppercase font-bold mb-1">
                    <span className={alert.severity === 'critical' ? 'text-red-500' : 'text-orange-500'}>
                      {alert.severity}
                    </span>
                    <span className="text-gray-500">{alert.type}</span>
                  </div>
                  <p className="text-sm font-semibold text-white">{alert.message}</p>
                </div>
              ))
            )}
          </div>
        </div>

      </div>
    </div>
  );
}