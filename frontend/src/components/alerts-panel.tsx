import React from 'react';
import { Alert } from '../types';

interface AlertsPanelProps {
  alerts: Alert[];
  setAlerts: React.Dispatch<React.SetStateAction<Alert[]>>;
}

const AlertsPanel: React.FC<AlertsPanelProps> = ({ alerts, setAlerts }) => {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 h-[550px] flex flex-col shadow-lg">
      <div className="flex justify-between items-center mb-4 border-b border-gray-800 pb-2">
        <h3 className="text-lg font-bold text-gray-100 flex items-center gap-2">
          🚨 Nhật Ký Sự Cố Khẩn Cấp
        </h3>
        {alerts.length > 0 && (
          <button 
            onClick={() => setAlerts([])}
            className="text-xs text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 px-2 py-1 rounded transition"
          >
            Xóa nhật ký
          </button>
        )}
      </div>

      {/* DANH SÁCH LOG CẢNH BÁO */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {alerts.length === 0 ? (
          <div className="h-full flex items-center justify-center text-center text-gray-500 italic text-sm">
            Hệ thống an toàn. Không ghi nhận rủi ro nào.
          </div>
        ) : (
          alerts.map((alert) => (
            <div 
              key={alert.id}
              className={`p-3 rounded-lg border text-sm transition-all shadow-sm ${
                alert.type === 'fire' 
                  ? 'bg-red-950/40 border-red-900/60 text-red-200' 
                  : 'bg-orange-950/40 border-orange-900/60 text-orange-200'
              }`}
            >
              <div className="flex justify-between font-bold mb-1">
                <span className={alert.type === 'fire' ? 'text-red-400' : 'text-orange-400'}>
                  [{alert.type.toUpperCase()}]
                </span>
                <span className="text-gray-500 font-normal text-xs">
                  {new Date(alert.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <p className="text-gray-300 text-xs leading-relaxed">{alert.message}</p>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default AlertsPanel;