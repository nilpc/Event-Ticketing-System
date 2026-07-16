import { createContext, useCallback, useContext, useState } from "react";

const QUEUE_TOKEN_KEY = "ets_queue_token";

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

function readPersistedQueueToken(): string | null {
  try {
    return localStorage.getItem(QUEUE_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function BookingFlowProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<BookingFlowState>({
    showId: null,
    seatId: null,
    queueToken: readPersistedQueueToken(),
    bookingId: null,
    paymentClientSecret: null,
  });

  const setShowId = useCallback((showId: string) => {
    setState((prev) => ({ ...prev, showId }));
  }, []);

  const setQueueToken = useCallback((token: string) => {
    try {
      localStorage.setItem(QUEUE_TOKEN_KEY, token);
    } catch {
      // storage unavailable
    }
    setState((prev) => ({ ...prev, queueToken: token }));
  }, []);

  const selectSeat = useCallback((showId: string, seatId: string, queueToken: string) => {
    try {
      localStorage.setItem(QUEUE_TOKEN_KEY, queueToken);
    } catch {
      // storage unavailable
    }
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
    try {
      localStorage.removeItem(QUEUE_TOKEN_KEY);
    } catch {
      // storage unavailable
    }
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
