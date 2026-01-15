const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

export const adminAuthAPI = {
  login: async (username: string, password: string) => {
    const resp = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(text || resp.statusText);
    }
    return resp.json();
  },
};
