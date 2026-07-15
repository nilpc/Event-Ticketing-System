import { useState, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Mail, Lock, Eye, EyeOff, User, Check } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authApi } from "@/lib/api-routes";
import { useAuth } from "@/stores/auth-store";
import type { AxiosError } from "axios";

const signupSchema = z
  .object({
    displayName: z.string().min(1, "Please enter your name"),
    email: z.string().email("Please enter a valid email address"),
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

type SignupForm = z.infer<typeof signupSchema>;

function getPasswordStrength(password: string): {
  level: number;
  label: string;
  color: string;
} {
  if (!password) return { level: 0, label: "", color: "" };

  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;

  if (score <= 1) return { level: 1, label: "Weak", color: "bg-destructive" };
  if (score <= 2) return { level: 2, label: "Fair", color: "bg-amber-500" };
  if (score <= 3) return { level: 3, label: "Good", color: "bg-chart-2" };
  return { level: 4, label: "Strong", color: "bg-primary" };
}

const requirements: { test: RegExp; label: string }[] = [
  { test: /.{8,}/, label: "At least 8 characters" },
  { test: /[A-Z]/, label: "One uppercase letter" },
  { test: /[a-z]/, label: "One lowercase letter" },
  { test: /\d/, label: "One number" },
  { test: /[^A-Za-z0-9]/, label: "One special character" },
];

const PREMIUM_EASE = [0.32, 0.72, 0, 1] as const;

const containerVariants = {
  hidden: { opacity: 0, y: 32 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: PREMIUM_EASE, staggerChildren: 0.06 },
  },
};

const childVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: PREMIUM_EASE } },
};

export default function SignupPage() {
  const navigate = useNavigate();
  const { login: storeLogin } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<SignupForm>({
    resolver: zodResolver(signupSchema),
    defaultValues: { displayName: "", email: "", password: "", confirmPassword: "" },
  });

  const watchedPassword = watch("password");
  const strength = useMemo(() => getPasswordStrength(watchedPassword), [watchedPassword]);

  const signupMutation = useMutation({
    mutationFn: (data: SignupForm) =>
      authApi.signup({ email: data.email, password: data.password }).then((r) => r.data),
    onSuccess: async (_data, variables) => {
      toast.success("Account created! Signing you in...");
      try {
        const loginRes = await authApi.login({
          email: variables.email,
          password: variables.password,
        });
        storeLogin(loginRes.data.access_token, loginRes.data.refresh_token);
        navigate("/");
      } catch {
        toast.info("Account created. Please sign in manually.");
        navigate("/login");
      }
    },
    onError: (error: AxiosError<{ detail?: string }>) => {
      toast.error(error.response?.data?.detail || "Signup failed. Please try again.");
    },
  });

  const onSubmit = (data: SignupForm) => {
    signupMutation.mutate(data);
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
              Create an account
            </h1>
            <p className="text-sm text-muted-foreground mt-2">
              Join us to book amazing events
            </p>
          </motion.div>

          <motion.div variants={childVariants}>
            <div className="flex rounded-full bg-muted/30 p-1 mb-6 border border-white/[0.04]">
              <Link
                to="/login"
                className="flex-1 text-center py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors rounded-full"
              >
                Sign in
              </Link>
              <div className="flex-1 text-center py-2 text-sm font-medium bg-primary/15 text-primary rounded-full border border-primary/20">
                Sign up
              </div>
            </div>
          </motion.div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <motion.div variants={childVariants} className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">Display Name</Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/60" />
                <Input
                  type="text"
                  placeholder="Your name"
                  className="pl-10 rounded-xl"
                  disabled={signupMutation.isPending}
                  {...register("displayName")}
                />
              </div>
              {errors.displayName && (
                <p className="text-xs text-destructive">{errors.displayName.message}</p>
              )}
            </motion.div>

            <motion.div variants={childVariants} className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">Email</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/60" />
                <Input
                  type="email"
                  placeholder="you@example.com"
                  className="pl-10 rounded-xl"
                  disabled={signupMutation.isPending}
                  {...register("email")}
                />
              </div>
              {errors.email && (
                <p className="text-xs text-destructive">{errors.email.message}</p>
              )}
            </motion.div>

            <motion.div variants={childVariants} className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/60" />
                <Input
                  type={showPassword ? "text" : "password"}
                  placeholder="Create a strong password"
                  className="pl-10 pr-10 rounded-xl"
                  disabled={signupMutation.isPending}
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

              {watchedPassword && (
                <div className="space-y-2 pt-1">
                  <div className="flex gap-1">
                    {[1, 2, 3, 4].map((i) => (
                      <div
                        key={i}
                        className={`h-1 flex-1 rounded-full transition-colors duration-300 ${
                          i <= strength.level ? strength.color : "bg-muted/30"
                        }`}
                      />
                    ))}
                  </div>
                  {strength.label && (
                    <p className="text-xs text-muted-foreground">
                      Password strength:{" "}
                      <span
                        className={
                          strength.level === 1
                            ? "text-destructive"
                            : strength.level === 2
                              ? "text-amber-500"
                              : strength.level === 3
                                ? "text-chart-2"
                                : "text-primary"
                        }
                      >
                        {strength.label}
                      </span>
                    </p>
                  )}
                  <div className="space-y-1">
                    {requirements.map((req) => {
                      const met = req.test.test(watchedPassword);
                      return (
                        <div key={req.label} className="flex items-center gap-1.5 text-xs">
                          <Check
                            className={`h-3 w-3 ${
                              met ? "text-primary" : "text-muted-foreground/30"
                            }`}
                          />
                          <span
                            className={
                              met ? "text-muted-foreground" : "text-muted-foreground/30"
                            }
                          >
                            {req.label}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </motion.div>

            <motion.div variants={childVariants} className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">Confirm Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/60" />
                <Input
                  type={showConfirm ? "text" : "password"}
                  placeholder="Confirm your password"
                  className="pl-10 pr-10 rounded-xl"
                  disabled={signupMutation.isPending}
                  {...register("confirmPassword")}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm(!showConfirm)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/60 hover:text-foreground transition-colors"
                >
                  {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.confirmPassword && (
                <p className="text-xs text-destructive">
                  {errors.confirmPassword.message}
                </p>
              )}
            </motion.div>

            <motion.div variants={childVariants}>
              <Button
                type="submit"
                className="w-full"
                size="lg"
                disabled={signupMutation.isPending}
              >
                {signupMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Creating account...
                  </>
                ) : (
                  "Create Account"
                )}
              </Button>
            </motion.div>
          </form>

          <motion.p
            variants={childVariants}
            className="text-center text-sm text-muted-foreground mt-6"
          >
            Already have an account?{" "}
            <Link to="/login" className="text-primary hover:underline font-medium">
              Sign in
            </Link>
          </motion.p>
        </div>
      </motion.div>
    </div>
  );
}
