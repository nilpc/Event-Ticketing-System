import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/stores/auth-store";
interface SeatUpdate {
  type: "seat_update";
  seat_id: string;
  status: "AVAILABLE" | "PENDING_PAYMENT" | "SOLD";
  locked_by: string | null;
}
interface UseSeatWebSocketOptions {
  showId: string;
  onSeatUpdate?: (update: SeatUpdate) => void;
  enabled?: boolean;
}
interface UseSeatWebSocketReturn {
  isConnected: boolean;
  reconnectCount: number;
}
const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY = 1000;
const MAX_RECONNECT_DELAY = 30000;
export function useSeatWebSocket({
  showId,
  onSeatUpdate,
  enabled = true,
}: UseSeatWebSocketOptions): UseSeatWebSocketReturn {
  const { isAuthenticated } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const attemptRef = useRef(0);
  const getReconnectDelay = useCallback(() => {
    const delay = Math.min(
      BASE_RECONNECT_DELAY * Math.pow(2, attemptRef.current),
      MAX_RECONNECT_DELAY,
    );
    return delay + Math.random() * 1000;
  }, []);
  const connect = useCallback(() => {
    if (!enabled || !isAuthenticated || !showId) return;
    const accessToken = localStorage.getItem("access_token");
    if (!accessToken) return;
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/showtime/${showId}?token=${accessToken}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onopen = () => {
      setIsConnected(true);
      attemptRef.current = 0;
      setReconnectCount(0);
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send("ping");
        } else {
          clearInterval(pingInterval);
        }
      }, 30000);
    };
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "seat_update" && onSeatUpdate) {
          onSeatUpdate(data as SeatUpdate);
        }
      } catch {
      }
    };
    ws.onclose = (event) => {
      setIsConnected(false);
      wsRef.current = null;
      if (event.code !== 1000 && attemptRef.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = getReconnectDelay();
        attemptRef.current += 1;
        setReconnectCount(attemptRef.current);
        reconnectTimerRef.current = setTimeout(() => {
          connect();
        }, delay);
      }
    };
    ws.onerror = () => {
      ws.close();
    };
  }, [showId, isAuthenticated, enabled, onSeatUpdate, getReconnectDelay]);
  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close(1000);
        wsRef.current = null;
      }
    };
  }, [connect]);
  return { isConnected, reconnectCount };
}
