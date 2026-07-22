/**
 * Axios-based API client with automatic JWT injection and refresh logic.
 *
 * Consumers pass a `getToken` / `setTokens` / `clearTokens` interface so the
 * SDK stays agnostic of any particular storage mechanism (localStorage, memory,
 * secure cookie, etc.).
 */

import axios, { AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from "axios";

export interface TokenCallbacks {
  /** Return the current access token (or null if unauthenticated). */
  getAccessToken: () => string | null;
  /** Return the current refresh token (or null if unavailable). */
  getRefreshToken: () => string | null;
  /** Persist a fresh token pair after a successful refresh. */
  setTokens: (accessToken: string, refreshToken: string) => void;
  /** Clear stored tokens (e.g. on logout or refresh failure). */
  clearTokens: () => void;
}

export interface SdkClientOptions {
  /** Base URL for the API, e.g. "/v1" or "https://api.example.com/v1". */
  baseURL: string;
  /** Callbacks so the SDK never directly touches storage. */
  tokens: TokenCallbacks;
  /** Optional: called when the user should be redirected to /login. */
  onUnauthorized?: () => void;
}

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else resolve(token as string);
  });
  failedQueue = [];
}

/**
 * Create a pre-configured Axios instance with auth interceptors.
 *
 * The instance is NOT a singleton — callers can create multiple clients with
 * different base URLs or token strategies (useful for testing).
 */
export function createApiClient(options: SdkClientOptions): AxiosInstance {
  const { baseURL, tokens, onUnauthorized } = options;

  const client = axios.create({
    baseURL,
    headers: { "Content-Type": "application/json" },
  });

  // ── Request interceptor: inject Bearer token ────────────────────────
  client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const token = tokens.getAccessToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  // ── Response interceptor: auto-refresh on 401 ──────────────────────
  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const originalRequest = error.config as InternalAxiosRequestConfig & {
        _retry?: boolean;
      };

      if (!originalRequest || error.response?.status !== 401 || originalRequest._retry) {
        return Promise.reject(error);
      }

      // If already refreshing, queue this request
      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
            }
            return client(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = tokens.getRefreshToken();
      if (!refreshToken) {
        isRefreshing = false;
        tokens.clearTokens();
        onUnauthorized?.();
        return Promise.reject(error);
      }

      try {
        const { data } = await axios.post(
          `${baseURL}/auth/refresh`,
          { refresh_token: refreshToken },
          { headers: { "Content-Type": "application/json" } },
        );
        tokens.setTokens(data.access_token, data.refresh_token);
        processQueue(null, data.access_token);
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        }
        return client(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        tokens.clearTokens();
        onUnauthorized?.();
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    },
  );

  return client;
}
