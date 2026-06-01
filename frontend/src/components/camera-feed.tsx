interface CameraFeedProps {
  videoFrame: string;
  riskLevel: number; 
}

export default function CameraFeed({ videoFrame, riskLevel }: CameraFeedProps) {
  return (
    <div className="bg-gray-900 rounded-2xl border border-gray-800 overflow-hidden">
      {/* Khung hiển thị ảnh thẻ <img> của videoFrame giữ nguyên ở đây... */}
      <div className="relative aspect-video bg-black flex items-center justify-center">
         {videoFrame ? <img src={videoFrame} alt="Live Stream" /> : <p>Waiting...</p>}
      </div>

      {/* CHÈN GIAO DIỆN THANH TIẾN TRÌNH Ở NGAY DƯỚI KHUNG ẢNH CAMERA */}
      <div className="p-4 bg-gray-950/40 border-t border-gray-800/60">
        <div className="flex justify-between items-center text-xs text-gray-400 font-mono mb-1.5">
          <span>Tích lũy rủi ro chống nhiễu (YOLO Buffer):</span>
          <span className={riskLevel >= 25 ? "text-red-500 font-bold animate-pulse" : "text-yellow-500 font-medium"}>
            {riskLevel}/25 Frames
          </span>
        </div>
        <div className="w-full bg-gray-800 h-2 rounded-full overflow-hidden">
          <div 
            style={{ width: `${(riskLevel / 25) * 100}%` }}
            className={`h-full transition-all duration-75 rounded-full ${
              riskLevel >= 25 ? 'bg-gradient-to-r from-orange-500 to-red-600' : 'bg-gradient-to-r from-yellow-400 to-orange-500'
            }`}
          />
        </div>
      </div>
    </div>
  );
}