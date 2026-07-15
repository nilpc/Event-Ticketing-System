import React, { Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AnimatePresence } from "framer-motion";
import { Toaster } from "sonner";
import { Loader2 } from "lucide-react";
import { AuthProvider } from "@/stores/auth-store";
import { BookingFlowProvider } from "@/stores/booking-store";
import Navbar from "@/components/layout/navbar";
import ProtectedRoute from "@/components/layout/protected-route";

const LoginPage = React.lazy(() => import("@/pages/login-page"));
const SignupPage = React.lazy(() => import("@/pages/signup-page"));
const GoogleCallbackPage = React.lazy(() => import("@/pages/google-callback-page"));
const CatalogPage = React.lazy(() => import("@/pages/catalog-page"));
const ShowtimePage = React.lazy(() => import("@/pages/showtime-page"));
const QueuePage = React.lazy(() => import("@/pages/queue-page"));
const CheckoutPage = React.lazy(() => import("@/pages/checkout-page"));
const AccountPage = React.lazy(() => import("@/pages/account-page"));

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

function Fallback() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <Loader2 className="animate-spin text-primary h-8 w-8" />
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BookingFlowProvider>
          <BrowserRouter>
            <div className="min-h-screen bg-background">
              <Navbar />
              <main className="pt-16">
                <AnimatePresence mode="wait">
                  <Suspense fallback={<Fallback />}>
                    <Routes>
                      <Route path="/login" element={<LoginPage />} />
                      <Route path="/signup" element={<SignupPage />} />
                      <Route path="/auth/callback" element={<GoogleCallbackPage />} />
                      <Route path="/" element={<CatalogPage />} />
                      <Route path="/events/:showId" element={<ShowtimePage />} />
                      <Route element={<ProtectedRoute />}>
                        <Route path="/checkout/:showId/:seatId" element={<CheckoutPage />} />
                        <Route path="/queue/:showId" element={<QueuePage />} />
                        <Route path="/account" element={<AccountPage />} />
                      </Route>
                    </Routes>
                  </Suspense>
                </AnimatePresence>
              </main>
            </div>
          </BrowserRouter>
        </BookingFlowProvider>
      </AuthProvider>
      <Toaster position="top-right" richColors closeButton />
    </QueryClientProvider>
  );
}
