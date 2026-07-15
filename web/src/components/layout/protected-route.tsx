import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/stores/auth-store";

export default function ProtectedRoute() {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Outlet />;
}
