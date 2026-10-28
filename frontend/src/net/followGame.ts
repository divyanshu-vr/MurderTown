/**
 * Follows one game over WebSocket, surviving disconnects.
 *
 * The server replays everything after the last sequence number we hold, then
 * streams new events. Reconnecting with that number, and dropping anything
 * already seen, means the caller never gets a gap or a duplicate.
 *
 * With the Host token the socket asks for full scope, sending the token as its first
 * message (a browser cannot put a header on a socket); without it, public scope.
 */
import { endsTheGame } from "../core/gameView";
import type { Event } from "../protocol";
import { API_URL } from "./fetchJson";

/** `refused`: the server did not accept the Host token, so following stopped. */
export type ConnectionStatus = "connecting" | "live" | "reconnecting" | "ended" | "refused";

/** How much of a game a page may see: only what the whole town saw, or everything. */
export type Scope = "public" | "full";

export interface GameFollower {
  onEvent(event: Event): void;
  onStatus(status: ConnectionStatus): void;
}

const MAX_BACKOFF_MS = 5000;

/** How the server closes a socket that did not send the Host token (its `NOT_THE_HOST`). */
const NOT_THE_HOST = 4401;

interface Following {
  apiUrl?: string;
  hostToken?: string | null;
}

/** Start following a game. Returns a function that stops following it. */
export function followGame(
  gameId: string,
  follower: GameFollower,
  { apiUrl = API_URL, hostToken = null }: Following = {},
): () => void {
  let lastSeq = 0;
  let attempt = 0;
  let stopped = false;
  let socket: WebSocket | null = null;
  let retry: ReturnType<typeof setTimeout> | undefined;

  const connect = () => {
    const scope = hostToken ? "&scope=full" : "";
    const opening = new WebSocket(`${apiUrl.replace(/^http/, "ws")}/ws/games/${gameId}?after=${lastSeq}${scope}`);
    socket = opening;
    opening.onopen = () => {
      if (hostToken) opening.send(hostToken);
      attempt = 0;
      follower.onStatus("live");
    };
    opening.onmessage = (message: MessageEvent<string>) => {
      const event = JSON.parse(message.data) as Event;
      if (event.seq <= lastSeq) return;
      lastSeq = event.seq;
      follower.onEvent(event);
      if (endsTheGame(event)) {
        stopped = true;
        follower.onStatus("ended");
      }
    };
    opening.onclose = (closed: { code: number }) => {
      if (stopped) return;
      if (closed.code === NOT_THE_HOST) {
        stopped = true;
        follower.onStatus("refused");
        return;
      }
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
