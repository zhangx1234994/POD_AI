import { http, unauthHttp } from '@/utils/http';
import { DEFAULT_POINTS_PAGE_SIZE } from '@/constants/points';

export interface PointsSummaryParams {
  userId?: string;
  user_id?: string; // support both keys
  change_type?: string;
  point_type?: string;
  q?: string;
}

export const pointsAPI = {
  // 1. 查询积分消耗 (POST /api/op/v1/img/points-cost)
  queryPointsCost: async (userId: string, action: string, imgCount: number) => {
    try {
      const payload = { userId, action, imgCount };
      const res = await http.post('/img/points-cost', payload);
      return res;
    } catch (err) {
      console.error('queryPointsCost error', err);
      throw err;
    }
  },

  // 2. 获取用户积分统计 (GET /api/os/v1/points/statistics)
  getPointsStatistics: async (params: { userId?: string } & PointsSummaryParams) => {
    try {
      const userId = params.userId ?? params.user_id;
      const res = await unauthHttp.get(`/points/statistics?userId=${userId}`);
      return res;
    } catch (err) {
      console.error('getPointsStatistics error', err);
      throw err;
    }
  },

  // 3. 获取用户积分交易记录 (GET /api/os/v1/points/transactions)
  getPointsTransactions: async (queryParams: string) => {
    try {
      const res = await unauthHttp.get(`/points/transactions${queryParams ? `?${queryParams}` : ''}`);
      return res;
    } catch (err) {
      console.error('getPointsTransactions error', err);
      throw err;
    }
  },

  // keep exportPoints for existing UI export (if backend supports it)
  exportPoints: async (params: any) => {
    try {
      const res = await unauthHttp.get('/points/export', { params, responseType: 'blob' });
      return res;
    } catch (err) {
      console.error('exportPoints error', err);
      throw err;
    }
  },
};

export default pointsAPI;
