import { requestJson } from './http';

export type LoginPayload = {
  username?: string;
  email?: string;
  password: string;
};

export type TokenResponse = {
  accessToken: string;
  refreshToken?: string | null;
  expiresIn: number;
  role: string;
  tokenType?: string;
};

export const authApi = {
  login(payload: LoginPayload) {
    return requestJson<TokenResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  refresh(refreshToken: string) {
    return requestJson<TokenResponse>('/api/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refreshToken }),
    });
  },
};

