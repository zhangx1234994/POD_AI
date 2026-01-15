// 用户信息接口
export interface UserInfo {
  id?: number;
  user_id?: string;
  username?: string;
  nickname?: string;
  email?: string;
  mobile?: string;
  platform?: number;
  avatar?: string;
  createdAt?: string;
  updatedAt?: string;
  role?: string | 'USER' | 'ADMIN';
}

// 更新昵称请求
export interface UpdateNicknameRequest {
  nickname: string;
}

// 更新密码请求
export interface UpdatePasswordRequest {
  currentPassword: string;
  newPassword: string;
}
