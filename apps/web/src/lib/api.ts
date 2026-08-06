import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { IS_ADMIN_KEY, IS_MASTER_ADMIN_KEY } from "@/stores/auth-store";
const api = axios.create({
  baseURL: "/v1",
  headers: { "Content-Type": "application/json" },
});
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];
function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else {
      resolve(token as string);
    }
  });
  failedQueue = [];
}
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem("access_token");
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    if (!originalRequest || error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }
    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      })
        .then((token) => {
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${token}`;
          }
          return api(originalRequest);
        })
        .catch((err) => Promise.reject(err));
    }
    originalRequest._retry = true;
    isRefreshing = true;
    const refreshToken = localStorage.getItem("refresh_token");
    if (!refreshToken) {
      isRefreshing = false;
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem(IS_ADMIN_KEY);
      localStorage.removeItem(IS_MASTER_ADMIN_KEY);
      window.location.href = "/login";
      return Promise.reject(error);
    }
    try {
      const { data } = await axios.post("/v1/auth/refresh", { refresh_token: refreshToken });
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      if (data.is_admin) {
        localStorage.setItem(IS_ADMIN_KEY, "true");
      } else {
        localStorage.removeItem(IS_ADMIN_KEY);
      }
      if (data.is_master_admin) {
        localStorage.setItem(IS_MASTER_ADMIN_KEY, "true");
      } else {
        localStorage.removeItem(IS_MASTER_ADMIN_KEY);
      }
      processQueue(null, data.access_token);
      if (originalRequest.headers) {
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
      }
      return api(originalRequest);
    } catch (refreshError) {
      processQueue(refreshError, null);
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem(IS_ADMIN_KEY);
      localStorage.removeItem(IS_MASTER_ADMIN_KEY);
      window.location.href = "/login";
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);
export default api;
