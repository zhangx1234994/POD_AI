import axios from 'axios';
import { authAPI } from '../utils/http';
import { http } from '../utils/http';
import { UserInfo } from '../types/user';

export interface CrossPlatformLoginParams {
  platform_id: string;
  token: string;
  user_id: string;
  account: string;
  mobile: string;
  timestamp: number;
  signature: string;
}

export const crossPlatformLogin = (data: CrossPlatformLoginParams) => {
  return axios.post('/api/os/v1/sso/cross-platform', data);
};

export interface StatisticsData {
  userId: string;
  imageStatistics: {
    totalUploaded: number;
    totalGenerated: number;
    totalImages: number;
    todayUploaded: number;
    todayGenerated: number;
  };
  taskStatistics: {
    totalTasks: number;
    totalSubtasks: number;
    todayTasks: number;
    todaySubtasks: number;
    totalSuccessSubtasks: number;
    todaySuccessSubtasks: number;
  };
  statisticsTime: string;
}

export interface StatisticsResponse {
  data: StatisticsData;
  success: boolean;
}

export interface UsageStats {
  uploadedImages: number;
  generatedImages: number;
  totalProcessed: number;
  todayUsage: number;
  monthlyLimit: number;
  storageUsed: number;
  storageLimit: number;
}

export const userAPI = {
  getCurrentUser: async (): Promise<UserInfo | null> => {
    try {
      const response = await authAPI.getCurrentUser();
      return response;
    } catch (error) {
      console.error('获取用户信息失败:', error);
      return null;
    }
  },

  updateNickname: async (nickname: string): Promise<UserInfo | null> => {
    try {
      const response = await authAPI.updateNickname(nickname);
      return response;
    } catch (error) {
      console.error('更新昵称失败:', error);
      throw error;
    }
  },

  updatePassword: async (currentPassword: string, newPassword: string): Promise<boolean> => {
    try {
      const response = await authAPI.updatePassword(currentPassword, newPassword);
      return response;
    } catch (error) {
      console.error('更新密码失败:', error);
      throw error;
    }
  },

  getUsageStatistics: async (userId: string): Promise<UsageStats | null> => {
    try {
      const response = await http.get<StatisticsResponse>('/statistics/used', { user_id: userId });
      const data = response.data;

      if (!data || !data.success) {
        console.error('获取统计数据失败:', data);
        return null;
      }

      const statsData = data.data;
      return {
        uploadedImages: statsData.imageStatistics.totalUploaded,
        generatedImages: statsData.imageStatistics.totalGenerated,
        totalProcessed: statsData.taskStatistics.totalSubtasks,
        todayUsage: statsData.taskStatistics.todaySubtasks,
        monthlyLimit: 999999,
        storageUsed: 0,
        storageLimit: 10,
      };
    } catch (error) {
      console.error('获取使用统计数据失败:', error);
      return null;
    }
  },
};
