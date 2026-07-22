/**
 * Typed API route functions.
 *
 * Each function accepts a pre-configured Axios instance and returns an
 * Axios Promise with the correct response type derived from the OpenAPI spec.
 *
 * Usage:
 *   import { createApiClient } from "@event-ticketing/sdk";
 *   import { authApi, catalogApi } from "@event-ticketing/sdk";
 *
 *   const client = createApiClient({ baseURL: "/v1", tokens: { ... } });
 *   const { data } = await authApi.login(client, { email, password });
 */

import type { AxiosInstance } from "axios";
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
  MockConfirmResponse,
  BookingListItem,
  PaymentIntentRequest,
  PaymentIntentResponse,
  EventCreateRequest,
  VenueCreateRequest,
  ShowtimeCreateRequest,
} from "./types";

// ── Auth ──────────────────────────────────────────────

export const authApi = {
  signup(client: AxiosInstance, data: SignupRequest) {
    return client.post<SignupResponse>("/auth/signup", data);
  },
  login(client: AxiosInstance, data: LoginRequest) {
    return client.post<LoginResponse>("/auth/login", data);
  },
  refresh(client: AxiosInstance, data: RefreshRequest) {
    return client.post<LoginResponse>("/auth/refresh", data);
  },
  logout(client: AxiosInstance, data: RefreshRequest) {
    return client.post<void>("/auth/logout", data);
  },
  getGoogleAuthUrl(client: AxiosInstance) {
    return client.get<OAuthAuthorizeResponse>("/auth/google/authorize");
  },
  handleGoogleCallback(client: AxiosInstance, code: string, state: string) {
    return client.get<LoginResponse>("/auth/google/callback", {
      params: { code, state },
    });
  },
  deleteAccount(client: AxiosInstance) {
    return client.delete<void>("/auth/me");
  },
  anonymizeAccount(client: AxiosInstance) {
    return client.post<void>("/auth/me/anonymize");
  },
};

// ── Catalog ───────────────────────────────────────────

export const catalogApi = {
  getVenues(client: AxiosInstance) {
    return client.get<VenueResponse[]>("/venues");
  },
  getEvents(client: AxiosInstance) {
    return client.get<EventResponse[]>("/events");
  },
  getShowtime(client: AxiosInstance, showId: string) {
    return client.get<ShowtimeResponse>(`/showtimes/${showId}`);
  },
  getSeatMap(client: AxiosInstance, showId: string) {
    return client.get<SeatMapResponse>(`/showtimes/${showId}/seats`);
  },
  getShowtimesByEvent(client: AxiosInstance, eventId: string) {
    return client.get<ShowtimeResponse[]>(`/events/${eventId}/showtimes`);
  },
};

// ── Queue ─────────────────────────────────────────────

export const queueApi = {
  joinQueue(client: AxiosInstance, data: QueueJoinRequest) {
    return client.post<QueueJoinResponse>("/queue/join", data);
  },
  getQueueStatus(client: AxiosInstance, showId: string) {
    return client.get<QueueStatusResponse>("/queue/status", {
      params: { show_id: showId },
    });
  },
  recoverQueue(client: AxiosInstance, showId: string) {
    return client.get<QueueRecoverResponse>("/queue/recover", {
      params: { show_id: showId },
    });
  },
};

// ── Seats ─────────────────────────────────────────────

export const seatApi = {
  lock(client: AxiosInstance, data: SeatLockRequest) {
    return client.post<SeatLockResponse>("/seats/lock", data);
  },
};

// ── Booking ───────────────────────────────────────────

export const bookingApi = {
  book(client: AxiosInstance, data: BookRequest, queueToken?: string) {
    const headers: Record<string, string> = {};
    if (queueToken) headers["X-Queue-Token"] = queueToken;
    return client.post<BookResponse>("/book", data, { headers });
  },
  mockConfirm(client: AxiosInstance, bookingId: string) {
    return client.post<MockConfirmResponse>(`/book/${bookingId}/mock-confirm`);
  },
  getUserBookings(client: AxiosInstance) {
    return client.get<BookingListItem[]>("/bookings");
  },
};

// ── Payment ───────────────────────────────────────────

export const paymentApi = {
  createIntent(client: AxiosInstance, data: PaymentIntentRequest) {
    return client.post<PaymentIntentResponse>("/payments/intent", data);
  },
};

// ── Admin ─────────────────────────────────────────────

export const adminApi = {
  createEvent(client: AxiosInstance, data: EventCreateRequest) {
    return client.post<EventResponse>("/admin/events", data);
  },
  deleteEvent(client: AxiosInstance, eventId: string) {
    return client.delete<void>(`/admin/events/${eventId}`);
  },
  createVenue(client: AxiosInstance, data: VenueCreateRequest) {
    return client.post<VenueResponse>("/admin/venues", data);
  },
  deleteVenue(client: AxiosInstance, venueId: string) {
    return client.delete<void>(`/admin/venues/${venueId}`);
  },
  getAllShowtimes(client: AxiosInstance) {
    return client.get<ShowtimeResponse[]>("/admin/showtimes");
  },
  createShowtime(client: AxiosInstance, data: ShowtimeCreateRequest) {
    return client.post<ShowtimeResponse>("/admin/showtimes", data);
  },
  deleteShowtime(client: AxiosInstance, showId: string) {
    return client.delete<void>(`/admin/showtimes/${showId}`);
  },
};
