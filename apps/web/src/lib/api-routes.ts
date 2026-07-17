import api from "./api";
import type {
  SignupRequest,
  SignupResponse,
  LoginRequest,
  LoginResponse,
  RefreshRequest,
  OAuthAuthorizeResponse,
  VenueResponse,
  EventResponse,
  ShowtimeResponse,
  SeatMapResponse,
  QueueJoinRequest,
  QueueJoinResponse,
  QueueStatusResponse,
  QueueRecoverResponse,
  SeatLockRequest,
  SeatLockResponse,
  BookRequest,
  BookResponse,
  PaymentIntentRequest,
  PaymentIntentResponse,
  MockConfirmResponse,
  BookingListItem,
  EventCreateRequest,
  VenueCreateRequest,
  ShowtimeCreateRequest,
} from "../types/api";

export const authApi = {
  signup(data: SignupRequest) {
    return api.post<SignupResponse>("/auth/signup", data);
  },
  login(data: LoginRequest) {
    return api.post<LoginResponse>("/auth/login", data);
  },
  refresh(data: RefreshRequest) {
    return api.post<LoginResponse>("/auth/refresh", data);
  },
  logout(data: RefreshRequest) {
    return api.post<void>("/auth/logout", data);
  },
  getGoogleAuthUrl() {
    return api.get<OAuthAuthorizeResponse>("/auth/google/authorize");
  },
  handleGoogleCallback(code: string, state: string) {
    return api.get<LoginResponse>("/auth/google/callback", { params: { code, state } });
  },
  deleteAccount() {
    return api.delete<void>("/auth/me");
  },
  anonymizeAccount() {
    return api.post<void>("/auth/me/anonymize");
  },
};

export const catalogApi = {
  getVenues() {
    return api.get<VenueResponse[]>("/venues");
  },
  getEvents() {
    return api.get<EventResponse[]>("/events");
  },
  getShowtime(showId: string) {
    return api.get<ShowtimeResponse>(`/showtimes/${showId}`);
  },
  getSeatMap(showId: string) {
    return api.get<SeatMapResponse>(`/showtimes/${showId}/seats`);
  },
  getShowtimesByEvent(eventId: string) {
    return api.get<ShowtimeResponse[]>(`/events/${eventId}/showtimes`);
  },
};

export const queueApi = {
  joinQueue(data: QueueJoinRequest) {
    return api.post<QueueJoinResponse>("/queue/join", data);
  },
  getQueueStatus(showId: string) {
    return api.get<QueueStatusResponse>("/queue/status", { params: { show_id: showId } });
  },
  recoverQueue(showId: string) {
    return api.get<QueueRecoverResponse>("/queue/recover", { params: { show_id: showId } });
  },
};

export const bookingApi = {
  lockSeats(data: SeatLockRequest) {
    return api.post<SeatLockResponse>("/seats/lock", data);
  },
  bookSeats(data: BookRequest, queueToken?: string) {
    const headers: Record<string, string> = {};
    if (queueToken) {
      headers["X-Queue-Token"] = queueToken;
    }
    return api.post<BookResponse>("/book", data, { headers });
  },
  getUserBookings() {
    return api.get<BookingListItem[]>("/bookings");
  },
};

export const paymentApi = {
  createIntent(data: PaymentIntentRequest) {
    return api.post<PaymentIntentResponse>("/payments/intent", data);
  },
};

export const confirmApi = {
  mockConfirm(bookingId: string) {
    return api.post<MockConfirmResponse>(`/book/${bookingId}/mock-confirm`);
  },
};

export const adminApi = {
  createEvent(data: EventCreateRequest) {
    return api.post<EventResponse>("/admin/events", data);
  },
  deleteEvent(eventId: string) {
    return api.delete<void>(`/admin/events/${eventId}`);
  },
  createVenue(data: VenueCreateRequest) {
    return api.post<VenueResponse>("/admin/venues", data);
  },
  deleteVenue(venueId: string) {
    return api.delete<void>(`/admin/venues/${venueId}`);
  },
  getAllShowtimes() {
    return api.get<ShowtimeResponse[]>("/admin/showtimes");
  },
  createShowtime(data: ShowtimeCreateRequest) {
    return api.post<ShowtimeResponse>("/admin/showtimes", data);
  },
  deleteShowtime(showId: string) {
    return api.delete<void>(`/admin/showtimes/${showId}`);
  },
};
