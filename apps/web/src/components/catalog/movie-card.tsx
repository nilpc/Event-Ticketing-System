import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Film, ArrowUpRight } from "lucide-react";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import type { EventResponse } from "@/types/api";

const PREMIUM_EASE = [0.32, 0.72, 0, 1] as const;

const cardVariants = {
  hidden: { opacity: 0, y: 24, scale: 0.97 },
  visible: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.5, ease: PREMIUM_EASE } },
};

interface MovieCardProps {
  event: EventResponse;
}

export function MovieCard({ event }: MovieCardProps) {
  const navigate = useNavigate();

  const openCard = () => {
    navigate(`/event/${event.event_id}`);
  };

  return (
    <motion.div variants={cardVariants}>
      <Card
        className="h-full group overflow-hidden hover:shadow-xl hover:shadow-amber-500/5 transition-all duration-500 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
        onClick={openCard}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            openCard();
          }
        }}
      >
        {/* Premium accent bar */}
        <div className="h-1 bg-gradient-to-r from-amber-500 via-orange-400 to-amber-500" />

        <CardHeader className="pb-3">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] font-mono uppercase tracking-wider bg-amber-500/10 text-amber-500 px-2 py-0.5 rounded-full border border-amber-500/20">
              {event.event_id}
            </span>
            <span className="text-[10px] font-mono uppercase tracking-wider bg-amber-500/10 text-amber-500 px-2 py-0.5 rounded-full border border-amber-500/20">
              Movie
            </span>
          </div>
          <CardTitle className="text-lg group-hover:text-amber-500 transition-colors duration-300 flex items-center gap-2">
            <Film className="h-5 w-5 text-amber-500 shrink-0" />
            {event.name}
            <ArrowUpRight className="h-4 w-4 text-amber-500 ml-auto opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300" />
          </CardTitle>
        </CardHeader>

        {event.description && (
          <CardContent className="pt-0">
            <p className="text-sm text-muted-foreground line-clamp-2 leading-relaxed">
              {event.description}
            </p>
          </CardContent>
        )}

        <CardContent className="pt-0">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
            View showtimes
          </p>
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
