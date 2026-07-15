import { Link } from "react-router-dom";
import { Ticket, LogOut } from "lucide-react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/stores/auth-store";

export default function Navbar() {
  const { isAuthenticated, logout } = useAuth();

  return (
    <motion.header
      initial={{ y: -64, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: [0.32, 0.72, 0, 1] }}
      className="fixed top-0 left-0 right-0 z-50 glass-panel h-16 border-b border-white/[0.04]"
    >
      <div className="max-w-7xl mx-auto flex items-center justify-between px-6 h-full">
        <Link to="/" className="flex items-center gap-2.5 group">
          <div className="flex items-center justify-center h-8 w-8 rounded-xl bg-primary/10 border border-primary/20 group-hover:bg-primary/15 transition-colors">
            <Ticket className="h-4 w-4 text-primary" />
          </div>
          <span className="font-bold text-lg tracking-tight">StageTicket</span>
        </Link>

        <nav className="flex items-center gap-1">
          {!isAuthenticated ? (
            <>
              <Button variant="ghost" asChild className="rounded-full">
                <Link to="/login">Sign in</Link>
              </Button>
              <Button asChild className="rounded-full">
                <Link to="/signup">Get Started</Link>
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" asChild className="rounded-full">
                <Link to="/">Events</Link>
              </Button>
              <Button variant="ghost" asChild className="rounded-full">
                <Link to="/account">Account</Link>
              </Button>
              <Button variant="ghost" onClick={logout} className="rounded-full">
                <LogOut className="h-4 w-4 mr-2" />
                Log out
              </Button>
            </>
          )}
        </nav>
      </div>
    </motion.header>
  );
}
