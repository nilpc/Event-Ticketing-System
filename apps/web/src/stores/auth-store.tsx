import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { authApi } from "@/lib/api-routes";

interface AuthContextValue {
  isAuthenticated: boolean;
  isAdmin: boolean;
  userId: string | null;
  login: (accessToken: string, refreshToken: string, adminToken?: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";
const ADMIN_TOKEN_KEY = "admin_token";

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
    return !!localStorage.getItem(ADMIN_TOKEN_KEY);
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
      setUserId(null);
    }
  }, []);

  const login = useCallback((accessToken: string, refreshToken: string, adminToken?: string) => {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    setIsAuthenticated(true);
    setUserId(parseJwtSub(accessToken));
    if (adminToken) {
      localStorage.setItem(ADMIN_TOKEN_KEY, adminToken);
      setIsAdmin(true);
    }
  }, []);

  const logout = useCallback(() => {
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (refreshToken) {
      authApi.logout({ refresh_token: refreshToken }).catch(() => {});
    }
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(ADMIN_TOKEN_KEY);
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
