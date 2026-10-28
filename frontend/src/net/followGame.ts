/**
 * Follows one game over WebSocket, surviving disconnects.
 *
 * The server replays everything after the last sequence number we hold, then
 * streams new events. Reconnecting with that number, dropping anything already
 * seen, and reconnecting on a gap means the caller never gets a gap or a duplicate.
 *
 * With the Host token the socket asks for full scope, sending the token as its first
 * message (a browser cannot put a header on a socket); without it, public scope.
 */
import { accept } from "../core/arrival";
import { endsTheGame } from "../core/gameView";
import type { Event } from "../protocol";
import { API_URL } from "./fetchJson";
import type { Sink } from "./sources";

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
  sink: Sink,
  { apiUrl = API_URL, hostToken = null }: Following = {},
): () => void {
  const full = Boolean(hostToken); // full scope sends every event, so a skipped one is a gap
  let lastSeq = 0;
  let attempt = 0;
  let stopped = false;
  let socket: WebSocket | null = null;
  let retry: ReturnType<typeof setTimeout> | undefined;

  const connect = () => {
    const scope = full ? "&scope=full" : "";
    const opening = new WebSocket(`${apiUrl.replace(/^http/, "ws")}/ws/games/${gameId}?after=${lastSeq}${scope}`);
    socket = opening;
    opening.onopen = () => {
      if (full && hostToken) opening.send(hostToken);
      attempt = 0;
      sink.status("live");
    };
    opening.onmessage = (message: MessageEvent<string>) => {
      const event = JSON.parse(message.data) as Event;
      const arrival = accept(lastSeq, event.seq, full);
      if (arrival === "duplicate") return;
      if (arrival === "gap") {
        opening.close(); // reconnecting asks again for everything after the last event held
        return;
      }
      lastSeq = event.seq;
      sink.receive([event]);
      if (endsTheGame(event)) {
        stopped = true;
        sink.status("ended");
      }
    };
    opening.onclose = (closed: { code: number }) => {
      if (stopped) return;
      if (closed.code === NOT_THE_HOST) {
        stopped = true;
        sink.status("refused");
        return;
      }
      sink.status("reconnecting");
      retry = setTimeout(connect, Math.min(500 * 2 ** attempt++, MAX_BACKOFF_MS));
    };
  };

  sink.status("connecting");
  connect();
  return () => {
    stopped = true;
    clearTimeout(retry);
    socket?.close();
  };
}
