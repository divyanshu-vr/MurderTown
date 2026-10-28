/** Transport, from the browser's side: following a game until it ends or is aborted. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Event } from "../protocol";
import { type ConnectionStatus, followGame } from "./followGame";

class FakeSocket {
  static opened: FakeSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((message: MessageEvent<string>) => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(readonly url: string) {
    FakeSocket.opened.push(this);
  }

  send(event: Partial<Event> & Pick<Event, "seq" | "payload">) {
    this.onmessage?.({ data: JSON.stringify(event) } as MessageEvent<string>);
  }

  close() {
    this.onclose?.();
  }
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
    const statuses: ConnectionStatus[] = [];
    followGame("abc", { onEvent: () => undefined, onStatus: (status) => statuses.push(status) }, "http://api");
    const socket = FakeSocket.opened[0];
    if (!socket) throw new Error("no socket was opened");
    socket.onopen?.();

    socket.send({
      seq: 1,
      payload: { type: "game_aborted", resident: "Rosa", kind: "statement", reason: "no answer within 90 seconds" },
    });
    socket.close();
    vi.runAllTimers();

    expect(statuses.at(-1)).toBe("ended");
    expect(FakeSocket.opened).toHaveLength(1);
  });
});
