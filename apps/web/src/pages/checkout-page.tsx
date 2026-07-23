import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Loader2,
  Check,
  CreditCard,
  Clock,
  AlertCircle,
  Ticket,
} from "lucide-react";
import { toast } from "sonner";
import type { AxiosError } from "axios";
import { PageTransition } from "@/components/layout/page-transition";
import { useBookingFlow } from "@/stores/booking-store";
import {
  bookingApi,
  catalogApi,
  confirmApi,
  queueApi,
} from "@/lib/api-routes";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { SeatResponse } from "@/types/api";

type CheckoutStage = "locking" | "booking" | "payment" | "complete";

const PREMIUM_EASE = [0.32, 0.72, 0, 1] as const;

const STAGES = [
  { key: "locking" as const, label: "Locking Seats" },
  { key: "booking" as const, label: "Creating Booking" },
  { key: "payment" as const, label: "Payment" },
];

function formatTime(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export default function CheckoutPage() {
  const { showId } = useParams<{ showId: string }>();
  const navigate = useNavigate();
  const {
    bookingId,
    selectedSeatIds,
    queueToken,
    setQueueToken,
    setLockedSeats,
    setBookingResult,
    reset: resetBookingFlow,
  } = useBookingFlow();
  const [localIdempotencyKey, setLocalIdempotencyKey] = useState<string | null>(null);
  const [queueValidated, setQueueValidated] = useState(false);

  const [stage, setStage] = useState<CheckoutStage>("locking");
  const [error, setError] = useState("");
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  const [timeLeft, setTimeLeft] = useState<number | null>(null);
  const [seatPrices, setSeatPrices] = useState<SeatResponse[]>([]);
  const [processing, setProcessing] = useState(false);
  const [cardNumber, setCardNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [cvc, setCvc] = useState("");
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stageIndex = STAGES.findIndex((s) => s.key === stage);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!expiresAt) return;
    const tick = () => {
      const remaining = Math.max(
        0,
        Math.floor((expiresAt - Date.now()) / 1000),
      );
      setTimeLeft(remaining);
      if (remaining <= 0) {
        clearTimer();
        toast.error("Booking expired");
        navigate(`/events/${showId}`);
      }
    };
    tick();
    timerRef.current = setInterval(tick, 1000);
    return clearTimer;
  }, [expiresAt, clearTimer, navigate, showId]);

  // Validate queue session
  useEffect(() => {
    if (!showId) return;
    let cancelled = false;

    const validate = async () => {
      if (!queueToken) {
        setQueueValidated(true);
        return;
      }
      try {
        const { data } = await queueApi.recoverQueue(showId);
        if (cancelled) return;
        if (data.status === "admitted" && data.queue_token) {
          setQueueToken(data.queue_token, showId);
          setQueueValidated(true);
        } else {
          setQueueToken("", undefined);
          toast.error("Queue session expired. Rejoining queue...");
          navigate(`/queue/${showId}`);
        }
      } catch {
        if (!cancelled) {
          setQueueValidated(true);
        }
      }
    };

    validate();
    return () => { cancelled = true; };
  }, [showId, queueToken, setQueueToken, navigate]);

  // Lock all selected seats
  useEffect(() => {
    if (!showId || selectedSeatIds.length === 0 || stage !== "locking" || !queueValidated) return;
    let cancelled = false;

    const lock = async () => {
      try {
        const { data } = await bookingApi.lockSeats({
          show_id: showId,
          seat_ids: selectedSeatIds,
        });
        if (cancelled) return;

        setLockedSeats(data.locked_seat_ids, data.idempotency_key, showId);
        setLocalIdempotencyKey(data.idempotency_key);
        setExpiresAt(new Date(data.expires_at).getTime());
        setStage("booking");
      } catch (err) {
        if (!cancelled) {
          const axiosErr = err as AxiosError<{ detail?: string }>;
          const detail = axiosErr.response?.data?.detail;
          const status = axiosErr.response?.status ?? (err as { status?: number }).status;
          if (status === 409) {
            setError(detail ?? "One or more seats are no longer available.");
          } else {
            setError("Failed to lock seats.");
          }
        }
      }
    };

    lock();
    return () => {
      cancelled = true;
    };
  }, [showId, selectedSeatIds, stage, queueValidated, setLockedSeats]);

  // Create booking
  useEffect(() => {
    if (!showId || selectedSeatIds.length === 0 || stage !== "booking" || !localIdempotencyKey) return;

    if (!queueToken) {
      setError("Queue session expired. Please rejoin the queue.");
      return;
    }

    let cancelled = false;

    const book = async () => {
      try {
        const result = await bookingApi.bookSeats(
          {
            show_id: showId,
            seat_ids: selectedSeatIds,
            idempotency_key: localIdempotencyKey,
          },
          queueToken,
        );
        if (cancelled) return;
        setBookingResult(result.data.booking_id);
        setStage("payment");
      } catch (err) {
        if (!cancelled) {
          const axiosErr = err as AxiosError<{ detail?: string }>;
          const detail = axiosErr.response?.data?.detail;
          setError(detail ?? "Failed to create booking.");
        }
      }
    };

    book();
    return () => {
      cancelled = true;
    };
  }, [
    stage,
    showId,
    selectedSeatIds,
    localIdempotencyKey,
    queueToken,
    setBookingResult,
  ]);

  // Fetch seat prices for display
  useEffect(() => {
    if (!showId || selectedSeatIds.length === 0 || stage !== "payment") return;
    catalogApi
      .getSeatMap(showId)
      .then((r) => {
        const selected = r.data.seats.filter((s) =>
          selectedSeatIds.includes(s.seat_id),
        );
        setSeatPrices(selected);
      })
      .catch(() => {});
  }, [showId, selectedSeatIds, stage]);

  const totalPrice = seatPrices.reduce((sum, s) => sum + parseFloat(s.price), 0);

  const formatCardNumber = (val: string) => {
    const digits = val.replace(/\D/g, "").slice(0, 16);
    return digits.replace(/(.{4})/g, "$1 ").trim();
  };

  const formatExpiry = (val: string) => {
    const digits = val.replace(/\D/g, "").slice(0, 4);
    if (digits.length > 2) return digits.slice(0, 2) + "/" + digits.slice(2);
    return digits;
  };

  const handlePayment = async () => {
    if (!cardNumber || !expiry || !cvc) {
      toast.error("Please fill in all card details.");
      return;
    }
    if (!bookingId) {
      toast.error("No booking to confirm.");
      return;
    }
    setProcessing(true);
    try {
      await new Promise((r) => setTimeout(r, 2000));
      await confirmApi.mockConfirm(bookingId);
      setStage("complete");
      resetBookingFlow();
      setTimeout(() => navigate("/account"), 1500);
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail?: string }>;
      const status = axiosErr.response?.status ?? (err as { status?: number }).status;
      const detail = axiosErr.response?.data?.detail;
      if (status === 409) {
        setError("Booking has expired. Please start over.");
      } else {
        setError(detail ?? "Payment confirmation failed. Please try again.");
      }
    } finally {
      setProcessing(false);
    }
  };

  const timerColor =
    timeLeft !== null
      ? timeLeft < 60
        ? "text-red-400"
        : timeLeft < 180
          ? "text-amber-400"
          : "text-muted-foreground"
      : "text-muted-foreground";

  if (error) {
    return (
      <PageTransition>
        <div className="min-h-screen flex items-center justify-center px-4">
          <div className="p-8 w-full max-w-md text-center space-y-4 rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl">
            <AlertCircle className="h-8 w-8 mx-auto text-red-400" />
            <p className="text-muted-foreground">{error}</p>
            <Button asChild variant="outline" className="rounded-full">
              <Link to={`/events/${showId}`}>Back to Events</Link>
            </Button>
          </div>
        </div>
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <div className="min-h-screen px-4 py-16 md:py-24">
        <div className="max-w-lg mx-auto space-y-8">
          {/* Countdown Timer */}
          {timeLeft !== null && stage !== "complete" && (
            <div
              className={cn(
                "flex items-center justify-end gap-1.5 text-sm font-mono",
                timerColor,
              )}
            >
              <Clock className="h-4 w-4" />
              Time remaining: {formatTime(timeLeft)}
            </div>
          )}

          {/* Stepper */}
          <div className="p-6 rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl">
            <div className="flex items-center justify-between">
              {STAGES.map((s, i) => (
                <div key={s.key} className="flex items-center">
                  <div className="flex flex-col items-center gap-1.5">
                    <div
                      className={cn(
                        "h-9 w-9 rounded-full flex items-center justify-center text-sm font-medium transition-all duration-300",
                        i < stageIndex
                          ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                          : i === stageIndex
                            ? "bg-primary/15 text-primary ring-2 ring-primary/30"
                            : "bg-muted/50 text-muted-foreground",
                      )}
                    >
                      {i < stageIndex ? (
                        <Check className="h-4 w-4" />
                      ) : (
                        i + 1
                      )}
                    </div>
                    <span className="text-[10px] text-muted-foreground/60 whitespace-nowrap font-medium">
                      {s.label}
                    </span>
                  </div>
                  {i < STAGES.length - 1 && (
                    <div
                      className={cn(
                        "h-0.5 w-12 mx-3 mb-5 transition-colors duration-300",
                        i < stageIndex ? "bg-primary" : "bg-muted/30",
                      )}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Selected seats summary */}
          {selectedSeatIds.length > 0 && stage !== "complete" && (
            <div className="p-4 rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl">
              <div className="flex items-center gap-2 mb-2">
                <Ticket className="h-4 w-4 text-primary" />
                <span className="text-sm font-medium">
                  {selectedSeatIds.length} seat{selectedSeatIds.length !== 1 ? "s" : ""}: {selectedSeatIds.join(", ")}
                </span>
              </div>
            </div>
          )}

          {/* Stage Content */}
          <AnimatePresence mode="wait">
            {stage === "locking" && (
              <motion.div
                key="locking"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="p-8 text-center space-y-4 rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl"
              >
                <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
                <p className="text-muted-foreground">Securing your seats...</p>
              </motion.div>
            )}

            {stage === "booking" && (
              <motion.div
                key="booking"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="p-8 text-center space-y-4 rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl"
              >
                <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
                <p className="text-muted-foreground">Creating your booking...</p>
              </motion.div>
            )}

            {stage === "payment" && !processing && (
              <motion.div
                key="payment-form"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.4, ease: PREMIUM_EASE }}
                className="p-8 space-y-6 rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl"
              >
                <div className="flex items-center gap-2.5">
                  <div className="flex items-center justify-center h-9 w-9 rounded-xl bg-primary/10">
                    <CreditCard className="h-4 w-4 text-primary" />
                  </div>
                  <h2 className="text-xl font-semibold tracking-tight">
                    Complete Payment
                  </h2>
                </div>

                {seatPrices.length > 0 && (
                  <div className="space-y-2">
                    {seatPrices.map((s) => (
                      <div key={s.seat_id} className="flex justify-between text-sm">
                        <span className="text-muted-foreground">
                          Seat {s.seat_id}
                          <span className="ml-1 text-[10px] uppercase text-muted-foreground/60">
                            {s.tier}
                          </span>
                        </span>
                        <span className="font-mono">₹{parseFloat(s.price).toFixed(2)}</span>
                      </div>
                    ))}
                    <div className="h-px bg-white/[0.06] my-2" />
                    <div className="flex justify-between font-bold">
                      <span>Total</span>
                      <span className="text-gradient text-lg">₹{totalPrice.toFixed(2)}</span>
                    </div>
                  </div>
                )}

                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label className="text-muted-foreground text-xs font-medium">Card Number</Label>
                    <Input
                      placeholder="4242 4242 4242 4242"
                      value={cardNumber}
                      onChange={(e) => setCardNumber(formatCardNumber(e.target.value))}
                      maxLength={19}
                      inputMode="numeric"
                      className="rounded-xl font-mono tracking-wider"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label className="text-muted-foreground text-xs font-medium">Expiry</Label>
                      <Input
                        placeholder="MM/YY"
                        value={expiry}
                        onChange={(e) => setExpiry(formatExpiry(e.target.value))}
                        maxLength={5}
                        inputMode="numeric"
                        className="rounded-xl font-mono tracking-wider"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-muted-foreground text-xs font-medium">CVC</Label>
                      <Input
                        placeholder="123"
                        value={cvc}
                        onChange={(e) => setCvc(e.target.value.replace(/\D/g, "").slice(0, 4))}
                        maxLength={4}
                        inputMode="numeric"
                        className="rounded-xl font-mono tracking-wider"
                      />
                    </div>
                  </div>
                </div>

                <Button
                  onClick={handlePayment}
                  className="w-full"
                  size="lg"
                  disabled={processing}
                >
                  Pay ₹{totalPrice.toFixed(2)}
                </Button>
              </motion.div>
            )}

            {stage === "payment" && processing && (
              <motion.div
                key="processing"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="p-8 text-center space-y-6 rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl"
              >
                <div className="h-1.5 w-full rounded-full overflow-hidden bg-muted/30">
                  <motion.div
                    className="h-full bg-gradient-to-r from-primary/60 via-primary to-primary/60 rounded-full"
                    animate={{
                      opacity: [0.5, 1, 0.5],
                      backgroundPosition: ["0% 50%", "100% 50%", "0% 50%"],
                    }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                  />
                </div>
                <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
                <p className="text-muted-foreground">Processing payment...</p>
              </motion.div>
            )}

            {stage === "complete" && (
              <motion.div
                key="complete"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, ease: PREMIUM_EASE }}
                className="p-8 text-center space-y-5 rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl"
              >
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 200, damping: 15 }}
                  className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-primary/15"
                >
                  <Check className="h-10 w-10 text-primary" />
                </motion.div>
                <h2 className="text-xl font-bold text-primary">
                  Payment successful!
                </h2>
                <p className="text-muted-foreground">Your booking is confirmed.</p>
                <Button asChild variant="outline" className="mt-2 rounded-full">
                  <Link to="/account">View your bookings</Link>
                </Button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </PageTransition>
  );
}
