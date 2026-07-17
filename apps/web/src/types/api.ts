export interface SignupRequest {
  email: string;
  password: string;
}

export interface SignupResponse {
  user_id: string;
  email: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  is_admin: boolean;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface OAuthAuthorizeResponse {
  authorize_url: string;
  state: string;
}

export interface VenueResponse {
  venue_id: string;
  name: string;
  capacity: number;
}

export type EventType = "MOVIE" | "EVENT";

export interface EventResponse {
  event_id: string;
  event_type: EventType;
  name: string;
  description: string | null;
}

export interface ShowtimeResponse {
  show_id: string;
  event_id: string;
  venue_id: string;
  base_price: string;
  start_time: string;
  end_time: string;
}

export interface SeatResponse {
  seat_id: string;
  tier: string;
  price: string;
  status: "AVAILABLE" | "PENDING_PAYMENT" | "SOLD";
}

export interface SeatMapResponse {
  show_id: string;
  seats: SeatResponse[];
}

export interface QueueJoinRequest {
  show_id: string;
}

export interface QueueJoinResponse {
  queue_token: string | null;
  position: number;
  status: "waiting" | "admitted";
}

export interface QueueStatusResponse {
  position: number | null;
  status: "waiting" | "admitted" | "expired";
  retry_after: number | null;
  queue_token: string | null;
}

export interface QueueRecoverResponse {
  queue_token: string | null;
  status: "admitted" | "none";
}

export interface SeatLockRequest {
  show_id: string;
  seat_ids: string[];
}

export interface SeatLockResponse {
  idempotency_key: string;
  expires_at: string;
  locked_seat_ids: string[];
}

export interface BookRequest {
  show_id: string;
  seat_ids: string[];
  idempotency_key: string;
}

export interface BookResponse {
  booking_id: string;
  status: string;
  expires_at: string;
}

export interface PaymentIntentRequest {
  booking_id: string;
}

export interface PaymentIntentResponse {
  payment_id: string;
  client_secret: string;
  status: string;
}

export interface MockConfirmResponse {
  booking_id: string;
  status: string;
  seat_ids: string[];
}

export interface BookingSeatInfo {
  seat_id: string;
  tier: string;
  price: string;
}

export interface BookingListItem {
  booking_id: string;
  status: string;
  seats: BookingSeatInfo[];
  amount: string;
  currency: string;
  created_at: string | null;
  show_id: string;
  start_time: string | null;
  end_time: string | null;
  event_name: string;
  venue_name: string;
}

export interface EventCreateRequest {
  event_type: EventType;
  name: string;
  description?: string;
}

export interface VenueCreateRequest {
  name: string;
  capacity: number;
}

export interface ShowtimeCreateRequest {
  event_id: string;
  venue_id: string;
  base_price: number;
  start_time: string;
  end_time: string;
  auto_seats?: boolean;
}
