import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  CalendarDays,
  Clock,
  Film,
  MapPin,
  Ticket,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageTransition } from "@/components/layout/page-transition";
import { catalogApi } from "@/lib/api-routes";
import type { ShowtimeResponse } from "@/types/api";

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

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function EventSkeleton() {
  return (
    <Card className="overflow-hidden">
      <div className="h-1 bg-muted/30" />
      <CardHeader className="space-y-3">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-4 w-full" />
      </CardHeader>
      <CardContent className="space-y-3">
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-2/3" />
      </CardContent>
    </Card>
  );
}

function ShowtimeSkeleton() {
  return (
    <Card>
      <CardContent className="py-5 space-y-3">
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-4 w-1/3" />
      </CardContent>
    </Card>
  );
}

export default function EventPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const navigate = useNavigate();

  const {
    data: events,
    isLoading: eventsLoading,
    error: eventsError,
  } = useQuery({
    queryKey: ["events"],
    queryFn: () => catalogApi.getEvents().then((r) => r.data),
  });

  const {
    data: venues,
    error: venuesError,
  } = useQuery({
    queryKey: ["venues"],
    queryFn: () => catalogApi.getVenues().then((r) => r.data),
  });

  const {
    data: showtimes,
    isLoading: showtimesLoading,
    error: showtimesError,
  } = useQuery({
    queryKey: ["eventShowtimes", eventId],
    queryFn: () => catalogApi.getShowtimesByEvent(eventId!).then((r) => r.data),
    enabled: !!eventId,
  });

  if (eventsError || venuesError || showtimesError) {
    toast.error("Failed to load event details. Please try again.");
  }

  const event = events?.find((e) => e.event_id === eventId);
  const isMovie = event?.event_type === "MOVIE";

  const accentBar = isMovie
    ? "from-amber-500 via-orange-400 to-amber-500"
    : "from-emerald-500 via-teal-400 to-emerald-500";
  const badgeClasses = isMovie
    ? "bg-amber-500/10 text-amber-500 border border-amber-500/20"
    : "bg-primary/10 text-primary border border-primary/20";
  const typeColor = isMovie ? "text-amber-500" : "text-primary";

  const venueMap = new Map<string, string>();
  venues?.forEach((v) => venueMap.set(v.venue_id, v.name));

  const sortedShowtimes: ShowtimeResponse[] = [...(showtimes ?? [])].sort(
    (a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime(),
  );

  return (
    <PageTransition>
      <div className="min-h-screen py-16 md:py-24">
        <motion.div
          className="max-w-4xl mx-auto px-6"
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

          {eventsLoading ? (
            <motion.div variants={childVariants}>
              <EventSkeleton />
            </motion.div>
          ) : event ? (
            <motion.div variants={childVariants}>
              <Card className="mb-10 overflow-hidden">
                <div className={`h-1 bg-gradient-to-r ${accentBar}`} />
                <CardHeader>
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-[10px] font-mono uppercase tracking-wider px-2.5 py-0.5 rounded-full ${badgeClasses}`}>
                      {event.event_id}
                    </span>
                    <span className={`text-[10px] font-mono uppercase tracking-wider px-2.5 py-0.5 rounded-full ${badgeClasses}`}>
                      {isMovie ? "Movie" : "Event"}
                    </span>
                  </div>
                  <CardTitle className="text-2xl md:text-3xl tracking-tight flex items-center gap-3">
                    {isMovie ? (
                      <Film className={`h-6 w-6 ${typeColor} shrink-0`} />
                    ) : (
                      <CalendarDays className={`h-6 w-6 ${typeColor} shrink-0`} />
                    )}
                    {event.name}
                  </CardTitle>
                  {event.description && (
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {event.description}
                    </p>
                  )}
                </CardHeader>
                <CardContent>
                  <div className="flex flex-col sm:flex-row sm:items-center gap-6">
                    <div className="flex items-start gap-3">
                      <div className={`flex items-center justify-center h-9 w-9 rounded-xl bg-primary/10 shrink-0`}>
                        <MapPin className={`h-4 w-4 ${typeColor}`} />
                      </div>
                      <div>
                        <p className="text-[10px] text-muted-foreground/60 uppercase tracking-wider font-medium">
                          Venues
                        </p>
                        <p className="text-sm font-medium mt-1">
                          {sortedShowtimes.length > 0
                            ? [...new Set(sortedShowtimes.map((st) => venueMap.get(st.venue_id)))]
                                .filter(Boolean)
                                .join(", ") || "TBA"
                            : "TBA"}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3 sm:ml-auto">
                      <div className={`flex items-center justify-center h-9 w-9 rounded-xl bg-primary/10 shrink-0`}>
                        <Ticket className={`h-4 w-4 ${typeColor}`} />
                      </div>
                      <div>
                        <p className="text-[10px] text-muted-foreground/60 uppercase tracking-wider font-medium">
                          Showtimes
                        </p>
                        <p className="text-sm font-medium mt-1">
                          {sortedShowtimes.length} available
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ) : (
            !eventsLoading && (
              <motion.div variants={childVariants}>
                <Card>
                  <CardContent className="py-16 text-center text-muted-foreground">
                    <p className="text-lg font-semibold">Event not found</p>
                    <p className="text-sm mt-1">It may have been removed from the catalog.</p>
                  </CardContent>
                </Card>
              </motion.div>
            )
          )}

          <motion.div variants={childVariants} className="mb-8">
            <h2 className="text-2xl font-bold tracking-tight">Select Showtime</h2>
            <p className="text-sm text-muted-foreground">
              Pick a date and time to view the seat map and book tickets.
            </p>
          </motion.div>

          {showtimesLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <motion.div key={i} variants={childVariants}>
                  <ShowtimeSkeleton />
                </motion.div>
              ))}
            </div>
          ) : sortedShowtimes.length > 0 ? (
            <div className="space-y-4">
              {sortedShowtimes.map((st) => (
                <motion.div key={st.show_id} variants={childVariants}>
                  <Card className="overflow-hidden group">
                    <CardContent className="p-5">
                      <div className="flex flex-col lg:flex-row lg:items-center gap-5">
                        <div className="flex items-center gap-4">
                          <div className="flex flex-col items-center justify-center h-14 w-14 rounded-2xl bg-primary/10 shrink-0">
                            <Clock className={`h-5 w-5 ${typeColor}`} />
                          </div>
                          <div>
                            <p className="text-sm font-semibold">
                              {formatDateTime(st.start_time)}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              ends {formatDateTime(st.end_time)}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 lg:ml-6">
                          <MapPin className="h-3.5 w-3.5 text-muted-foreground" />
                          <span className="text-sm text-muted-foreground">
                            {venueMap.get(st.venue_id) ?? st.venue_id.slice(0, 8)}
                          </span>
                        </div>

                        <div className="lg:ml-auto flex items-center gap-5">
                          <span className="text-xl font-bold">
                            <span className="text-gradient">
                              ₹{parseFloat(st.base_price).toFixed(2)}
                            </span>
                          </span>
                          <Button
                            onClick={() => navigate(`/events/${st.show_id}`)}
                            className="rounded-full"
                          >
                            <Ticket className="h-4 w-4 mr-2" />
                            Select Show
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ))}
            </div>
          ) : (
            !showtimesLoading && (
              <motion.div variants={childVariants}>
                <Card>
                  <CardContent className="py-16 text-center text-muted-foreground">
                    <p className="text-lg font-semibold">No showtimes available</p>
                    <p className="text-sm mt-1">
                      Check back soon — new showtimes are added regularly.
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            )
          )}
        </motion.div>
      </div>
    </PageTransition>
  );
}
