import { useState } from "react";
import { motion } from "framer-motion";
import { CreditCard, Loader2 } from "lucide-react";
import { toast } from "sonner";
import type { AxiosError } from "axios";
import {
  PaymentElement,
  useStripe,
  useElements,
} from "@stripe/react-stripe-js";
import type { StripeError } from "@stripe/stripe-js";
import { Button } from "@/components/ui/button";
import { paymentApi } from "@/lib/api-routes";
const PREMIUM_EASE = [0.32, 0.72, 0, 1] as const;
interface StripePaymentFormProps {
  totalPrice: number;
  paymentId: string;
  onSuccess: () => void;
  onError: (msg: string) => void;
}
export default function StripePaymentForm({
  totalPrice,
  paymentId,
  onSuccess,
  onError,
}: StripePaymentFormProps) {
  const stripe = useStripe();
  const elements = useElements();
  const [processing, setProcessing] = useState(false);
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stripe || !elements) return;
    setProcessing(true);
    try {
      const { error, paymentIntent } = await stripe.confirmPayment({
        elements,
        confirmParams: {
          return_url: window.location.origin + "/account",
        },
        redirect: "if_required",
      });
      if (error) {
        const msg = handleStripeError(error);
        onError(msg);
        toast.error(msg);
        setProcessing(false);
        return;
      }
      if (paymentIntent && paymentIntent.status === "succeeded") {
        let syncOk = false;
        try {
          const syncRes = await paymentApi.syncPayment(paymentId);
          syncOk = syncRes.data.booking_status === "CONFIRMED";
        } catch (syncErr) {
          console.error("syncPayment failed:", syncErr);
          toast.warning(
            "Payment captured by Stripe. If your booking doesn't appear in a few seconds, please refresh your account page.",
          );
        }
        if (syncOk) {
          toast.success("Payment successful! Your booking is confirmed.");
        } else if (!syncOk) {
          toast.info("Payment received — confirming your booking...");
        }
        onSuccess();
      } else {
        const msg = "Payment confirmation failed. Please try again.";
        onError(msg);
        toast.error(msg);
      }
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail?: string }>;
      const msg = axiosErr.response?.data?.detail ?? "Payment failed. Please try again.";
      onError(msg);
      toast.error(msg);
    } finally {
      setProcessing(false);
    }
  };
  return (
    <motion.form
      onSubmit={handleSubmit}
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
      <PaymentElement
        options={{
          layout: "tabs",
          paymentMethodOrder: ["card"],
          wallets: { link: "never" },
        }}
      />
      <Button
        type="submit"
        className="w-full"
        size="lg"
        disabled={!stripe || !elements || processing}
      >
        {processing ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Processing...
          </>
        ) : (
          `Pay \u20B9${totalPrice.toFixed(2)}`
        )}
      </Button>
    </motion.form>
  );
}
function handleStripeError(error: StripeError): string {
  switch (error.type) {
    case "card_error":
    case "validation_error":
      return error.message ?? "Invalid card details.";
    default:
      return "Payment failed. Please try again.";
  }
}
