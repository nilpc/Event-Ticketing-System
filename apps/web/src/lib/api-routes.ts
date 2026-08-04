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
  EventUpdateRequest,
  VenueCreateRequest,
  VenueUpdateRequest,
  ShowtimeCreateRequest,
  ShowtimeUpdateRequest,
  UserPromoteResponse,
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
  getAllShowtimes() {
    return api.get<ShowtimeResponse[]>("/showtimes");
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
  syncPayment(paymentId: string) {
    return api.post<{ payment_id: string; payment_status: string; booking_id: string; booking_status: string }>(
      `/payments/${paymentId}/sync`,
    );
  },
};

export const confirmApi = {
  mockConfirm(bookingId: string) {
    return api.post<MockConfirmResponse>(`/book/${bookingId}/mock-confirm`);
  },
};

export const adminApi = {
  promoteUser(userId: string) {
    return api.post<UserPromoteResponse>(`/admin/users/${userId}/promote`);
  },
  createEvent(data: EventCreateRequest) {
    return api.post<EventResponse>("/admin/events", data);
  },
  updateEvent(eventId: string, data: EventUpdateRequest) {
    return api.put<EventResponse>(`/admin/events/${eventId}`, data);
  },
  deleteEvent(eventId: string) {
    return api.delete<void>(`/admin/events/${eventId}`);
  },
  createVenue(data: VenueCreateRequest) {
    return api.post<VenueResponse>("/admin/venues", data);
  },
  updateVenue(venueId: string, data: VenueUpdateRequest) {
    return api.put<VenueResponse>(`/admin/venues/${venueId}`, data);
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
  updateShowtime(showId: string, data: ShowtimeUpdateRequest) {
    return api.put<ShowtimeResponse>(`/admin/showtimes/${showId}`, data);
  },
  deleteShowtime(showId: string) {
    return api.delete<void>(`/admin/showtimes/${showId}`);
  },
};
