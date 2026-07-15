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
  lockSeat(data: SeatLockRequest) {
    return api.post<SeatLockResponse>("/seats/lock", data);
  },
  book(data: BookRequest, queueToken?: string) {
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
  getAdminToken(): string | null {
    return localStorage.getItem("admin_token");
  },
  setAdminToken(token: string) {
    localStorage.setItem("admin_token", token);
  },
  createEvent(data: EventCreateRequest) {
    const headers: Record<string, string> = {};
    const t = localStorage.getItem("admin_token");
    if (t) headers["X-Admin-Token"] = t;
    return api.post<EventResponse>("/admin/events", data, { headers });
  },
  deleteEvent(eventId: string) {
    const headers: Record<string, string> = {};
    const t = localStorage.getItem("admin_token");
    if (t) headers["X-Admin-Token"] = t;
    return api.delete<void>(`/admin/events/${eventId}`, { headers });
  },
  createVenue(data: VenueCreateRequest) {
    const headers: Record<string, string> = {};
    const t = localStorage.getItem("admin_token");
    if (t) headers["X-Admin-Token"] = t;
    return api.post<VenueResponse>("/admin/venues", data, { headers });
  },
  deleteVenue(venueId: string) {
    const headers: Record<string, string> = {};
    const t = localStorage.getItem("admin_token");
    if (t) headers["X-Admin-Token"] = t;
    return api.delete<void>(`/admin/venues/${venueId}`, { headers });
  },
  getAllShowtimes() {
    const headers: Record<string, string> = {};
    const t = localStorage.getItem("admin_token");
    if (t) headers["X-Admin-Token"] = t;
    return api.get<ShowtimeResponse[]>("/admin/showtimes", { headers });
  },
  createShowtime(data: ShowtimeCreateRequest) {
    const headers: Record<string, string> = {};
    const t = localStorage.getItem("admin_token");
    if (t) headers["X-Admin-Token"] = t;
    return api.post<ShowtimeResponse>("/admin/showtimes", data, { headers });
  },
  deleteShowtime(showId: string) {
    const headers: Record<string, string> = {};
    const t = localStorage.getItem("admin_token");
    if (t) headers["X-Admin-Token"] = t;
    return api.delete<void>(`/admin/showtimes/${showId}`, { headers });
  },
};
