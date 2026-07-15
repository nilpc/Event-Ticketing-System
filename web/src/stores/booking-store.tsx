import { createContext, useCallback, useContext, useState } from "react";

interface BookingFlowState {
  showId: string | null;
  seatId: string | null;
  queueToken: string | null;
  bookingId: string | null;
  paymentClientSecret: string | null;
}

interface BookingFlowContextValue extends BookingFlowState {
  setShowId: (showId: string) => void;
  setQueueToken: (token: string) => void;
  selectSeat: (showId: string, seatId: string, queueToken: string) => void;
  setBookingResult: (bookingId: string) => void;
  setPaymentResult: (clientSecret: string) => void;
  reset: () => void;
}

const BookingFlowContext = createContext<BookingFlowContextValue | null>(null);

export function BookingFlowProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<BookingFlowState>({
    showId: null,
    seatId: null,
    queueToken: null,
    bookingId: null,
    paymentClientSecret: null,
  });

  const setShowId = useCallback((showId: string) => {
    setState((prev) => ({ ...prev, showId }));
  }, []);

  const setQueueToken = useCallback((token: string) => {
    setState((prev) => ({ ...prev, queueToken: token }));
  }, []);

  const selectSeat = useCallback((showId: string, seatId: string, queueToken: string) => {
    setState((prev) => ({
      ...prev,
      showId,
      seatId,
      queueToken,
    }));
  }, []);

  const setBookingResult = useCallback((bookingId: string) => {
    setState((prev) => ({ ...prev, bookingId }));
  }, []);

  const setPaymentResult = useCallback((clientSecret: string) => {
    setState((prev) => ({ ...prev, paymentClientSecret: clientSecret }));
  }, []);

  const reset = useCallback(() => {
    setState({
      showId: null,
      seatId: null,
      queueToken: null,
      bookingId: null,
      paymentClientSecret: null,
    });
  }, []);

  return (
    <BookingFlowContext.Provider
      value={{
        ...state,
        setShowId,
        setQueueToken,
        selectSeat,
        setBookingResult,
        setPaymentResult,
        reset,
      }}
    >
      {children}
    </BookingFlowContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useBookingFlow(): BookingFlowContextValue {
  const context = useContext(BookingFlowContext);
  if (!context) {
    throw new Error("useBookingFlow must be used within a BookingFlowProvider");
  }
  return context;
}
