import { Alert } from '../types';

interface AlertsPanelProps {
  alerts: Alert[];
  setAlerts: React.Dispatch<React.SetStateAction<Alert[]>>;
}

export default function AlertsPanel({ alerts, setAlerts }: AlertsPanelProps) {
  
  // Sự kiện bấm nút "Bỏ qua": Xóa cảnh báo khỏi danh sách hiển thị
  const handleDismiss = (id: string) => {
    setAlerts(prev => prev.filter(a => a.id !== id));
  };

  // Sự kiện bấm nút "Xử lý": Hạ cấp độ nghiêm trọng xuống 'medium' (Màu vàng an toàn)
  const handleResolve = (id: string) => {
    setAlerts(prev =>
      prev.map(a => a.id === id ? { ...a, severity: 'medium' as const } : a)
    );
  };

  // Hàm helper sinh màu sắc dựa theo các sự kiện AI trả về
  const getSeverityStyle = (severity: string) => {
    if (severity === 'critical') return 'border-red-600/50 bg-red-950/30 text-red-200';
    if (severity === 'high') return 'border-orange-600/50 bg-orange-950/30 text-orange-200';
    return 'border-yellow-600/40 bg-yellow-950/20 text-yellow-200';
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl h-fit shadow-xl overflow-hidden">
      
      {/* Header hiển thị tổng số lượng sự kiện đang kích hoạt */}
      <div className="bg-gradient-to-r from-red-600 to-orange-600 p-5">
        <div className="flex justify-between items-center">
          <div>
            <h3 className="font-bold text-xl tracking-wide">Bảng Sự Kiện AI</h3>
            <p className="text-xs opacity-90 mt-0.5">Dữ liệu truyền từ luồng Python SocketIO</p>
          </div>
          <span className="bg-black/30 px-3 py-1 rounded-full text-xs font-bold backdrop-blur-sm animate-pulse">
            {alerts.length} Active
          </span>
        </div>
      </div>

      {/* Vùng hiển thị nội dung các sự kiện */}
      <div className="p-5 max-h-[600px] overflow-y-auto space-y-4">
        {alerts.length === 0 ? (
          /* Trạng thái 1: Hệ thống chạy (success=True) nhưng chưa vượt ngưỡng rủi ro 25 frames */
          <div className="text-center py-12 space-y-2">
            <div className="w-12 h-12 bg-gray-800/50 rounded-full flex items-center justify-center mx-auto text-green-400 border border-green-500/20">
              ✓
            </div>
            <p className="text-gray-400 font-medium text-sm">Hệ thống an toàn</p>
            <p className="text-xs text-gray-500">Đang quét ngầm luồng video...</p>
          </div>
        ) : (
          /* Trạng thái 2: Python bắt được sự kiện và bắn object 'new_alert' qua Socket */
          alerts.map(alert => (
            <div 
              key={alert.id} 
              className={`p-4 rounded-xl border transition-all duration-200 ${getSeverityStyle(alert.severity)}`}
            >
              <div className="flex justify-between items-start gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2.5">
                    {/* Badge thể hiện mức độ nghiêm trọng quy định từ loại nhãn (Fire -> Critical, Smoke -> High) */}
                    <span className={`inline-block px-2.5 py-0.5 text-[10px] font-extrabold rounded-md tracking-wider uppercase
                      ${alert.severity === 'critical' ? 'bg-red-600 text-white' : alert.severity === 'high' ? 'bg-orange-600 text-white' : 'bg-yellow-600 text-black'}`}>
                      {alert.severity === 'critical' ? ' CRITICAL' : alert.severity === 'high' ? '⚠ HIGH' : ' RESOLVED'}
                    </span>
                    <span className="text-[11px] font-mono text-gray-400 bg-gray-950 px-2 py-0.5 rounded uppercase">
                      {alert.type}
                    </span>
                  </div>

                  {/* Nội dung tin nhắn sự kiện */}
                  <p className="font-semibold text-sm text-white leading-snug">{alert.message}</p>
                  
                  {/* Định dạng lại mốc thời gian hệ thống bắn sự kiện */}
                  <p className="text-[11px] text-gray-400 mt-2 flex items-center gap-1 font-mono">
                    <span>Time:</span>
                    <span>
                      {alert.timestamp instanceof Date 
                        ? alert.timestamp.toLocaleTimeString('vi-VN') 
                        : new Date(alert.timestamp).toLocaleTimeString('vi-VN')}
                    </span>
                  </p>
                </div>

                <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${
                  alert.severity === 'critical' ? 'bg-red-500 animate-ping' : alert.severity === 'high' ? 'bg-orange-500' : 'bg-yellow-500'
                }`} />
              </div>

              {/* Tiến trình mô phỏng bộ đệm tích lũy chống nhiễu từ OpenCV */}
              {alert.severity !== 'medium' && (
                <div className="mt-3 bg-gray-950/40 p-2 rounded-lg border border-gray-800/30">
                  <div className="flex justify-between text-[10px] text-gray-400 mb-1 font-mono">
                    <span>AI Risk Level Buffer:</span>
                    <span className="text-red-400 font-bold">25/25 frames (Đạt ngưỡng)</span>
                  </div>
                  <div className="w-full bg-gray-800 h-1 rounded-full overflow-hidden">
                    <div className="bg-gradient-to-r from-orange-500 to-red-600 h-1 w-full" />
                  </div>
                </div>
              )}

              {/* Tương tác cục bộ trên giao diện */}
              <div className="flex gap-2 mt-4 pt-3 border-t border-gray-800/60">
                <button
                  onClick={() => handleResolve(alert.id)}
                  disabled={alert.severity === 'medium'}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition
                    ${alert.severity === 'medium' 
                      ? 'bg-gray-800 text-gray-500 cursor-not-allowed' 
                      : 'bg-green-600/20 text-green-400 hover:bg-green-600 hover:text-white border border-green-500/20'}`}
                >
                  {alert.severity === 'medium' ? '✓ Đã xử lý' : 'Xác nhận'}
                </button>
                <button
                  onClick={() => handleDismiss(alert.id)}
                  className="flex-1 bg-gray-800 hover:bg-gray-700 text-gray-300 py-1.5 rounded-lg text-xs font-semibold transition border border-gray-700/50"
                >
                  Bỏ qua
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}