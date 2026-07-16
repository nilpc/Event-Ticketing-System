import { motion } from "framer-motion";

const PREMIUM_EASE = [0.32, 0.72, 0, 1] as const;

const pageVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.4, ease: PREMIUM_EASE } },
  exit: { opacity: 0, transition: { duration: 0.25, ease: PREMIUM_EASE } },
};

export function PageTransition({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      variants={pageVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
    >
      {children}
    </motion.div>
  );
}
