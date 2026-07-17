import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { authApi } from "@/lib/api-routes";

interface AuthContextValue {
  isAuthenticated: boolean;
  isAdmin: boolean;
  userId: string | null;
  login: (accessToken: string, refreshToken: string, is_admin?: boolean) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";
const IS_ADMIN_KEY = "is_admin";

function parseJwtSub(token: string): string | null {
  try {
    const payload = token.split(".")[1];
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const decoded = atob(base64);
    const json = JSON.parse(decoded);
    return typeof json.sub === "string" ? json.sub : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    return !!localStorage.getItem(ACCESS_TOKEN_KEY);
  });

  const [isAdmin, setIsAdmin] = useState<boolean>(() => {
    return localStorage.getItem(IS_ADMIN_KEY) === "true";
  });

  const [userId, setUserId] = useState<string | null>(() => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    return token ? parseJwtSub(token) : null;
  });

  useEffect(() => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (token) {
      setIsAuthenticated(true);
      setUserId(parseJwtSub(token));
    } else {
      setIsAuthenticated(false);
      setIsAdmin(false);
      setUserId(null);
    }
  }, []);

  const login = useCallback((accessToken: string, refreshToken: string, is_admin?: boolean) => {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    setIsAuthenticated(true);
    setUserId(parseJwtSub(accessToken));
    if (is_admin) {
      localStorage.setItem(IS_ADMIN_KEY, "true");
      setIsAdmin(true);
    } else {
      localStorage.removeItem(IS_ADMIN_KEY);
      setIsAdmin(false);
    }
  }, []);

  const logout = useCallback(() => {
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (refreshToken) {
      authApi.logout({ refresh_token: refreshToken }).catch(() => {});
    }
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(IS_ADMIN_KEY);
    setIsAuthenticated(false);
    setIsAdmin(false);
    setUserId(null);
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthenticated, isAdmin, userId, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
