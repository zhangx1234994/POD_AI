// HTTP client for API requests
import axios from 'axios';

// Create axios instance - 与utils/http.ts保持一致的配置
const http = axios.create({
  baseURL: 'http://localhost:8090/api',
  timeout: 30000,
  withCredentials: true, // 添加与utils/http.ts相同的凭据设置
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
http.interceptors.request.use(
  (config) => {
    // Add auth token if available - 使用与utils/http.ts相同的token键名
    const token = localStorage.getItem('token') || localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
http.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    // Handle common errors
    if (error.response?.status === 401) {
      // Handle unauthorized error - 清除两个可能的token键名
      localStorage.removeItem('auth_token');
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export { http };
