// 呼叫端一律傳 "/api/..."，交給 nginx.conf 的 /api proxy_pass 轉給 backend。
// 這樣前端完全不用知道 backend 在哪台機器，local/tailscale 切換不用重 build。
// （原本寫死 http://100.123.184.43:8002，那是舊架構裡「前端自己」的位址，不是
// backend 的，而且這個 port 早就不用了）
export const API_BASE_URL = "";
export const TOKEN_STORAGE_KEY = "my_jwt_token";
export const AUTH_UNAUTHORIZED_EVENT = "auth:unauthorized";

export const getAuthToken = () => localStorage.getItem(TOKEN_STORAGE_KEY);

export const saveAuthToken = (token: string) => {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
};

export const clearAuthToken = () => {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
};

export const getErrorMessage = async (response: Response) => {
  try {
    const data = (await response.json()) as { detail?: string; message?: string };
    return data.detail || data.message || `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
};

const notifyUnauthorized = () => {
  clearAuthToken();
  window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT));
};

export const authFetch = async (path: string, options: RequestInit = {}) => {
  const token = getAuthToken();
  if (!token) {
    notifyUnauthorized();
    throw new Error("AUTH_TOKEN_MISSING");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...options.headers,
      "x-token": token,
    },
  });

  if (response.status === 401) {
    notifyUnauthorized();
  }

  return response;
};
