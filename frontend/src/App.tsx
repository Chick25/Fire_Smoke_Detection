import React, { useEffect, useState } from 'react';
import { io, Socket } from 'socket.io-client';
import './App.css';

interface AlertItem {
  id: string;
  time: string;
  type: 'fire' | 'smoke' | 'warning';
  message: string;
}

interface HistoryCaseItem {
  caseId: number;
  resolvedAt: string;
  logs: AlertItem[];
}

const socket: Socket = io('http://127.0.0.1:5000', {
  transports: ['polling', 'websocket'],
  upgrade: true,
  reconnection: true,
  reconnectionAttempts: 10,
  timeout: 15000,
});

function App() {
  const [imageSrc, setImageSrc] = useState<string>('');
  const [riskLevel, setRiskLevel] = useState<number>(0);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [systemStatus, setSystemStatus] = useState<'safe' | 'danger'>('safe');
  const [caseCount, setCaseCount] = useState<number>(0);
  const [caseHistory, setCaseHistory] = useState<HistoryCaseItem[]>([]);

  const [activeTab, setActiveTab] = useState<'camera' | 'video'>('camera');
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadedVideoName, setUploadedVideoName] = useState<string>('');
  const [isConnected, setIsConnected] = useState<boolean>(false);

  const [analysis, setAnalysis] = useState({
    fireArea: 0,
    smokeArea: 0,
    fireGrowth: 0,
    smokeGrowth: 0,
    duration: 0,
    intensity: 0,
    fsi: 0,
    risk: 'SAFE'
  });


  const resetStreamData = () => {
    setImageSrc('');
    setRiskLevel(0);
    setAlerts([]);
    setSystemStatus('safe');
  };
  useEffect(() => {
    // Theo dõi kết nối
    socket.on('connect', () => {
      console.log('✅ Socket Connected!');
      setIsConnected(true);
      socket.emit('start_stream'); // Khởi động mặc định
    });

    socket.on('disconnect', () => {
      console.log('❌ Socket Disconnected!');
      setIsConnected(false);
    });

    socket.on('connect_error', (err) => {
      console.error('❌ Socket Error:', err.message);
      setIsConnected(false);
    });

    socket.on('risk_update', (data: { level: number }) => {
      setRiskLevel(data.level);
      setSystemStatus(data.level >= 15 ? 'danger' : 'safe');
    });

    socket.on(
      "analysis_update",
      (data) => {
        console.log("📥 RECEIVED analysis_update:", data);

        setAnalysis(data);
      }
    );

    socket.on('video_frame', (data: { image: string }) => {
      setImageSrc(`data:image/jpeg;base64,${data.image}`);
    });

    socket.on('new_alert', (data: { type: 'fire' | 'smoke'; message: string }) => {
      const now = new Date();
      const newAlert: AlertItem = {
        id: now.getTime().toString() + Math.random().toString(36).substr(2, 5),
        time: now.toLocaleTimeString('vi-VN'),
        type: data.type,
        message: data.message,
      };

      setAlerts((prev) => {
        const updatedAlerts = [newAlert, ...prev];

        setCaseCount((current) => {
          if (current === 0 || prev.length === 0) return current + 1;
          const timeParts = prev[0].time.split(':');
          const lastAlertTime = new Date();
          lastAlertTime.setHours(
            parseInt(timeParts[0], 10),
            parseInt(timeParts[1], 10),
            parseInt(timeParts[2], 10)
          );
          const diffMinutes = (now.getTime() - lastAlertTime.getTime()) / 1000 / 60;
          return diffMinutes > 2 ? current + 1 : current;
        });

        return updatedAlerts;
      });
    });

    return () => {
      socket.off('connect');
      socket.off('disconnect');
      socket.off('connect_error');
      socket.off('risk_update');
      socket.off('video_frame');
      socket.off('new_alert');
      socket.off('analysis_update');
    };
  }, []);

  const switchStreamSource = (type: 'camera' | 'video', videoName?: string) => {
    setActiveTab(type);
    resetStreamData();

    if (type === 'camera') {
      setUploadedVideoName('');
      socket.emit('start_stream');
    } else if (type === 'video' && videoName) {
      setUploadedVideoName(videoName);
      socket.emit('start_stream', { video_name: videoName });
    }
  };

  const handleResolveCase = () => {
    if (alerts.length === 0) return;

    const newHistoryItem: HistoryCaseItem = {
      caseId: caseCount,
      resolvedAt: new Date().toLocaleTimeString('vi-VN'),
      logs: [...alerts],
    };

    setCaseHistory(prev => [newHistoryItem, ...prev]);
    setAlerts([]);
    setSystemStatus('safe');
  };

  const handleVideoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setImageSrc('');

    console.log(`📤 Đang upload file: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`);

    const formData = new FormData();
    formData.append('video_file', file);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // Timeout 30 giây

      const response = await fetch('http://127.0.0.1:5000/upload', {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      console.log(`📥 Response status: ${response.status}`);

      const data = await response.json();

      if (response.ok) {
        console.log("✅ Upload thành công:", data);
        switchStreamSource('video', data.filename);
      } else {
        alert(`Lỗi server: ${data.error || 'Không rõ'}`);
      }
    } catch (error: any) {
      if (error.name === 'AbortError') {
        alert('⏱️ Upload bị timeout (quá 30 giây)');
      } else {
        console.error("❌ Upload error:", error);
        alert('Không thể kết nối đến server. Kiểm tra backend có đang chạy không?');
      }
    } finally {
      setIsUploading(false);
    }
  };


  return (
    <div className="min-h-screen bg-neutral-950 text-white font-sans antialiased selection:bg-red-600/30 pb-12">
      
      {/* 1. THANH BANNER TRÊN CÙNG */}
      <header className={`border-b px-6 py-4 flex flex-col md:flex-row justify-between items-center gap-4 transition-colors duration-500 ${
        systemStatus === 'danger' ? 'bg-red-950/80 border-red-700 animate-pulse' : 'bg-neutral-900 border-neutral-850'
      }`}>
        <div className="flex items-center gap-3">
          <div className={`p-2.5 rounded-lg ${systemStatus === 'danger' ? 'bg-red-600 text-white' : 'bg-orange-600 text-white'}`}>
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-6 h-6">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.362 5.214A8.252 8.252 0 0 1 12 21 8.25 8.25 0 0 1 6.038 7.047 8.287 8.287 0 0 0 9 9.601a8.983 8.983 0 0 1 3.361-6.867 8.21 8.21 0 0 0 3 2.48Z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 18a3.75 3.75 0 0 0 .495-7.467 5.99 5.99 0 0 0-1.925 3.546 5.974 5.974 0 0 1-2.133-1A3.75 3.75 0 0 0 12 18Z" />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-black tracking-wider text-neutral-100 uppercase">
              NHẬN DIỆN ĐÁM CHÁY REALTIME
            </h1>
            <p className="text-xs text-neutral-400">Hệ thống phân tích hình ảnh AI giám sát rủi ro hoả hoạn</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right hidden sm:block">
            <span className="text-xs block text-neutral-400">Thời gian hệ thống</span>
            <span className="text-sm font-mono text-neutral-200">{new Date().toLocaleDateString('vi-VN')}</span>
          </div>
          <div className={`px-4 py-2 rounded-full border font-bold text-xs uppercase tracking-widest flex items-center gap-2 ${
            systemStatus === 'danger' 
              ? 'bg-red-600 border-red-500 text-white animate-bounce' 
              : 'bg-emerald-950/60 border-emerald-500/50 text-emerald-400'
          }`}>
            <span className={`w-2 h-2 rounded-full ${systemStatus === 'danger' ? 'bg-white animate-ping' : 'bg-emerald-400'}`}></span>
            {systemStatus === 'danger' ? '⚠️ NGUY HIỂM: CÓ CHÁY/KHÓI' : '✅ HỆ THỐNG AN TOÀN'}
          </div>
        </div>
      </header>

      {/* 2. BỐ CỤC CHÍNH */}
      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        
        {/* WIDGETS THỐNG KÊ */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4 flex justify-between items-center">
            <div>
              <span className="text-xs text-neutral-400 block uppercase font-semibold">Thiết bị giám sát</span>
              <span className="text-lg font-bold text-neutral-200">CAMERA_01 (Khu Vực Chính)</span>
            </div>
            <span className="text-xs text-emerald-400 bg-emerald-950/50 px-2 py-1 rounded border border-emerald-900/50">ONLINE</span>
          </div>

          <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4 flex justify-between items-center">
            <div>
              <span className="text-xs text-neutral-400 block uppercase font-semibold">Mức độ nguy cơ hiện tại</span>
              <span className={`text-xl font-extrabold ${riskLevel > 15 ? 'text-red-500' : 'text-orange-400'}`}>{riskLevel * 4}%</span>
            </div>
            <div className="text-xs text-neutral-500">Ngưỡng báo động: 100%</div>
          </div>

          <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4 flex justify-between items-center">
            <div>
              <span className="text-xs text-neutral-400 block uppercase font-semibold">Tổng số sự cố đã ghi nhận</span>
              <span className="text-xl font-bold text-red-500">{caseCount} vụ việc</span>
            </div>
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6 text-neutral-600">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
            </svg>
          </div>
        </div>

        {/* CHI TIẾT CAMERA & BẢN GHI KHẨN CẤP */}
        <div className="flex flex-col lg:flex-row gap-6">
          
          {/* MÀN HÌNH CAMERA LIVE AI */}
          <div className="flex-1 bg-neutral-900 border border-neutral-800 rounded-2xl p-4 shadow-xl">
            <div className="flex justify-between items-center mb-3">
              <h3 className="text-md font-bold tracking-wide text-neutral-300 uppercase flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-red-600 animate-ping"></span>
                MÀN HÌNH QUAN SÁT AI {activeTab === 'camera' ? '(LIVE CAM)' : '(VIDEO TEST)'}
              </h3>

              <div className="flex p-1 bg-neutral-950 rounded-xl border border-neutral-800/80 w-fit">
                <button onClick={() => switchStreamSource('camera')} className={`px-4 py-1.5 rounded-lg font-bold text-[11px] uppercase tracking-wider transition-all ${activeTab === 'camera' ? 'bg-blue-600/10 border border-blue-500/40 text-blue-400' : 'text-neutral-500 hover:text-neutral-300'}`}>
                  Camera
                </button>
                <button onClick={() => setActiveTab('video')} className={`px-4 py-1.5 rounded-lg font-bold text-[11px] uppercase tracking-wider transition-all ${activeTab === 'video' ? 'bg-orange-600/10 border border-orange-500/40 text-orange-400' : 'text-neutral-500 hover:text-neutral-300'}`}>
                  Video
                </button>
              </div>
            </div>

            <div className={`relative aspect-video rounded-xl overflow-hidden flex items-center justify-center bg-stone-950 border-2 transition-all duration-300 ${
              riskLevel > 15 ? 'border-red-600 shadow-2xl shadow-red-900/20' : 'border-neutral-950'
            }`}>
              {imageSrc ? (
                <img src={imageSrc} alt="Fire/Smoke Live feed" className="w-full h-full object-contain" />
              ) : (
                <div className="text-center text-neutral-500 space-y-3">
                  <div className="animate-spin inline-block w-8 h-8 border-[3px] border-current border-t-transparent text-red-600 rounded-full"></div>
                  <p className="text-sm font-medium">Đang kết nối luồng AI từ Server Python...</p>
                </div>
              )}

              {riskLevel >= 25 && (
                <div className="absolute inset-0 bg-red-600/10 pointer-events-none border-4 border-red-600 animate-pulse flex items-start justify-center pt-4">
                  <span className="bg-red-600 text-white font-black px-4 py-1.5 rounded text-sm tracking-widest uppercase shadow-lg animate-bounce">
                    🚨 ĐÃ KÍCH HOẠT BÁO ĐỘNG ĐỎ 🚨
                  </span>
                </div>
              )}
            </div>

            <div className="mt-5 space-y-2">
              <div className="flex justify-between text-xs font-bold uppercase tracking-wider text-neutral-400">
                <span>Chỉ số tích lũy rủi ro cháy nổ</span>
                <span className={riskLevel > 15 ? 'text-red-500 font-black' : 'text-orange-400'}>
                  {riskLevel} / 15 Khung hình nghi vấn
                </span>
              </div>
              <div className="w-full bg-neutral-950 h-3 rounded-full overflow-hidden p-0.5 border border-neutral-800">
                <div 
                  className="h-full rounded-full transition-all duration-100 ease-in-out"
                  style={{ 
                    width: `${(riskLevel / 15) * 100}%`,
                    backgroundColor: riskLevel > 15 ? '#dc2626' : riskLevel > 5 ? '#ea580c' : '#16a34a'
                  }}
                />
              </div>
            </div>
            {activeTab === 'video' && (
              <div className="mt-6 flex justify-end">
                <label className={`cursor-pointer inline-flex items-center gap-3 bg-neutral-800 hover:bg-neutral-700 text-white font-bold text-xs uppercase tracking-wider px-5 py-3 rounded-lg transition-colors border border-neutral-700 ${isUploading ? 'opacity-50 pointer-events-none' : ''}`}>
                  📥 {isUploading ? 'Đang xử lý...' : 'Import Video Mới'}
                  <input 
                    type="file" 
                    accept="video/*" 
                    className="hidden" 
                    disabled={isUploading}
                    onChange={handleVideoUpload}
                  />
                </label>
              </div>
            )}

            {activeTab === 'video' && uploadedVideoName && (
              <p className="text-center text-blue-400 text-sm mt-2">Đang phát: {uploadedVideoName}</p>
            )}

            {/* ================= FIRE ANALYSIS PANEL ================= */}

            <div className="mt-6 bg-neutral-950 border border-neutral-800 rounded-xl p-4">

              <div className="flex justify-between items-center mb-4">
                <h3 className="text-sm font-bold uppercase tracking-wider text-orange-400">
                  🔥 Cảnh báo về mức độ cháy
                </h3>

                <span className="text-xs bg-red-950 text-red-400 px-2 py-1 rounded border border-red-800">
                  Realtime
                </span>
              </div>

              {/* Fire Area */}
              <div className="mb-4">
                <div className="flex justify-between text-xs mb-1">
                  <span>Fire Area</span>
                  <span>{analysis.fireArea.toFixed(1)}%</span>
                </div>

                <div className="h-3 bg-neutral-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-red-500"
                    style={{ width: `${analysis.fireArea}%` }}
                  />
                </div>
              </div>

              {/* Smoke Area */}
              <div className="mb-4">
                <div className="flex justify-between text-xs mb-1">
                  <span>Smoke Area</span>
                  <span>{analysis.smokeArea.toFixed(1)}%</span>
                </div>

                <div className="h-3 bg-neutral-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-orange-500"
                    style={{ width: `${analysis.smokeArea}%` }}
                  />
                </div>
              </div>

              {/* Intensity */}
              <div className="mb-4">
                <div className="flex justify-between text-xs mb-1">
                  <span>Intensity</span>
                  <span>{analysis.intensity.toFixed(1)}%</span>
                </div>

                <div className="h-3 bg-neutral-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-yellow-500"
                    style={{ width: `${analysis.intensity}%` }}
                  />
                </div>
              </div>

              {/* FSI */}
              <div className="mb-5">
                <div className="flex justify-between text-xs mb-1">
                  <span>FSI</span>
                  <span>{analysis.fsi.toFixed(1)}%</span>
                </div>

                <div className="h-3 bg-neutral-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500"
                    style={{ width: `${analysis.fsi}%` }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 border-t border-neutral-800 pt-4">

                <div className="bg-neutral-900 rounded-lg p-3">
                  <div className="text-xs text-neutral-500">
                    Fire Growth
                  </div>
                  <div className="text-red-400 font-bold">
                    {analysis.fireGrowth.toFixed(2)}
                  </div>
                </div>

                <div className="bg-neutral-900 rounded-lg p-3">
                  <div className="text-xs text-neutral-500">
                    Smoke Growth
                  </div>
                  <div className="text-orange-400 font-bold">
                    {analysis.smokeGrowth.toFixed(2)}
                  </div>
                </div>

                <div className="bg-neutral-900 rounded-lg p-3">
                  <div className="text-xs text-neutral-500">
                    Duration
                  </div>
                  <div className="font-bold">
                    {analysis.duration}s
                  </div>
                </div>

                <div className="bg-neutral-900 rounded-lg p-3">
                  <div className="text-xs text-neutral-500">
                    Intensity
                  </div>
                  <div className="font-bold">
                    {analysis.intensity.toFixed(1)}
                  </div>
                </div>

              </div>

              <div className="mt-4">
                <div
                  className={`text-center py-3 rounded-lg font-black text-xl
                  ${
                  analysis.risk === "SAFE"
                  ? "bg-green-950 border border-green-700 text-green-400"
                  : analysis.risk === "MEDIUM"
                  ? "bg-yellow-950 border border-yellow-700 text-yellow-400"
                  : analysis.risk === "HIGH"
                  ? "bg-orange-950 border border-orange-700 text-orange-400"
                  : "bg-red-950 border border-red-700 text-red-400 animate-pulse"
                  }`}
                  >
                  RISK: {analysis.risk}
                </div>
              </div>

            </div>
          </div>


          

          {/* CỘT PHẢI: BẢN GHI SỰ CỐ & THỦ TỤC */}
          <div className="lg:w-[400px] w-full flex flex-col gap-6">
            
            <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-4 h-[320px] flex flex-col shadow-xl">
              <div className="flex justify-between items-center border-b border-neutral-800 pb-2 mb-3">
                <h3 className="text-sm font-bold tracking-wide text-neutral-300 uppercase flex items-center gap-2">
                  📂 BẢN GHI SỰ CỐ KHẨN CẤP
                </h3>
                {alerts.length > 0 && (
                  <button
                    onClick={handleResolveCase}
                    className="text-[11px] bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-2 py-1 rounded transition-colors shadow"
                  >
                    ✔️ Đã giải quyết xong
                  </button>
                )}
              </div>
              
              <div className="flex-1 overflow-y-auto space-y-2 pr-1">
                {alerts.length === 0 ? (
                  <div className="h-full flex items-center justify-center text-center text-neutral-600 italic text-xs">
                    Hệ thống an toàn. Chưa ghi nhận sự cố mới.
                  </div>
                ) : (
                  <>
                    {alerts.map((alert) => (
                      <div 
                        key={alert.id}
                        className={`p-3 rounded-xl border text-xs leading-relaxed shadow-sm transition-all ${
                          alert.type === 'fire' 
                            ? 'bg-red-950/30 border-red-900/60 text-red-200' 
                            : 'bg-orange-950/30 border-orange-900/60 text-orange-200'
                        }`}
                      >
                        <div className="flex justify-between font-black mb-1">
                          <span className={alert.type === 'fire' ? 'text-red-500' : 'text-orange-500'}>
                            ⚠️ PHÁT HIỆN {alert.type.toUpperCase()}
                          </span>
                          <span className="text-neutral-500 font-mono font-normal">{alert.time}</span>
                        </div>
                        <p className="text-neutral-300">{alert.message}</p>
                      </div>
                    ))}
                  </>
                )}
              </div>
            </div>

            {/* 🧯 THỦ TỤC PHẢN ỨNG KHẨN CẤP */}
            <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-4 shadow-xl flex-1">
              <h3 className="text-sm font-bold tracking-wide text-neutral-300 uppercase border-b border-neutral-800 pb-2 mb-3">
                🧯 THỦ TỤC PHẢN ỨNG KHẨN CẤP
              </h3>
              <ul className="space-y-3 text-xs text-neutral-300">
                <li className="flex items-start gap-2">
                  <span className="bg-neutral-800 text-neutral-400 w-5 h-5 rounded-full flex items-center justify-center font-bold flex-shrink-0">1</span>
                  <span><strong>Xác minh luồng:</strong> Xem lại bounding box trên camera AI để loại trừ cảnh báo giả.</span>
                </li>
                
                <li className="flex items-start gap-2">
                  <span className="bg-neutral-800 text-neutral-400 w-5 h-5 rounded-full flex items-center justify-center font-bold flex-shrink-0">2</span>
                  <span><strong>Xử lý hiện trường:</strong> Sau khi dập tắt đám cháy, nhấn nút <strong className="text-emerald-400">"Đã giải quyết xong"</strong> để đóng sự cố và lưu hồ sơ.</span>
                </li>
                
                <li className="flex items-start gap-2">
                  <span className={`w-5 h-5 rounded-full flex items-center justify-center font-bold flex-shrink-0 transition-colors duration-300 ${
                    systemStatus === 'danger' ? 'bg-red-600 text-white animate-pulse' : 'bg-neutral-800 text-neutral-400'
                  }`}>
                    3
                  </span>
                  <div className={`flex-1 transition-all rounded-md ${
                    systemStatus === 'danger' ? 'bg-red-950/40 border border-red-900/60 p-1.5 -mt-1 text-red-200 animate-pulse' : ''
                  }`}>
                    <span><strong>Liên hệ khẩn cấp:</strong> Gọi ngay lực lượng cứu hỏa <strong className="text-red-500 font-extrabold">114</strong> nếu đám cháy lan rộng.</span>
                  </div>
                </li>
              </ul>
            </div>

          </div>
        </div>

        {/* LỊCH SỬ KHO LƯU TRỮ HỒ SƠ */}
        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 shadow-xl">
          <h3 className="text-md font-bold tracking-wide text-neutral-300 uppercase border-b border-neutral-800 pb-3 mb-4 flex items-center gap-2">
            📋 NHẬT KÝ LỊCH SỬ XỬ LÝ SỰ CỐ (LƯU TRỮ HỒ SƠ)
          </h3>
          
          {caseHistory.length === 0 ? (
            <div className="text-center text-neutral-600 italic text-sm py-4">
              Chưa có dữ liệu lưu trữ lịch sử sự cố đã đóng.
            </div>
          ) : (
            <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2">
              {caseHistory.map((historyCase) => (
                <div key={historyCase.caseId} className="bg-neutral-950 border border-neutral-850 rounded-xl p-4">
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-neutral-850 pb-2 mb-2 gap-2">
                    <span className="text-sm font-bold text-neutral-200">
                      🔥 VỤ VIỆC SỐ #{historyCase.caseId}
                    </span>
                    <span className="text-xs bg-emerald-950 text-emerald-400 border border-emerald-900/50 px-2.5 py-1 rounded-md font-medium">
                      ✓ Đã giải quyết & Đóng hồ sơ lúc: {historyCase.resolvedAt}
                    </span>
                  </div>
                  
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 mt-3">
                    {historyCase.logs.map((log) => (
                      <div key={log.id} className="bg-neutral-900/60 p-2 rounded-lg border border-neutral-800 flex justify-between items-center text-[11px]">
                        <span className={log.type === 'fire' ? 'text-red-400/80 font-bold' : 'text-orange-400/80 font-bold'}>
                          [{log.type.toUpperCase()}] Ghi nhận
                        </span>
                        <span className="text-neutral-500 font-mono">{log.time}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </main>
    </div>
  );
}

export default App;