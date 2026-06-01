export interface Alert {
  id: string;
  type: 'fire' | 'smoke' | 'warning';
  severity: 'critical' | 'high' | 'medium';
  message: string;
  timestamp: Date;
}