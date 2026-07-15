import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { CalendarDays, Clock, MapPin, ArrowUpRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import type { EventResponse, ShowtimeResponse, VenueResponse } from "@/types/api";

const PREMIUM_EASE = [0.32, 0.72, 0, 1] as const;

const cardVariants = {
  hidden: { opacity: 0, y: 24, scale: 0.97 },
  visible: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.5, ease: PREMIUM_EASE } },
};

interface EventCardProps {
  event: EventResponse;
  showtimes: ShowtimeResponse[];
  venueMap: Map<string, VenueResponse>;
}

export function EventCard({ event, showtimes, venueMap }: EventCardProps) {
  const navigate = useNavigate();

  const venueNames = [
    ...new Set(
      showtimes
        .map((st) => venueMap.get(st.venue_id)?.name)
        .filter(Boolean),
    ),
  ];

  return (
    <motion.div variants={cardVariants}>
      <Card className="h-full group overflow-hidden hover:shadow-xl hover:shadow-primary/5 transition-all duration-500">
        {/* Premium accent bar */}
        <div className="h-1 bg-gradient-to-r from-emerald-500 via-teal-400 to-emerald-500" />

        <CardHeader className="pb-3">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] font-mono uppercase tracking-wider bg-primary/10 text-primary px-2 py-0.5 rounded-full border border-primary/20">
              {event.event_id}
            </span>
            <span className="text-[10px] font-mono uppercase tracking-wider bg-primary/10 text-primary px-2 py-0.5 rounded-full border border-primary/20">
              Event
            </span>
          </div>
          <CardTitle className="text-lg group-hover:text-primary transition-colors duration-300 flex items-center gap-2">
            <CalendarDays className="h-5 w-5 text-primary shrink-0" />
            {event.name}
            <ArrowUpRight className="h-4 w-4 ml-auto opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300 text-primary" />
          </CardTitle>
          {venueNames.length > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <MapPin className="h-3 w-3" />
              <span>{venueNames.join(", ")}</span>
            </div>
          )}
        </CardHeader>

        {event.description && (
          <CardContent className="pt-0">
            <p className="text-sm text-muted-foreground line-clamp-2 leading-relaxed">
              {event.description}
            </p>
          </CardContent>
        )}

        <CardContent className="pt-0">
          {showtimes.length > 0 ? (
            <div className="space-y-2.5">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                Showtimes
              </p>
              {showtimes.map((st) => (
                <div
                  key={st.show_id}
                  className="flex items-center justify-between text-sm group/row"
                >
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    <span className="text-xs">
                      {new Date(st.start_time).toLocaleString()}
                    </span>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => navigate(`/events/${st.show_id}`)}
                    className="h-7 px-2.5 rounded-full text-xs text-primary hover:bg-primary/10"
                  >
                    Get Tickets
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground/50">
              No showtimes available
            </p>
          )}
        </CardContent>

        <CardFooter className="pt-2">
          <div className="text-[10px] text-muted-foreground/40 font-mono">
            {event.event_id}
          </div>
        </CardFooter>
      </Card>
    </motion.div>
  );
}
