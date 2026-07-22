import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Shield, User, LogOut, Ticket, MapPin, Clock, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { PageTransition } from "@/components/layout/page-transition";
import { useAuth } from "@/stores/auth-store";
import { authApi, bookingApi } from "@/lib/api-routes";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

const PREMIUM_EASE = [0.32, 0.72, 0, 1] as const;

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1, ease: PREMIUM_EASE },
  },
};

const item = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: PREMIUM_EASE } },
};

export default function AccountPage() {
  const navigate = useNavigate();
  const { userId, logout } = useAuth();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [anonymizeOpen, setAnonymizeOpen] = useState(false);
  const [loading, setLoading] = useState<"delete" | "anonymize" | null>(
    null,
  );

  const { data: bookings, isLoading: bookingsLoading, isError: bookingsError, refetch: refetchBookings } = useQuery({
    queryKey: ["userBookings"],
    queryFn: () => bookingApi.getUserBookings().then((r) => r.data),
    retry: 1,
  });

  const handleDelete = async () => {
    setLoading("delete");
    try {
      await authApi.deleteAccount();
      toast.success("Account deleted");
      logout();
      navigate("/");
    } catch {
      toast.error("Failed to delete account");
    } finally {
      setLoading(null);
      setDeleteOpen(false);
    }
  };

  const handleAnonymize = async () => {
    setLoading("anonymize");
    try {
      await authApi.anonymizeAccount();
      toast.success("Data anonymized");
      logout();
      navigate("/");
    } catch {
      toast.error("Failed to anonymize data");
    } finally {
      setLoading(null);
      setAnonymizeOpen(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate("/");
    toast.success("Logged out");
  };

  return (
    <PageTransition>
      <div className="max-w-3xl mx-auto px-6 py-16 md:py-24">
        <motion.h1
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: PREMIUM_EASE }}
          className="text-3xl font-bold tracking-tight mb-10"
        >
          Account Settings
        </motion.h1>

        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="space-y-6"
        >
          {/* Profile Card */}
          <motion.div variants={item} className="p-6 rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center h-9 w-9 rounded-xl bg-primary/10">
                <User className="h-4 w-4 text-primary" />
              </div>
              <h2 className="text-lg font-semibold">Profile</h2>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-muted-foreground text-xs">User ID</Label>
                <span className="text-sm font-mono text-muted-foreground">
                  {userId ? `${userId.slice(0, 8)}...` : "N/A"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <Label className="text-muted-foreground text-xs">Status</Label>
                <span className="inline-flex items-center gap-1.5 text-sm text-primary">
                  <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                  Active
                </span>
              </div>
            </div>
          </motion.div>

          {/* My Bookings */}
          <motion.div variants={item} className="p-6 rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center h-9 w-9 rounded-xl bg-primary/10">
                <Ticket className="h-4 w-4 text-primary" />
              </div>
              <h2 className="text-lg font-semibold">My Bookings</h2>
            </div>
            {bookingsLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : bookingsError ? (
              <div className="flex flex-col items-center gap-3 py-8">
                <p className="text-sm text-muted-foreground/50">
                  Failed to load bookings.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refetchBookings()}
                  className="rounded-full"
                >
                  <RefreshCw className="mr-2 h-3 w-3" />
                  Retry
                </Button>
              </div>
            ) : !bookings || bookings.length === 0 ? (
              <p className="text-sm text-muted-foreground/50 py-4 text-center">
                No bookings yet. Browse events to get started.
              </p>
            ) : (
              <div className="space-y-3">
                {bookings.map((b) => (
                  <div
                    key={b.booking_id}
                    className="p-4 rounded-xl bg-muted/20 border border-white/[0.04] space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-semibold">
                        {b.event_name}
                      </p>
                      <span
                        className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full ${
                          b.status === "CONFIRMED"
                            ? "bg-primary/15 text-primary border border-primary/20"
                            : b.status === "PENDING"
                              ? "bg-amber-500/15 text-amber-500 border border-amber-500/20"
                              : "bg-muted/30 text-muted-foreground border border-white/[0.04]"
                        }`}
                      >
                        {b.status}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <MapPin className="h-3 w-3" />
                        {b.venue_name}
                      </span>
                      <span className="flex items-center gap-1">
                        <Ticket className="h-3 w-3" />
                        {b.seats.map((s) => s.seat_id).join(", ")}
                      </span>
                      {b.start_time && (
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {new Date(b.start_time).toLocaleString()}
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <span className="text-primary font-medium">
                          ₹{parseFloat(b.amount).toFixed(2)}
                        </span>
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </motion.div>

          {/* GDPR Data Controls */}
          <motion.div variants={item} className="p-6 rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center h-9 w-9 rounded-xl bg-primary/10">
                <Shield className="h-4 w-4 text-primary" />
              </div>
              <h2 className="text-lg font-semibold">Data &amp; Privacy</h2>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 rounded-xl bg-muted/20 border border-white/[0.04]">
                <div>
                  <p className="text-sm">Delete my account</p>
                  <p className="text-xs text-muted-foreground/50">
                    Soft-delete your account. Data retained for 30 days.
                  </p>
                </div>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setDeleteOpen(true)}
                  className="rounded-full"
                >
                  Delete
                </Button>
              </div>

              <div className="flex items-center justify-between p-3 rounded-xl bg-muted/20 border border-white/[0.04]">
                <div>
                  <p className="text-sm">Anonymize my data</p>
                  <p className="text-xs text-muted-foreground/50">
                    Permanently anonymize your personal data.
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setAnonymizeOpen(true)}
                  className="rounded-full"
                >
                  Anonymize
                </Button>
              </div>
            </div>
          </motion.div>

          {/* Session Info */}
          <motion.div variants={item} className="p-6 rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center h-9 w-9 rounded-xl bg-primary/10">
                <LogOut className="h-4 w-4 text-primary" />
              </div>
              <h2 className="text-lg font-semibold">Sessions</h2>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-primary" />
                <span className="text-sm text-muted-foreground">
                  Active session
                </span>
              </div>
              <Button variant="outline" size="sm" onClick={handleLogout} className="rounded-full">
                Logout
              </Button>
            </div>
          </motion.div>
        </motion.div>

        {/* Delete Account Dialog */}
        <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
          <DialogContent className="rounded-2xl border border-white/[0.06] bg-card/80 backdrop-blur-xl">
            <DialogHeader>
              <DialogTitle>
                Delete Account?
              </DialogTitle>
              <DialogDescription className="text-muted-foreground">
                This will soft-delete your account. Your data will be
                retained for 30 days then permanently removed.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="gap-2">
              <Button
                variant="outline"
                onClick={() => setDeleteOpen(false)}
                className="rounded-full"
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDelete}
                disabled={loading === "delete"}
                className="rounded-full"
              >
                {loading === "delete" && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Yes, delete my account
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Anonymize Account Dialog */}
        <Dialog open={anonymizeOpen} onOpenChange={setAnonymizeOpen}>
          <DialogContent className="rounded-2xl border border-white/[0.06] bg-card/80 backdrop-blur-xl">
            <DialogHeader>
              <DialogTitle>
                Anonymize Data?
              </DialogTitle>
              <DialogDescription className="text-muted-foreground">
                This will permanently anonymize your personal data. This
                action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="gap-2">
              <Button
                variant="outline"
                onClick={() => setAnonymizeOpen(false)}
                className="rounded-full"
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleAnonymize}
                disabled={loading === "anonymize"}
                className="rounded-full"
              >
                {loading === "anonymize" && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Yes, anonymize everything
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </PageTransition>
  );
}
