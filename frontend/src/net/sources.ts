/**
 * Where a console's events come from. Watching live and replaying differ only in this: a live
 * game streams over a socket, a finished one is read whole from the server, and a game file is
 * read with no server at all.
 */
import { eventsInGameFile } from "../core/gameFile";
import type { Event, EventPage } from "../protocol";
import { API_URL, fetchJson, Refusal } from "./fetchJson";
import { followGame } from "./followGame";

/** How much of a game a page may see: only what the whole town saw, or everything. */
export type Scope = "public" | "full";

/**
 * How a source is doing. `ended`: everything has arrived (a live game's stream ends with
 * the game). `refused`: the server did not accept the Host token. `unavailable`: a replay's
 * events could not be read.
 */
export type ConnectionStatus = "connecting" | "live" | "reconnecting" | "ended" | "refused" | "unavailable";

/** Where a source sends what arrives, and how it is doing. */
export interface Sink {
  receive(events: readonly Event[]): void;
  status(status: ConnectionStatus): void;
}

/** Starts sending events to the sink; returns a function that stops it. */
export type EventSource = (sink: Sink) => () => void;

/** A game as it is played: with the Host token, in full scope; without, in public scope. */
export function liveSource(gameId: string, hostToken: string | null, apiUrl = API_URL): EventSource {
  return (sink) => followGame(gameId, sink, { apiUrl, hostToken });
}

/** A game's whole stored log, read once, in the scope the Host token allows. */
export function replaySource(gameId: string, hostToken: string | null, apiUrl = API_URL): EventSource {
  return readOnce(async () => {
    const page = await fetchJson<EventPage>(`${apiUrl}/games/${gameId}/events`, "replay the game", { hostToken });
    return page.events;
  });
}

/** A game file, from wherever it is served. */
export function fileSource(url: string): EventSource {
  return readOnce(async () => {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Could not read the game file (${response.status}).`);
    return eventsInGameFile(await response.text());
  });
}

function readOnce(read: () => Promise<Event[]>): EventSource {
  return (sink) => {
    let stopped = false;
    sink.status("connecting");
    read().then(
      (events) => {
        if (stopped) return;
        sink.receive(events);
        sink.status("ended");
      },
      (error: unknown) => {
        if (!stopped) sink.status(error instanceof Refusal && error.status === 401 ? "refused" : "unavailable");
      },
    );
    return () => {
      stopped = true;
    };
  };
}
