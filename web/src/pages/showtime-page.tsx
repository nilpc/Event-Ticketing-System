import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import {
  CalendarDays,
  Clock,
  DollarSign,
  MapPin,
  ArrowLeft,
  Lock,
  CheckCircle2,
  XCircle,
  Users,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageTransition } from "@/components/layout/page-transition";
import { catalogApi } from "@/lib/api-routes";
import { useAuth } from "@/stores/auth-store";
import { useBookingFlow } from "@/stores/booking-store";
import type { SeatResponse } from "@/types/api";

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

const seatVariants = {
  hidden: { opacity: 0, scale: 0.8 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.35, ease: PREMIUM_EASE } },
};

function SeatSkeleton() {
  return <Skeleton className="h-11 w-11 rounded-xl" />;
}

function InfoSkeleton() {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="space-y-3">
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-4 w-1/2" />
      </CardHeader>
      <CardContent className="space-y-3">
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-8 w-24" />
      </CardContent>
    </Card>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function groupSeatsByTier(seats: SeatResponse[]): Record<string, SeatResponse[]> {
  const grouped: Record<string, SeatResponse[]> = {};
  for (const seat of seats) {
    if (!grouped[seat.tier]) {
      grouped[seat.tier] = [];
    }
    grouped[seat.tier].push(seat);
  }
  const sorted: Record<string, SeatResponse[]> = {};
  for (const tier of Object.keys(grouped).sort()) {
    sorted[tier] = grouped[tier].sort((a, b) => a.seat_id.localeCompare(b.seat_id));
  }
  return sorted;
}

function seatButtonClasses(status: SeatResponse["status"]): string {
  switch (status) {
    case "AVAILABLE":
      return "bg-primary/15 border border-primary/25 text-primary hover:bg-primary/30 hover:border-primary/40 cursor-pointer hover:shadow-lg hover:shadow-primary/10";
    case "PENDING_PAYMENT":
      return "bg-amber-500/15 border border-amber-500/25 text-amber-400 cursor-not-allowed";
    case "SOLD":
      return "bg-muted/30 border border-white/[0.04] text-muted-foreground/40 cursor-not-allowed";
  }
}

function SeatIcon({ status }: { status: SeatResponse["status"] }) {
  switch (status) {
    case "AVAILABLE":
      return <CheckCircle2 className="h-3 w-3" />;
    case "PENDING_PAYMENT":
      return <Lock className="h-3 w-3" />;
    case "SOLD":
      return <XCircle className="h-3 w-3" />;
  }
}

export default function ShowtimePage() {
  const { showId } = useParams<{ showId: string }>();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const { queueToken, selectSeat } = useBookingFlow();

  const {
    data: showtime,
    isLoading: showtimeLoading,
    error: showtimeError,
  } = useQuery({
    queryKey: ["showtime", showId],
    queryFn: () => catalogApi.getShowtime(showId!).then((r) => r.data),
    enabled: !!showId,
  });

  const {
    data: seatMap,
    isLoading: seatMapLoading,
    error: seatMapError,
  } = useQuery({
    queryKey: ["seatMap", showId],
    queryFn: () => catalogApi.getSeatMap(showId!).then((r) => r.data),
    enabled: !!showId,
  });

  if (showtimeError || seatMapError) {
    toast.error("Failed to load showtime details. Please try again.");
  }

  const handleSeatClick = (seat: SeatResponse) => {
    if (seat.status !== "AVAILABLE") return;
    if (!isAuthenticated) {
      toast.info("Please sign in to purchase tickets.");
      navigate("/login");
      return;
    }
    if (!queueToken) {
      toast.error("Please join the queue first before selecting a seat.");
      return;
    }
    selectSeat(showId!, seat.seat_id, queueToken);
    navigate(`/checkout/${showId}/${seat.seat_id}`);
  };

  const groupedSeats = seatMap ? groupSeatsByTier(seatMap.seats) : {};
  const availableCount = seatMap?.seats.filter((s) => s.status === "AVAILABLE").length ?? 0;
  const soldCount = seatMap?.seats.filter((s) => s.status === "SOLD").length ?? 0;
  const pendingCount = seatMap?.seats.filter((s) => s.status === "PENDING_PAYMENT").length ?? 0;

  return (
    <PageTransition>
      <div className="min-h-screen py-16 md:py-24">
        <motion.div
          className="max-w-6xl mx-auto px-6"
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          <motion.div variants={childVariants} className="mb-10">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/")}
              className="text-muted-foreground hover:text-foreground rounded-full"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Catalog
            </Button>
          </motion.div>

          {showtimeLoading ? (
            <InfoSkeleton />
          ) : showtime ? (
            <motion.div variants={childVariants}>
              <Card className="mb-10 overflow-hidden">
                <CardHeader>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] font-mono uppercase tracking-wider bg-primary/10 text-primary px-2.5 py-0.5 rounded-full border border-primary/20">
                      {showtime.show_id.slice(0, 8)}
                    </span>
                  </div>
                  <CardTitle className="text-2xl tracking-tight">Showtime</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                    <div className="flex items-start gap-3">
                      <div className="flex items-center justify-center h-9 w-9 rounded-xl bg-primary/10 shrink-0">
                        <CalendarDays className="h-4 w-4 text-primary" />
                      </div>
                      <div>
                        <p className="text-[10px] text-muted-foreground/60 uppercase tracking-wider font-medium">Date</p>
                        <p className="text-sm font-medium mt-1">
                          {formatDate(showtime.start_time)}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-start gap-3">
                      <div className="flex items-center justify-center h-9 w-9 rounded-xl bg-primary/10 shrink-0">
                        <Clock className="h-4 w-4 text-primary" />
                      </div>
                      <div>
                        <p className="text-[10px] text-muted-foreground/60 uppercase tracking-wider font-medium">Duration</p>
                        <p className="text-sm font-medium mt-1">
                          {formatDate(showtime.start_time)} - {formatDate(showtime.end_time)}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-start gap-3">
                      <div className="flex items-center justify-center h-9 w-9 rounded-xl bg-primary/10 shrink-0">
                        <MapPin className="h-4 w-4 text-primary" />
                      </div>
                      <div>
                        <p className="text-[10px] text-muted-foreground/60 uppercase tracking-wider font-medium">Venue</p>
                        <p className="text-sm font-medium mt-1 font-mono">
                          {showtime.venue_id.slice(0, 8)}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-start gap-3">
                      <div className="flex items-center justify-center h-9 w-9 rounded-xl bg-primary/10 shrink-0">
                        <DollarSign className="h-4 w-4 text-primary" />
                      </div>
                      <div>
                        <p className="text-[10px] text-muted-foreground/60 uppercase tracking-wider font-medium">Base Price</p>
                        <p className="text-xl font-bold mt-1">
                          <span className="text-gradient">
                            ₹{parseFloat(showtime.base_price).toFixed(2)}
                          </span>
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ) : null}

          {showtime && (
            <motion.div variants={childVariants} className="mb-10">
              <Card className="overflow-hidden">
                <CardContent className="py-6">
                  {queueToken ? (
                    <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                      <div>
                        <h3 className="text-lg font-semibold text-primary">
                          You&apos;re admitted!
                        </h3>
                        <p className="text-sm text-muted-foreground">
                          Select an available seat below to proceed to checkout.
                        </p>
                      </div>
                      <CheckCircle2 className="h-6 w-6 text-primary shrink-0" />
                    </div>
                  ) : (
                    <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                      <div>
                        <h3 className="text-lg font-semibold">Ready to book?</h3>
                        <p className="text-sm text-muted-foreground">
                          {isAuthenticated
                            ? "Join the queue to get access to seat selection."
                            : "Sign in and join the queue to get access to seat selection."}
                        </p>
                      </div>
                      <Button
                        onClick={() => {
                          if (!isAuthenticated) {
                            toast.info("Please sign in to join the queue.");
                            navigate("/login");
                            return;
                          }
                          navigate(`/queue/${showId}`);
                        }}
                        className="shrink-0"
                      >
                        <Users className="h-4 w-4 mr-2" />
                        Join Queue
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          )}

          <motion.div variants={childVariants}>
            <div className="flex items-center gap-3 mb-8">
              <h2 className="text-2xl font-bold tracking-tight">Seat Map</h2>
              {!seatMapLoading && seatMap && (
                <div className="flex items-center gap-4 text-xs text-muted-foreground ml-auto">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-primary/60" />
                    {availableCount} available
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-500/60" />
                    {pendingCount} pending
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-muted-foreground/30" />
                    {soldCount} sold
                  </span>
                </div>
              )}
            </div>
          </motion.div>

          {seatMapLoading ? (
            <div className="space-y-8">
              {[1, 2, 3].map((section) => (
                <motion.div key={section} variants={childVariants}>
                  <Skeleton className="h-5 w-24 mb-4" />
                  <div className="flex flex-wrap gap-2">
                    {Array.from({ length: 12 }).map((_, i) => (
                      <SeatSkeleton key={i} />
                    ))}
                  </div>
                </motion.div>
              ))}
            </div>
          ) : seatMap ? (
            <motion.div
              className="space-y-10"
              variants={containerVariants}
              initial="hidden"
              animate="visible"
            >
              {Object.entries(groupedSeats).map(([tier, seats]) => (
                <motion.div key={tier} variants={childVariants}>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/60 mb-4 flex items-center gap-3">
                    <span className="h-px flex-1 bg-white/[0.04]" />
                    <span>{tier}</span>
                    <span className="h-px flex-1 bg-white/[0.04]" />
                  </h3>
                  <div className="flex flex-wrap gap-2 justify-center">
                    {seats.map((seat) => (
                      <motion.button
                        key={seat.seat_id}
                        variants={seatVariants}
                        whileHover={seat.status === "AVAILABLE" ? { scale: 1.08, y: -2 } : {}}
                        whileTap={seat.status === "AVAILABLE" ? { scale: 0.95 } : {}}
                        className={`relative flex flex-col items-center justify-center h-11 w-12 rounded-xl text-xs font-mono transition-all duration-200 ${seatButtonClasses(seat.status)}`}
                        onClick={() => handleSeatClick(seat)}
                        disabled={seat.status !== "AVAILABLE"}
                        title={
                          seat.status === "AVAILABLE"
                            ? `${seat.seat_id} - ₹${parseFloat(seat.price).toFixed(2)}`
                            : seat.status === "PENDING_PAYMENT"
                              ? `${seat.seat_id} - Pending`
                              : `${seat.seat_id} - Sold`
                        }
                      >
                        <SeatIcon status={seat.status} />
                        <span className="mt-0.5 text-[9px] leading-none">{seat.seat_id}</span>
                      </motion.button>
                    ))}
                  </div>
                </motion.div>
              ))}
            </motion.div>
          ) : (
            <div className="text-center py-20 text-muted-foreground">
              <p>No seat data available for this showtime.</p>
            </div>
          )}

          <motion.div variants={childVariants} className="mt-16">
            <Card className="overflow-hidden">
              <CardContent className="py-6">
                <div className="flex flex-col sm:flex-row items-center justify-center gap-6 text-sm text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <span className="h-3 w-3 rounded-lg bg-primary/20 border border-primary/30" />
                    <span>Available</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="h-3 w-3 rounded-lg bg-amber-500/20 border border-amber-500/30" />
                    <span>Pending Payment</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="h-3 w-3 rounded-lg bg-muted/30 border border-white/[0.04]" />
                    <span>Sold</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </motion.div>
      </div>
    </PageTransition>
  );
}
