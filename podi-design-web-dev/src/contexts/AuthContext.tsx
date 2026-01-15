import * as React from 'react';

interface User {
  id: string;
  username: string;
  nickname?: string;
  email?: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  loginPhone: (phone: string, code: string, agreed_privacy: boolean) => Promise<void>;
}

// 创建默认值
const defaultAuthContext: AuthContextType = {
  user: null,
  isLoading: true,
  login: async () => {
    throw new Error('AuthProvider not initialized');
  },
  logout: async () => {
    throw new Error('AuthProvider not initialized');
  },
  checkAuth: async () => {
    throw new Error('AuthProvider not initialized');
  },
  loginPhone: async () => {
    throw new Error('AuthProvider not initialized');
  },
};

// 创建Context实例，提供默认值
const AuthContext = React.createContext<AuthContextType>(defaultAuthContext);

// 创建useAuth钩子
export const useAuth = () => {
  const context = React.useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// 导出Context和类型
export { AuthContext };
export type { AuthContextType, User };
