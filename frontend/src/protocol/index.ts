/**
 * The protocol between backend and frontend.
 *
 * The types are generated from the backend's models (`pnpm gen:types`), so they
 * cannot drift from what the server sends. Import from here, not from the
 * generated file.
 */
import type { Event } from "./murdertown.gen";

export type * from "./murdertown.gen";

export type Payload = Event["payload"];

export type PayloadOf<T extends Payload["type"]> = Extract<Payload, { type: T }>;
