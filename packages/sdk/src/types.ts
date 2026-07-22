/**
 * Generated types from OpenAPI spec.
 * Source of truth: packages/sdk/openapi.json
 *
 * Re-exported as flat, ergonomic names for downstream consumers.
 * Re-run `pnpm generate` when the backend schema changes.
 */
import type { components } from "./generated/api";

export type { components, operations, paths } from "./generated/api";

type S = components["schemas"];

// ── Auth ──────────────────────────────────────────────
export type SignupRequest = S["SignupRequest"];
export type SignupResponse = S["SignupResponse"];
export type LoginRequest = S["LoginRequest"];
export type LoginResponse = S["LoginResponse"];
export type RefreshRequest = S["RefreshRequest"];
export type OAuthAuthorizeResponse = S["OAuthAuthorizeResponse"];

// ── Catalog ───────────────────────────────────────────
export type VenueResponse = S["VenueResponse"];
export type EventResponse = S["EventResponse"];
export type ShowtimeResponse = S["ShowtimeResponse"];
export type SeatResponse = S["SeatResponse"];
export type SeatMapResponse = S["SeatMapResponse"];

// ── Queue ─────────────────────────────────────────────
export type QueueJoinRequest = S["QueueJoinRequest"];
export type QueueJoinResponse = S["QueueJoinResponse"];
export type QueueStatusResponse = S["QueueStatusResponse"];
export type QueueRecoverResponse = S["QueueRecoverResponse"];

// ── Seat Lock ─────────────────────────────────────────
export type SeatLockRequest = S["SeatLockRequest"];
export type SeatLockResponse = S["SeatLockResponse"];

// ── Booking ───────────────────────────────────────────
export type BookRequest = S["BookRequest"];
export type BookResponse = S["BookResponse"];
export type MockConfirmResponse = S["MockConfirmResponse"];
export type BookingSeatInfo = S["BookingSeatInfo"];
export type BookingListItem = S["BookingListItem"];

// ── Payment ───────────────────────────────────────────
export type PaymentIntentRequest = S["PaymentIntentRequest"];
export type PaymentIntentResponse = S["PaymentIntentResponse"];

// ── Admin ─────────────────────────────────────────────
export type EventCreateRequest = S["EventCreateRequest"];
export type VenueCreateRequest = S["VenueCreateRequest"];
export type ShowtimeCreateRequest = S["ShowtimeCreateRequest"];

// ── Enums ─────────────────────────────────────────────
export type EventType = "MOVIE" | "EVENT";
export type SeatStatus = "AVAILABLE" | "PENDING_PAYMENT" | "SOLD";
export type BookingStatus = "PENDING" | "CONFIRMED" | "FAILED" | "CANCELLED";
