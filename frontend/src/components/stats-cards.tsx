import { Alert } from '../types';

interface StatsCardsProps {
  alerts: Alert[]; 
}

export default function StatsCards({ alerts }: StatsCardsProps) {
  const criticalCount = alerts.filter(a => a.severity === 'critical').length;
  const highCount = alerts.filter(a => a.severity === 'high').length;
  const totalEvents = alerts.length;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      
      {/* CARD 1: CẢNH BÁO NGUY HIỂM (Màu đỏ khẩn cấp - Lửa) */}
      <div className={`transition-all duration-300 rounded-2xl p-6 border ${
        criticalCount > 0 
          ? 'bg-red-950/20 border-red-500 animate-pulse' 
          : 'bg-gray-900 border-gray-800'
      }`}>
        <div className="flex justify-between items-center">
          <p className="text-gray-400 text-xs font-bold tracking-wider uppercase">NGUY CƠ HỎA HOẠN</p>
          {criticalCount > 0 && (
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
            </span>
          )}
        </div>
        <p className={`text-4xl font-extrabold mt-2 ${criticalCount > 0 ? 'text-red-500' : 'text-gray-300'}`}>
          {criticalCount}
        </p>
        <p className="text-xs text-gray-500 mt-1">Sự cố khẩn cấp cần xử lý ngay</p>
      </div>

      {/* CARD 2: CẢNH BÁO CHÚ Ý (Màu cam - Khói) */}
      <div className={`transition-all duration-300 rounded-2xl p-6 border ${
        highCount > 0 
          ? 'bg-orange-950/20 border-orange-500' 
          : 'bg-gray-900 border-gray-800'
      }`}>
        <p className="text-gray-400 text-xs font-bold tracking-wider uppercase">CẢNH BÁO CÓ KHÓI</p>
        <p className={`text-4xl font-extrabold mt-2 ${highCount > 0 ? 'text-orange-400' : 'text-gray-300'}`}>
          {highCount}
        </p>
        <p className="text-xs text-gray-500 mt-1">Khu vực cần kiểm tra giám sát</p>
      </div>

      {/* CARD 3: TỔNG SỰ CỐ ĐÃ GHI NHẬN */}
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
        <p className="text-gray-400 text-xs font-bold tracking-wider uppercase">TỔNG SỰ KIỆN LƯU TRỮ</p>
        <p className="text-4xl font-bold mt-2 text-blue-400">
          {totalEvents}
        </p>
        <p className="text-xs text-gray-500 mt-1">Hệ thống AI đang hoạt động ổn định (99.8%)</p>
      </div>

    </div>
  );
}