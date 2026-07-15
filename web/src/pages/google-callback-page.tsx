import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { authApi } from "@/lib/api-routes";
import { useAuth } from "@/stores/auth-store";

export default function GoogleCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login: storeLogin } = useAuth();

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");

    if (!code || !state) {
      toast.error("Missing authentication parameters.");
      navigate("/login");
      return;
    }

    let cancelled = false;

    authApi
      .handleGoogleCallback(code, state)
      .then((res) => {
        if (cancelled) return;
        storeLogin(res.data.access_token, res.data.refresh_token);
        navigate("/");
      })
      .catch(() => {
        if (cancelled) return;
        toast.error("Google sign-in failed. Please try again.");
        navigate("/login");
      });

    return () => {
      cancelled = true;
    };
  }, [searchParams, navigate, storeLogin]);

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.3 }}
        className="glass-card p-10 text-center"
      >
        <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto mb-4" />
        <p className="text-sm text-muted-foreground">Completing sign-in...</p>
      </motion.div>
    </div>
  );
}
