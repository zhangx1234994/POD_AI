import axios, { AxiosResponse, AxiosError, AxiosInstance } from 'axios';
import { ERROR_MESSAGES } from '@/constants/errorMessages';
import { PLATFORM_BASE_URL } from '@/constants/gallery';

const ENABLE_DEMO_AUTH = import.meta.env.VITE_ENABLE_DEMO_AUTH === 'true' || import.meta.env.DEV;
const DEMO_USER_KEY = 'podi-demo-user';
const SMS_CODE_OVERRIDE =
  (import.meta.env.VITE_SMS_CODE_OVERRIDE as string | undefined)?.trim() || '';

export const getFixedSmsCode = (): string => SMS_CODE_OVERRIDE;

// 获取用户友好的错误信息
export const getFriendlyErrorMessage = (error: AxiosError): string => {
  // 如果响应中包含错误码，使用错误码映射
  if (error.response?.data && typeof error.response.data === 'object') {
    const data = error.response.data as any;
    if (data.code && ERROR_MESSAGES[data.code]) {
      return ERROR_MESSAGES[data.code];
    }
    // 兼容旧格式的错误响应
    if (data.message) {
      return data.message;
    }
    if (data.error) {
      return data.error;
    }
  }

  // 根据HTTP状态码返回通用错误信息
  switch (error.response?.status) {
    case 400:
      return '请求参数错误，请检查输入';
    case 401:
      return '登录信息已过期，请重新登录';
    case 403:
      return '您没有权限执行此操作';
    case 404:
      return '请求的资源不存在';
    case 409:
      return '请求冲突，请稍后重试';
    case 500:
      return '服务器内部错误，请稍后重试';
    case 502:
      return '网关错误，请稍后重试';
    case 503:
      return '服务不可用，请稍后重试';
    case 504:
      return '请求超时，请稍后重试';
    default:
      return error.message || '网络请求失败，请稍后重试';
  }
};

export const getUserId = (): string => {
  try {
    const id = typeof localStorage !== 'undefined' ? localStorage.getItem('userId') : null;
    return id || '';
  } catch {
    return '';
  }
};

// Token管理函数
export const getToken = (): string | null => {
  try {
    return typeof localStorage !== 'undefined' ? localStorage.getItem('token') : null;
  } catch {
    return null;
  }
};

export const setToken = (token: string): void => {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('token', token);
    }
  } catch (error) {
    console.error('保存Token失败:', error);
  }
};

export const removeToken = (): void => {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('token');
    }
  } catch (error) {
    console.error('移除Token失败:', error);
  }
};

// 通用HTTP客户端，用于podi-server服务
const httpClient = axios.create({
  baseURL: '/api/op/v1',
  timeout: 30000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

// 认证HTTP客户端，用于podi-manage服务
const authClient = axios.create({
  baseURL: '/api/os/v1/auth',
  timeout: 30000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

// 无需认证的HTTP客户端，用于 podi-manage 客户端
const unauthClient = axios.create({
  baseURL: '/api/os/v1',
  timeout: 30000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

// 通用请求拦截器
const setupRequestInterceptor = (client: AxiosInstance) => {
  client.interceptors.request.use(
    (config) => {
      // 添加Token到请求头
      const token = getToken();
      if (token) {
        config.headers['Authorization'] = `Bearer ${token}`;
      }
      // 保留原有的用户ID逻辑
      const userId = getUserId();
      if (userId) config.headers['X-User-Id'] = userId;
      return config;
    },
    (error) => Promise.reject(error)
  );
};

// 通用响应拦截器
const setupResponseInterceptor = (client: AxiosInstance) => {
  client.interceptors.response.use(
    (response: AxiosResponse) => {
      return response;
    },
    (error: AxiosError) => {
      // 处理401未授权错误
      if (error.response?.status === 401) {
        // 触发自定义事件，通知AuthContext处理401错误
        window.dispatchEvent(new CustomEvent('auth:unauthorized'));
      }

      // 增强错误对象，添加友好的错误信息
      const friendlyMessage = getFriendlyErrorMessage(error);
      const enhancedError = {
        ...error,
        friendlyMessage,
        originalMessage: error.message,
      };

      return Promise.reject(enhancedError);
    }
  );
};

// 为两个客户端设置拦截器
setupRequestInterceptor(httpClient);
setupResponseInterceptor(httpClient);
setupRequestInterceptor(authClient);
setupResponseInterceptor(authClient);
setupRequestInterceptor(unauthClient);
setupResponseInterceptor(unauthClient);

// 定义HTTP客户端接口
export interface HttpClient {
  get: <T = any>(url: string, params?: any) => Promise<AxiosResponse<T>>;
  post: <T = any>(url: string, data?: any) => Promise<AxiosResponse<T>>;
  put: <T = any>(url: string, data?: any) => Promise<AxiosResponse<T>>;
  delete: <T = any>(url: string) => Promise<AxiosResponse<T>>;
  patch: <T = any>(url: string, data?: any) => Promise<AxiosResponse<T>>;
}

// podi-server服务API
export const http: HttpClient = {
  get: <T = any>(url: string, params?: any): Promise<AxiosResponse<T>> => {
    // 检查params是否已经是{ params: ... }格式
    if (params && params.params !== undefined) {
      return httpClient.get(url, params);
    }
    // 否则将params作为查询参数传递
    return httpClient.get(url, { params });
  },
  post: <T = any>(url: string, data?: any): Promise<AxiosResponse<T>> => httpClient.post(url, data),
  put: <T = any>(url: string, data?: any): Promise<AxiosResponse<T>> => httpClient.put(url, data),
  delete: <T = any>(url: string): Promise<AxiosResponse<T>> => httpClient.delete(url),
  patch: <T = any>(url: string, data?: any): Promise<AxiosResponse<T>> =>
    httpClient.patch(url, data),
};

// podi-manage服务API
export const authHttp: HttpClient = {
  get: <T = any>(url: string, params?: any): Promise<AxiosResponse<T>> =>
    authClient.get(url, { params }),
  post: <T = any>(url: string, data?: any): Promise<AxiosResponse<T>> => authClient.post(url, data),
  put: <T = any>(url: string, data?: any): Promise<AxiosResponse<T>> => authClient.put(url, data),
  delete: <T = any>(url: string): Promise<AxiosResponse<T>> => authClient.delete(url),
  patch: <T = any>(url: string, data?: any): Promise<AxiosResponse<T>> =>
    authClient.patch(url, data),
};

// podi-manage 不带认证的 HTTP 客户端
export const unauthHttp: HttpClient = {
  get: <T = any>(url: string, params?: any): Promise<AxiosResponse<T>> =>
    unauthClient.get(url, { params }),
  post: <T = any>(url: string, data?: any): Promise<AxiosResponse<T>> => unauthClient.post(url, data),
  put: <T = any>(url: string, data?: any): Promise<AxiosResponse<T>> => unauthClient.put(url, data),
  delete: <T = any>(url: string): Promise<AxiosResponse<T>> => unauthClient.delete(url),
  patch: <T = any>(url: string, data?: any): Promise<AxiosResponse<T>> => unauthClient.patch(url, data),
};

const getDemoUser = () => {
  try {
    const raw = localStorage.getItem(DEMO_USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

const setDemoUser = (user: any) => {
  try {
    localStorage.setItem(DEMO_USER_KEY, JSON.stringify(user));
  } catch (e) {
    console.warn('failed to persist demo user', e);
  }
};

const clearDemoUser = () => {
  try {
    localStorage.removeItem(DEMO_USER_KEY);
  } catch (e) {
    console.warn('failed to clear demo user', e);
  }
};

const buildDemoUser = (overrides: Partial<any> = {}) => {
  const baseId = overrides.user_id || overrides.userId || overrides.username || overrides.phone || 'demo-user';
  return {
    token: 'demo-token',
    user_id: `demo-${baseId}`,
    username: overrides.username || overrides.phone || 'demo-user',
    nickname: overrides.nickname || overrides.username || overrides.phone || 'Demo 用户',
    email: overrides.email || '',
    platform: overrides.platform || 'demo',
  };
};

// 认证相关API - 使用podi-manage服务
export const authAPI = {
  login: async (username: string, password: string) => {
    if (ENABLE_DEMO_AUTH) {
      const mock = buildDemoUser({ username });
      setToken(mock.token);
      setDemoUser(mock);
      return mock;
    }
    const response = await authHttp.post('/login', { username, password });
    const data = response.data;

    // 如果响应中包含token，保存到localStorage
    if (data && data.token) {
      setToken(data.token);
    }

    return data;
  },
  register: async (username: string, email: string, password: string) => {
    const response = await authHttp.post('/register', { username, email, password });
    return response.data;
  },
  logout: async () => {
    if (ENABLE_DEMO_AUTH) {
      clearDemoUser();
      removeToken();
      return { success: true };
    }
    try {
      const response = await authHttp.post('/logout');
      return response.data;
    } finally {
      removeToken();
    }
  },
  getCurrentUser: async () => {
    if (ENABLE_DEMO_AUTH) {
      return getDemoUser();
    }
    try {
      const response = await authHttp.get('/token/me');
      if (!response || !response.data) {
        console.warn('getCurrentUser: 无效的响应数据');
        return null;
      }
      return response.data;
    } catch (error) {
      console.error('getCurrentUser: 获取用户信息失败', error);
      return null;
    }
  },
  // 发送短信验证码接口：参数格式 { phone, scene }
  sendSms: async (phone: string, scene: string = 'login') => {
    if (SMS_CODE_OVERRIDE) {
      console.info('[auth] using fixed sms code override');
      return { success: true, code: SMS_CODE_OVERRIDE, override: true };
    }
    if (ENABLE_DEMO_AUTH) {
      console.info('[auth] demo sendSms');
      return { success: true, code: '000000' };
    }
    try {
      const response = await authHttp.post('/sms/send', { phone, scene });
      return response.data;
    } catch (err) {
      console.error('sendSms error', err);
      throw err;
    }
  },
  // 手机登录接口：参数格式 { phone, code, agreed_privacy }
  loginPhone: async (phone: string, code: string, agreed_privacy = true) => {
    if (SMS_CODE_OVERRIDE && code === SMS_CODE_OVERRIDE) {
      const mock = buildDemoUser({ phone });
      setToken(mock.token);
      setDemoUser(mock);
      return mock;
    }
    if (ENABLE_DEMO_AUTH) {
      const mock = buildDemoUser({ phone });
      setToken(mock.token);
      setDemoUser(mock);
      return mock;
    }
    try {
      const response = await authHttp.post('/login/phone', { phone, code, agreed_privacy });
      const data = response.data;
      if (data && data.token) {
        setToken(data.token);
      }
      return data;
    } catch (err) {
      console.error('loginPhone error', err);
      throw err;
    }
  },
  updateNickname: async (nickname: string) => {
    try {
      const response = await authHttp.put('/nickname', { nickname });
      return response.data;
    } catch (error) {
      console.error('updateNickname: 更新昵称失败', error);
      throw error;
    }
  },
  updatePassword: async (currentPassword: string, newPassword: string) => {
    try {
      await authHttp.put('/password', {
        currentPassword,
        newPassword,
      });
      return true;
    } catch (error) {
      console.error('updatePassword: 更新密码失败', error);
      throw error;
    }
  },
};

export const unauthAPI = {
  // 获取推送第三方平台所需的临时 token / sourceExtraInfo / sourceImageId 等信息
  getPlatformToken: async (userId: string, imgId: string) => {
    try {
      const path = `/sso/platform/token?user_id=${encodeURIComponent(String(userId || ''))}&img_id=${encodeURIComponent(String(imgId || ''))}`;
      const resp = await unauthHttp.get(path);
      return resp && resp.data ? resp.data : resp;
    } catch (error) {
      throw error;
    }
  },
};

/**
 * 使用 axios 直接向第三方平台发起 POST 请求（跨域独立请求）
 * @param path 相对路径，例如 `/base-web/designimage/cmDesignImageAiTask/downloadAiImageAndSave`
 * @param payload 请求体
 * @param extraHeaders 额外的 headers（例如 x-aipod-key、ssotoken）
 */
export const postToThirdPartyPlatform = async (path: string, payload: any, extraHeaders: Record<string, any> = {}) => {
  try {
    const base = String(PLATFORM_BASE_URL || '').replace(/\/$/, '');
    const fullPath = path && path.startsWith('/') ? path : `/${String(path || '')}`;
    const url = `${base}${fullPath}`;

    const resp = await axios.post(url, payload, {
      headers: {
        'Content-Type': 'application/json',
        ...extraHeaders,
      },
      timeout: 30000,
    });

    return resp && resp.data ? resp.data : resp;
  } catch (error) {
    throw error;
  }
};

export default http;
