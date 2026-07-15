import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useQuery, useQueries } from "@tanstack/react-query";
import {
  CalendarDays,
  Film,
  Ticket,
  Search,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageTransition } from "@/components/layout/page-transition";
import { catalogApi } from "@/lib/api-routes";
import { MovieCard } from "@/components/catalog/movie-card";
import { EventCard } from "@/components/catalog/event-card";
import type { EventResponse, VenueResponse, ShowtimeResponse } from "@/types/api";

const PREMIUM_EASE = [0.32, 0.72, 0, 1] as const;

const containerVariants = {
  hidden: { opacity: 0, y: 32 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: PREMIUM_EASE, staggerChildren: 0.1 },
  },
};

const childVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: PREMIUM_EASE } },
};

function CardSkeleton() {
  return (
    <Card className="overflow-hidden">
      <div className="h-48 bg-muted/30 animate-pulse" />
      <CardHeader className="space-y-3">
        <Skeleton className="h-5 w-3/4" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-2/3" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-4 w-1/2" />
      </CardContent>
    </Card>
  );
}

type TabType = "all" | "movies" | "events";

export default function CatalogPage() {
  const navigate = useNavigate();
  const [showtimeInput, setShowtimeInput] = useState("");
  const [activeTab, setActiveTab] = useState<TabType>("all");

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

  const showtimeQueries = useQueries({
    queries: (events ?? []).map((event) => ({
      queryKey: ["showtimes", event.event_id],
      queryFn: () =>
        catalogApi.getShowtimesByEvent(event.event_id).then((r) => r.data),
      enabled: !!events,
    })),
  });

  const showtimesByEvent = new Map<string, ShowtimeResponse[]>();
  showtimeQueries.forEach((q, i) => {
    if (q.data && events?.[i]) {
      showtimesByEvent.set(events[i].event_id, q.data);
    }
  });

  const venueMap = new Map<string, VenueResponse>();
  venues?.forEach((v) => venueMap.set(v.venue_id, v));

  if (eventsError || venuesError) {
    toast.error("Failed to load catalog data. Please try again.");
  }

  const movies = events?.filter((e) => e.event_type === "MOVIE") ?? [];
  const liveEvents = events?.filter((e) => e.event_type === "EVENT") ?? [];

  const filteredEvents =
    activeTab === "movies"
      ? movies
      : activeTab === "events"
        ? liveEvents
        : events ?? [];

  const handleShowtimeSearch = async () => {
    const trimmed = showtimeInput.trim();
    if (!trimmed) return;

    const isPrefixedId = /^(STE|STM)\d{2,}$/i.test(trimmed);
    if (isPrefixedId) {
      try {
        const res = await catalogApi.getShowtimesByEvent(trimmed.toUpperCase());
        const showtimes = res.data;
        if (showtimes.length > 0) {
          navigate(`/events/${showtimes[0].show_id}`);
        } else {
          toast.error("No showtimes found for this event.");
        }
      } catch {
        toast.error("Event not found. Check the ID and try again.");
      }
    } else {
      navigate(`/events/${trimmed}`);
    }
  };

  const lookupId = showtimeInput.trim().toUpperCase();
  const isPrefixedId = /^(STE|STM)\d{2,}$/.test(lookupId);
  const matchedEvent = isPrefixedId
    ? events?.find((e) => e.event_id === lookupId)
    : null;

  const tabs: { key: TabType; label: string; icon: React.ReactNode; count: number }[] = [
    { key: "all", label: "All", icon: <Zap className="h-3.5 w-3.5" />, count: events?.length ?? 0 },
    { key: "movies", label: "Movies", icon: <Film className="h-3.5 w-3.5" />, count: movies.length },
    { key: "events", label: "Events", icon: <CalendarDays className="h-3.5 w-3.5" />, count: liveEvents.length },
  ];

  return (
    <PageTransition>
      <div className="min-h-screen">
        {/* Hero - cinematic spacing */}
        <motion.section
          className="relative py-32 md:py-48 overflow-hidden"
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="h-[800px] w-[800px] rounded-full bg-primary/[0.03] blur-[120px]" />
          </div>

          <div className="relative max-w-4xl mx-auto px-6 text-center">
            <motion.div variants={childVariants} className="mb-6">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium border border-primary/20">
                <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
                Live Now
              </span>
            </motion.div>
            <motion.h1
              variants={childVariants}
              className="text-5xl md:text-7xl font-bold tracking-tight mb-6 leading-[0.95]"
            >
              <span className="text-gradient">Discover</span>
              <br />
              <span className="text-foreground/90">Live Events</span>
            </motion.h1>
            <motion.p
              variants={childVariants}
              className="text-lg md:text-xl text-muted-foreground max-w-xl mx-auto leading-relaxed"
            >
              Secure your seats before they sell out.
            </motion.p>
          </div>
        </motion.section>

        {/* Tabs + Content */}
        <motion.section
          className="max-w-6xl mx-auto px-6 pb-24"
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-100px" }}
        >
          {/* Tab Bar - pill design */}
          <motion.div variants={childVariants} className="flex items-center gap-4 mb-10">
            <h2 className="text-2xl font-bold tracking-tight">Browse</h2>

            <div className="ml-auto flex gap-1 bg-muted/30 p-1 rounded-full border border-white/[0.04]">
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-medium transition-all duration-300 ${
                    activeTab === tab.key
                      ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                  <span className={`text-xs ${activeTab === tab.key ? "text-primary-foreground/70" : "text-muted-foreground/60"}`}>
                    {tab.count}
                  </span>
                </button>
              ))}
            </div>
          </motion.div>

          {/* Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {eventsLoading
              ? Array.from({ length: 3 }).map((_, i) => (
                  <motion.div key={i} variants={childVariants}>
                    <CardSkeleton />
                  </motion.div>
                ))
              : filteredEvents.map((event: EventResponse) => {
                  const showtimes = showtimesByEvent.get(event.event_id) ?? [];

                  if (event.event_type === "MOVIE") {
                    return (
                      <MovieCard
                        key={event.event_id}
                        event={event}
                        showtimes={showtimes}
                        venueMap={venueMap}
                      />
                    );
                  }

                  return (
                    <EventCard
                      key={event.event_id}
                      event={event}
                      showtimes={showtimes}
                      venueMap={venueMap}
                    />
                  );
                })}
          </div>

          {!eventsLoading && filteredEvents.length === 0 && (
            <div className="text-center py-20 text-muted-foreground">
              <p>No {activeTab === "all" ? "" : activeTab} found.</p>
            </div>
          )}
        </motion.section>

        {/* Search by ID */}
        <motion.section
          className="max-w-6xl mx-auto px-6 pb-32"
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-100px" }}
        >
          <motion.div variants={childVariants}>
            <Card className="overflow-hidden">
              <CardHeader className="text-center pt-8">
                <div className="flex items-center justify-center h-12 w-12 rounded-2xl bg-primary/10 mx-auto mb-3">
                  <Ticket className="h-6 w-6 text-primary" />
                </div>
                <CardTitle className="text-xl">Search by ID</CardTitle>
                <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                  Enter an event ID (STE01, STM02) or showtime ID to view seats and book tickets.
                </p>
              </CardHeader>
              <CardContent className="pb-8">
                <div className="flex gap-3 max-w-md mx-auto">
                  <Input
                    placeholder="e.g. STE01, STM02"
                    value={showtimeInput}
                    onChange={(e) => setShowtimeInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleShowtimeSearch()}
                    className="font-mono text-sm rounded-full"
                  />
                  <Button
                    onClick={handleShowtimeSearch}
                    disabled={!showtimeInput.trim()}
                  >
                    <Search className="h-4 w-4" />
                  </Button>
                </div>

                {isPrefixedId && showtimeInput.trim() && (
                  <div className="mt-4 max-w-md mx-auto">
                    {matchedEvent ? (
                      <div className="flex items-center gap-3 p-3 rounded-xl bg-muted/30 border border-white/[0.04]">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${
                            matchedEvent.event_type === "MOVIE"
                              ? "bg-amber-500/10 text-amber-500 border border-amber-500/20"
                              : "bg-primary/10 text-primary border border-primary/20"
                          }`}
                        >
                          {matchedEvent.event_type === "MOVIE" ? (
                            <Film className="h-3 w-3" />
                          ) : (
                            <CalendarDays className="h-3 w-3" />
                          )}
                          {matchedEvent.event_type === "MOVIE" ? "Movie" : "Event"}
                        </span>
                        <span className="font-medium text-sm">{matchedEvent.name}</span>
                        <span className="ml-auto text-xs text-muted-foreground font-mono">
                          {matchedEvent.event_id}
                        </span>
                      </div>
                    ) : (
                      !eventsLoading && (
                        <p className="text-xs text-destructive text-center">
                          No event found for &quot;{lookupId}&quot;
                        </p>
                      )
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </motion.section>
      </div>
    </PageTransition>
  );
}
