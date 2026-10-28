/**
 * Follows one game over WebSocket, surviving disconnects.
 *
 * The server replays everything after the last sequence number we hold, then
 * streams new events. Reconnecting with that number, and dropping anything
 * already seen, means the caller never gets a gap or a duplicate.
 */
import type { Event } from "../protocol";

export type ConnectionStatus = "connecting" | "live" | "reconnecting" | "ended";

/** How much of a game a page may see: only what the whole town saw, or everything. */
export type Scope = "public" | "full";

export interface GameFollower {
  onEvent(event: Event): void;
  onStatus(status: ConnectionStatus): void;
}

export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

const MAX_BACKOFF_MS = 5000;

/** Start following a game. Returns a function that stops following it. */
export function followGame(gameId: string, follower: GameFollower, apiUrl = API_URL): () => void {
  let lastSeq = 0;
  let attempt = 0;
  let stopped = false;
  let socket: WebSocket | null = null;
  let retry: ReturnType<typeof setTimeout> | undefined;

  const connect = () => {
    const url = `${apiUrl.replace(/^http/, "ws")}/ws/games/${gameId}?after=${lastSeq}`;
    socket = new WebSocket(url);
    socket.onopen = () => {
      attempt = 0;
      follower.onStatus("live");
    };
    socket.onmessage = (message: MessageEvent<string>) => {
      const event = JSON.parse(message.data) as Event;
      if (event.seq <= lastSeq) return;
      lastSeq = event.seq;
      follower.onEvent(event);
      if (event.payload.type === "game_ended") {
        stopped = true;
        follower.onStatus("ended");
      }
    };
    socket.onclose = () => {
      if (stopped) return;
      follower.onStatus("reconnecting");
      retry = setTimeout(connect, Math.min(500 * 2 ** attempt++, MAX_BACKOFF_MS));
    };
  };

  follower.onStatus("connecting");
  connect();
  return () => {
    stopped = true;
    clearTimeout(retry);
    socket?.close();
  };
}
