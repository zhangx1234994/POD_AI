export interface PointsRecord {
  id?: string;
  change_type?: string;
  time?: string;
  created_at?: string;
  task_name?: string;
  note?: string;
  amount?: number;
  balance?: number;
  temp?: number;
  recharge?: number;
  total?: number;
  [key: string]: any;
}

export default PointsRecord;
