import React from 'react';

// 1. Định nghĩa kiểu dữ liệu cho Props nhận từ App.tsx
interface CameraFeedProps {
  videoFrame: string;
  riskLevel: number;
}

const CameraFeed: React.FC<CameraFeedProps> = ({ videoFrame, riskLevel }) => {
  const FRAME_THRESHOLD = 25; // Ngưỡng kích hoạt từ Python

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 shadow-lg">
      <h3 className="text-lg font-semibold text-gray-200 mb-3 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
        🎥 Luồng Camera Giám Sát AI (YOLOv8)
      </h3>
      
      {/* KHU VỰC HIỂN THỊ ẢNH BASE64 */}
      <div className="relative aspect-video bg-black rounded-lg overflow-hidden flex items-center justify-center border border-gray-950">
        {videoFrame ? (
          <img 
            src={videoFrame} 
            alt="AI Realtime Stream" 
            className="w-full h-full object-contain"
          />
        ) : (
          <div className="text-center text-gray-500 space-y-2">
            <div className="animate-spin inline-block w-6 h-6 border-[3px] border-current border-t-transparent text-red-500 rounded-full" role="status" aria-label="loading"></div>
            <p className="text-sm">Đang kết nối luồng AI từ Server Python...</p>
          </div>
        )}
      </div>
      
      {/* THANH TRẠNG THÁI RISK LEVEL TÍCH LŨY */}
      <div className="mt-4 space-y-1.5">
        <div className="flex justify-between text-xs font-medium text-gray-400">
          <span>Mức độ rủi ro tích lũy</span>
          <span className={riskLevel > 15 ? "text-red-500 font-bold" : riskLevel > 5 ? "text-orange-400" : "text-green-400"}>
            {riskLevel} / {FRAME_THRESHOLD} frames
          </span>
        </div>
        
        {/* THANH PROGRESS BAR CHẠY THEO RISK LEVEL */}
        <div className="w-full bg-gray-800 h-2.5 rounded-full overflow-hidden border border-gray-750">
          <div 
            className="h-full transition-all duration-100 ease-in-out"
            style={{ 
              width: `${(riskLevel / FRAME_THRESHOLD) * 100}%`,
              backgroundColor: riskLevel > 15 ? '#ef4444' : riskLevel > 5 ? '#f97316' : '#22c55e'
            }}
          />
        </div>
      </div>
    </div>
  );
};

export default CameraFeed;