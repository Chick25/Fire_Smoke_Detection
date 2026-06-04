import { Flame } from 'lucide-react';

export default function Header() {
  return (
    <header className="sticky top-0 z-50 bg-gray-900 border-b border-gray-800 px-6 py-5">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-red-600 to-orange-600 flex items-center justify-center font-bold text-2xl shadow-lg">
            FG
          </div>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Fire Smoke Detection</h1>
            <p className="text-xs text-gray-500 -mt-1">Hệ thống cảnh báo cháy thời gian thực</p>
          </div>
        </div>

        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-2 bg-green-900/30 text-green-400 px-4 py-2 rounded-full">
            <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
            Hệ thống đang hoạt động
          </div>
          <div className="text-gray-400">
            {new Date().toLocaleDateString('vi-VN')}
          </div>
        </div>
      </div>
    </header>
  );
}