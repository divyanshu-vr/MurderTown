/** Transport, from the browser's side: following a game until it ends or is aborted. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Event } from "../protocol";
import { type ConnectionStatus, followGame } from "./followGame";

class FakeSocket {
  static opened: FakeSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((message: MessageEvent<string>) => void) | null = null;
  onclose: ((closed: { code: number }) => void) | null = null;
  readonly sent: string[] = [];

  constructor(readonly url: string) {
    FakeSocket.opened.push(this);
  }

  /** What the browser sends the server. */
  send(text: string) {
    this.sent.push(text);
  }

  /** The server sends an event. */
  receive(event: Partial<Event> & Pick<Event, "seq" | "payload">) {
    this.onmessage?.({ data: JSON.stringify(event) } as MessageEvent<string>);
  }

  close(code = 1000) {
    this.onclose?.({ code });
  }
}

function opened(index = 0): FakeSocket {
  const socket = FakeSocket.opened[index];
  if (!socket) throw new Error(`socket ${index} was never opened`);
  return socket;
}

function follow(hostToken: string | null = null) {
  const statuses: ConnectionStatus[] = [];
  followGame(
    "abc",
    { onEvent: () => undefined, onStatus: (status) => statuses.push(status) },
    { apiUrl: "http://api", hostToken },
  );
  return statuses;
}

beforeEach(() => {
  FakeSocket.opened = [];
  vi.useFakeTimers();
  vi.stubGlobal("WebSocket", FakeSocket);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("following a game", () => {
  it("stops after the game is aborted and never reconnects", () => {
    const statuses = follow();
    opened().onopen?.();

    opened().receive({ seq: 1, payload: { type: "game_aborted", reason: "no answer within 90 seconds" } });
    opened().close();
    vi.runAllTimers();

    expect(statuses.at(-1)).toBe("ended");
    expect(FakeSocket.opened).toHaveLength(1);
  });

  it("asks a Spectator's socket for public scope and sends nothing", () => {
    follow();
    opened().onopen?.();

    expect(opened().url).toBe("ws://api/ws/games/abc?after=0");
    expect(opened().sent).toEqual([]);
  });

  it("asks the Host's socket for full scope and sends the Host token first", () => {
    follow("s3cret");
    opened().onopen?.();

    expect(opened().url).toBe("ws://api/ws/games/abc?after=0&scope=full");
    expect(opened().sent).toEqual(["s3cret"]);
  });

  it("gives up when the server refuses the Host token", () => {
    const statuses = follow("wrong");
    opened().onopen?.();

    opened().close(4401);
    vi.runAllTimers();

    expect(statuses.at(-1)).toBe("refused");
    expect(FakeSocket.opened).toHaveLength(1);
  });
});
