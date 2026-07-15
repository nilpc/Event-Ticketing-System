import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, Check, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { PageTransition } from "@/components/layout/page-transition";
import { queueApi } from "@/lib/api-routes";
import { QUEUE_POLL_MS } from "@/lib/constants";
import { useBookingFlow } from "@/stores/booking-store";
import { Button } from "@/components/ui/button";

type QueueState = "joining" | "waiting" | "admitted" | "error";

const PREMIUM_EASE = [0.32, 0.72, 0, 1] as const;

export default function QueuePage() {
  const { showId } = useParams<{ showId: string }>();
  const navigate = useNavigate();
  const { setQueueToken } = useBookingFlow();
  const [state, setState] = useState<QueueState>("joining");
  const [position, setPosition] = useState<number | null>(null);
  const [error, setError] = useState("");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const pollStatus = useCallback(
    (sid: string) => {
      const fetchStatus = async () => {
        try {
          const { data: status } = await queueApi.getQueueStatus(sid);
          if (status.status === "admitted") {
            clearPolling();
            if (status.queue_token) setQueueToken(status.queue_token);
            setState("admitted");
            toast.success("You've been admitted!");
            setTimeout(() => navigate(`/events/${sid}`), 1500);
          } else if (status.status === "waiting") {
            setPosition(status.position ?? null);
            const ms = status.retry_after
              ? status.retry_after * 1000
              : QUEUE_POLL_MS;
            clearPolling();
            intervalRef.current = setInterval(fetchStatus, ms);
          } else {
            clearPolling();
            setState("error");
            setError("Your queue session has expired.");
          }
        } catch {
          clearPolling();
          setState("error");
          setError("Failed to check queue status.");
        }
      };
      fetchStatus();
    },
    [clearPolling, navigate, setQueueToken],
  );

  useEffect(() => {
    if (!showId) return;
    let cancelled = false;

    const init = async () => {
      try {
        const { data: recovered } = await queueApi.recoverQueue(showId);
        if (cancelled) return;

        if (recovered.status === "admitted") {
          if (recovered.queue_token) setQueueToken(recovered.queue_token);
          toast.info("Resuming your session...");
          navigate(`/events/${showId}`);
          return;
        }

        const { data: result } = await queueApi.joinQueue({ show_id: showId });
        if (cancelled) return;
        if (result.queue_token) setQueueToken(result.queue_token);
        setPosition(result.position);
        setState("waiting");
        intervalRef.current = setInterval(() => pollStatus(showId), QUEUE_POLL_MS);
      } catch {
        if (!cancelled) {
          setState("error");
          setError("Failed to join the queue.");
        }
      }
    };

    init();
    return () => {
      cancelled = true;
      clearPolling();
    };
  }, [showId, navigate, pollStatus, clearPolling, setQueueToken]);

  return (
    <PageTransition>
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="p-10 w-full max-w-md text-center rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl">
          <AnimatePresence mode="wait">
            {state === "joining" && (
              <motion.div
                key="joining"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-4"
              >
                <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
                <p className="text-muted-foreground">Joining queue...</p>
              </motion.div>
            )}

            {state === "waiting" && (
              <motion.div
                key="waiting"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.4, ease: PREMIUM_EASE }}
                className="space-y-6"
              >
                <p className="text-muted-foreground/60 text-[10px] uppercase tracking-widest font-medium">
                  You&apos;re in the queue
                </p>

                <div className="relative flex items-center justify-center h-44">
                  <motion.div
                    className="absolute inset-0 rounded-full border-2 border-dashed border-primary/20"
                    animate={{ rotate: 360 }}
                    transition={{
                      duration: 20,
                      repeat: Infinity,
                      ease: "linear",
                    }}
                  />
                  <div className="relative z-10">
                    <AnimatePresence mode="wait">
                      <motion.span
                        key={position}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className="text-6xl font-bold text-gradient"
                      >
                        #{position ?? "..."}
                      </motion.span>
                    </AnimatePresence>
                  </div>
                </div>

                <div className="flex items-center justify-center gap-2 text-muted-foreground">
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
                  </span>
                  <span className="text-sm">Waiting to be admitted...</span>
                </div>

                <div className="w-full h-1 bg-muted/30 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-gradient-to-r from-primary/60 via-primary to-primary/60 rounded-full"
                    animate={{ x: ["-100%", "100%"] }}
                    transition={{
                      duration: 1.5,
                      repeat: Infinity,
                      ease: [0.32, 0.72, 0, 1],
                    }}
                    style={{ width: "40%" }}
                  />
                </div>

                <p className="text-xs text-muted-foreground/40">
                  This may take a few minutes
                </p>
              </motion.div>
            )}

            {state === "admitted" && (
              <motion.div
                key="admitted"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, ease: PREMIUM_EASE }}
                className="space-y-4"
              >
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 200, damping: 15 }}
                  className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-primary/15"
                >
                  <Check className="h-10 w-10 text-primary" />
                </motion.div>
                <h2 className="text-2xl font-bold text-primary">
                  You&apos;re in!
                </h2>
                <p className="text-muted-foreground">
                  Redirecting to seat selection...
                </p>
              </motion.div>
            )}

            {state === "error" && (
              <motion.div
                key="error"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="space-y-4"
              >
                <AlertCircle className="h-8 w-8 mx-auto text-destructive" />
                <p className="text-muted-foreground">{error}</p>
                <Button
                  onClick={() => navigate(-1)}
                  variant="outline"
                  className="rounded-full"
                >
                  Go Back
                </Button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </PageTransition>
  );
}
