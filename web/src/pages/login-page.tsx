import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Mail, Lock, Eye, EyeOff, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authApi } from "@/lib/api-routes";
import { useAuth } from "@/stores/auth-store";
import type { AxiosError } from "axios";

const loginSchema = z.object({
  email: z.string().email("Please enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

type LoginForm = z.infer<typeof loginSchema>;

const PREMIUM_EASE = [0.32, 0.72, 0, 1] as const;

const containerVariants = {
  hidden: { opacity: 0, y: 32 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: PREMIUM_EASE, staggerChildren: 0.08 },
  },
};

const childVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: PREMIUM_EASE } },
};

export default function LoginPage() {
  const navigate = useNavigate();
  const { login: storeLogin } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [isAdminLogin, setIsAdminLogin] = useState(false);
  const [adminToken, setAdminToken] = useState("");

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const loginMutation = useMutation({
    mutationFn: (data: LoginForm) => authApi.login(data).then((r) => r.data),
    onSuccess: (data) => {
      storeLogin(data.access_token, data.refresh_token, isAdminLogin && adminToken ? adminToken : undefined);
      if (isAdminLogin && adminToken) {
        navigate("/admin");
      } else {
        navigate("/");
      }
    },
    onError: (error: AxiosError<{ detail?: string }>) => {
      toast.error(error.response?.data?.detail || "Login failed. Please try again.");
    },
  });

  const googleMutation = useMutation({
    mutationFn: () => authApi.getGoogleAuthUrl().then((r) => r.data),
    onSuccess: (data) => {
      window.location.href = data.authorize_url;
    },
    onError: () => {
      toast.error("Failed to initiate Google sign-in.");
    },
  });

  const onSubmit = (data: LoginForm) => {
    loginMutation.mutate(data);
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12">
      <motion.div
        className="w-full max-w-sm mx-auto"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        <div className="p-8 rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl">
          <motion.div variants={childVariants} className="text-center mb-8">
            <h1 className="text-2xl font-bold tracking-tight">
              Welcome back
            </h1>
            <p className="text-sm text-muted-foreground mt-2">
              Sign in to your account
            </p>
          </motion.div>

          <motion.div variants={childVariants}>
            <div className="flex rounded-full bg-muted/30 p-1 mb-6 border border-white/[0.04]">
              <div className="flex-1 text-center py-2 text-sm font-medium bg-primary/15 text-primary rounded-full border border-primary/20">
                Sign in
              </div>
              <Link
                to="/signup"
                className="flex-1 text-center py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors rounded-full"
              >
                Sign up
              </Link>
            </div>
          </motion.div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <motion.div variants={childVariants} className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">Email</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/60" />
                <Input
                  type="email"
                  placeholder="you@example.com"
                  className="pl-10 rounded-xl"
                  disabled={loginMutation.isPending}
                  {...register("email")}
                />
              </div>
              {errors.email && (
                <p className="text-xs text-destructive">{errors.email.message}</p>
              )}
            </motion.div>

            <motion.div variants={childVariants} className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-medium text-muted-foreground">Password</Label>
                <button
                  type="button"
                  className="text-xs text-muted-foreground/60 hover:text-primary transition-colors"
                >
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/60" />
                <Input
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter your password"
                  className="pl-10 pr-10 rounded-xl"
                  disabled={loginMutation.isPending}
                  {...register("password")}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/60 hover:text-foreground transition-colors"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && (
                <p className="text-xs text-destructive">{errors.password.message}</p>
              )}
            </motion.div>

            <motion.div variants={childVariants} className="space-y-3">
              <label className="flex items-center gap-2.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={isAdminLogin}
                  onChange={(e) => {
                    setIsAdminLogin(e.target.checked);
                    if (!e.target.checked) setAdminToken("");
                  }}
                  className="sr-only peer"
                />
                <div className="h-4 w-4 rounded border border-white/[0.12] bg-muted/30 peer-checked:bg-primary peer-checked:border-primary flex items-center justify-center transition-colors">
                  {isAdminLogin && (
                    <svg className="h-3 w-3 text-primary-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
                <div className="flex items-center gap-1.5">
                  <ShieldCheck className="h-3.5 w-3.5 text-muted-foreground/60" />
                  <span className="text-sm text-muted-foreground">Admin access</span>
                </div>
              </label>

              {isAdminLogin && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="space-y-2"
                >
                  <Label className="text-xs font-medium text-muted-foreground">Admin Token</Label>
                  <Input
                    type="password"
                    placeholder="Enter admin token"
                    value={adminToken}
                    onChange={(e) => setAdminToken(e.target.value)}
                    className="rounded-xl"
                    disabled={loginMutation.isPending}
                  />
                </motion.div>
              )}
            </motion.div>

            <motion.div variants={childVariants}>
              <Button
                type="submit"
                className="w-full"
                size="lg"
                disabled={loginMutation.isPending}
              >
                {loginMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Signing in...
                  </>
                ) : (
                  "Sign In"
                )}
              </Button>
            </motion.div>
          </form>

          <motion.div variants={childVariants} className="mt-6">
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-white/[0.06]" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-card/50 px-3 text-muted-foreground/40">or</span>
              </div>
            </div>

            <Button
              type="button"
              variant="outline"
              className="w-full mt-4 rounded-full"
              size="lg"
              disabled={googleMutation.isPending}
              onClick={() => googleMutation.mutate()}
            >
              {googleMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <svg className="h-4 w-4" viewBox="0 0 24 24">
                  <path
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                    fill="#4285F4"
                  />
                  <path
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    fill="#34A853"
                  />
                  <path
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                    fill="#FBBC05"
                  />
                  <path
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                    fill="#EA4335"
                  />
                </svg>
              )}
              Sign up with Google
            </Button>
          </motion.div>

          <motion.p
            variants={childVariants}
            className="text-center text-sm text-muted-foreground mt-6"
          >
            Don&apos;t have an account?{" "}
            <Link to="/signup" className="text-primary hover:underline font-medium">
              Sign up
            </Link>
          </motion.p>
        </div>
      </motion.div>
    </div>
  );
}
