import { createContext, useCallback, useContext, useState } from "react";

const QUEUE_TOKEN_KEY = "ets_queue_token";
const QUEUE_SHOW_KEY = "ets_queue_show_id";
const SELECTED_SEATS_KEY = "ets_selected_seats";

interface BookingFlowState {
  showId: string | null;
  selectedSeatIds: string[];
  queueToken: string | null;
  queueShowId: string | null;
  bookingId: string | null;
  idempotencyKey: string | null;
}

interface BookingFlowContextValue extends BookingFlowState {
  setShowId: (showId: string) => void;
  setQueueToken: (token: string, showId?: string) => void;
  toggleSeat: (showId: string, seatId: string) => void;
  clearSelectedSeats: () => void;
  setLockedSeats: (seatIds: string[], idempotencyKey: string, showId: string) => void;
  setBookingResult: (bookingId: string) => void;
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

function readPersistedQueueShowId(): string | null {
  try {
    return localStorage.getItem(QUEUE_SHOW_KEY);
  } catch {
    return null;
  }
}

function readPersistedSeatIds(): string[] {
  try {
    const raw = localStorage.getItem(SELECTED_SEATS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function BookingFlowProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<BookingFlowState>({
    showId: null,
    selectedSeatIds: readPersistedSeatIds(),
    queueToken: readPersistedQueueToken(),
    queueShowId: readPersistedQueueShowId(),
    bookingId: null,
    idempotencyKey: null,
  });

  const setShowId = useCallback((showId: string) => {
    setState((prev) => ({ ...prev, showId }));
  }, []);

  const setQueueToken = useCallback((token: string, showId?: string) => {
    try {
      localStorage.setItem(QUEUE_TOKEN_KEY, token);
      if (showId) {
        localStorage.setItem(QUEUE_SHOW_KEY, showId);
      }
    } catch {
      // storage unavailable
    }
    setState((prev) => ({
      ...prev,
      queueToken: token,
      queueShowId: showId ?? prev.queueShowId,
    }));
  }, []);

  const toggleSeat = useCallback((showId: string, seatId: string) => {
    setState((prev) => {
      const currentSeatIds = prev.showId === showId ? prev.selectedSeatIds : [];
      const isSelected = currentSeatIds.includes(seatId);
      const nextSeatIds = isSelected
        ? currentSeatIds.filter((id) => id !== seatId)
        : [...currentSeatIds, seatId];

      try {
        if (nextSeatIds.length > 0) {
          localStorage.setItem(SELECTED_SEATS_KEY, JSON.stringify(nextSeatIds));
        } else {
          localStorage.removeItem(SELECTED_SEATS_KEY);
        }
      } catch {
        // storage unavailable
      }

      return {
        ...prev,
        showId,
        selectedSeatIds: nextSeatIds,
      };
    });
  }, []);

  const clearSelectedSeats = useCallback(() => {
    try {
      localStorage.removeItem(SELECTED_SEATS_KEY);
    } catch {
      // storage unavailable
    }
    setState((prev) => ({ ...prev, selectedSeatIds: [] }));
  }, []);

  const setLockedSeats = useCallback((seatIds: string[], idempotencyKey: string, showId: string) => {
    setState((prev) => ({
      ...prev,
      showId,
      selectedSeatIds: seatIds,
      idempotencyKey,
    }));
  }, []);

  const setBookingResult = useCallback((bookingId: string) => {
    setState((prev) => ({ ...prev, bookingId }));
  }, []);

  const reset = useCallback(() => {
    try {
      localStorage.removeItem(QUEUE_TOKEN_KEY);
      localStorage.removeItem(QUEUE_SHOW_KEY);
      localStorage.removeItem(SELECTED_SEATS_KEY);
    } catch {
      // storage unavailable
    }
    setState({
      showId: null,
      selectedSeatIds: [],
      queueToken: null,
      queueShowId: null,
      bookingId: null,
      idempotencyKey: null,
    });
  }, []);

  return (
    <BookingFlowContext.Provider
      value={{
        ...state,
        setShowId,
        setQueueToken,
        toggleSeat,
        clearSelectedSeats,
        setLockedSeats,
        setBookingResult,
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
