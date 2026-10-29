/** Seam 3: the game's sound beside playback, on the recorded game, with a stand-in for the browser's audio. */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { playbackAt } from "../../test/playback";
import { present } from "../../test/present";
import { recordedGame } from "../../test/recordedGame";
import { GameConsole } from "./GameConsole";

const events = recordedGame();

/** Stands in for the browser's audio, noting the volumes asked for and the notes started; its nodes make no sound. */
class StandInAudio {
  static made: StandInAudio[] = [];
  /** How the browser starts audio: held back, when it did not count the gesture. */
  static starts: AudioContextState = "running";
  state: AudioContextState = StandInAudio.starts;
  currentTime = 0;
  sampleRate = 8000;
  destination = {};
  volumes: number[] = [];
  notes = 0;

  constructor() {
    StandInAudio.made.push(this);
  }

  createGain = () => ({ gain: param((volume) => this.volumes.push(volume)), connect: (to: unknown) => to, disconnect: () => undefined });
  createOscillator = () => ({
    type: "",
    frequency: param(),
    connect: (to: unknown) => to,
    start: () => {
      this.notes += 1;
    },
    stop: () => undefined,
  });
  createBufferSource = () => ({ buffer: null, connect: (to: unknown) => to, start: () => undefined, stop: () => undefined });
  createBuffer = () => ({ getChannelData: () => new Float32Array(8) });
  suspend = () => {
    this.state = "suspended";
    return Promise.resolve();
  };
  resume = () => {
    this.state = "running";
    return Promise.resolve();
  };
  close = () => Promise.resolve();
}

function param(onTarget: (value: number) => void = () => undefined) {
  const nothing = () => undefined;
  return {
    value: 0,
    setTargetAtTime: onTarget,
    setValueAtTime: nothing,
    linearRampToValueAtTime: nothing,
    exponentialRampToValueAtTime: nothing,
    cancelScheduledValues: nothing,
  };
}

const watching = (held = false) => (
  <GameConsole events={events} connection="ended" playback={playbackAt(200, events.length, { held })} />
);

beforeEach(() => {
  StandInAudio.made = [];
  StandInAudio.starts = "running";
  vi.stubGlobal("AudioContext", StandInAudio);
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
  window.history.replaceState(null, "", "/");
});

describe("the game's sound", () => {
  it("starts at the Spectator's first click, as browsers require, and only once", () => {
    render(watching());
    expect(StandInAudio.made).toHaveLength(0);

    fireEvent.pointerDown(window);
    fireEvent.pointerDown(window);

    expect(StandInAudio.made).toHaveLength(1);
  });

  it("starts at a touch too, waking the audio when the browser held it back", () => {
    StandInAudio.starts = "suspended";
    render(watching());

    fireEvent.pointerUp(window);

    expect(StandInAudio.made[0]?.state).toBe("running");
  });

  it("stays off in a deterministic run", () => {
    window.history.replaceState(null, "", "/?deterministic=1");
    render(watching());

    fireEvent.pointerDown(window);

    expect(StandInAudio.made).toHaveLength(0);
  });

  it("plays the music while playback plays", async () => {
    render(watching());

    fireEvent.pointerDown(window);

    await waitFor(() => expect(StandInAudio.made[0]?.notes).toBeGreaterThan(0));
  });

  it("falls silent when the Spectator turns it off, and comes back at their volume", () => {
    render(watching());
    fireEvent.pointerDown(window);
    const audio = present(StandInAudio.made[0], "the audio");

    fireEvent.click(screen.getByRole("button", { name: "Sound" }));
    expect(audio.volumes.at(-1)).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: "Sound" }));
    expect(audio.volumes.at(-1)).toBe(0.6);
  });

  it("falls silent while playback is held", async () => {
    render(watching(true));

    fireEvent.keyDown(window, { key: "x" });

    await waitFor(() => expect(StandInAudio.made[0]?.state).toBe("suspended"));
  });

  it("can be turned off and made quieter beside playback, and the browser remembers both", () => {
    const first = render(watching());
    const playback = screen.getByRole("group", { name: "Playback" });

    fireEvent.change(screen.getByRole("slider", { name: "Volume" }), { target: { value: "0.3" } });
    fireEvent.click(screen.getByRole("button", { name: "Sound" }));
    expect(screen.getByRole("button", { name: "Sound" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("slider", { name: "Volume" })).toBeDisabled();
    expect(playback).toContainElement(screen.getByRole("slider", { name: "Volume" }));
    first.unmount();

    render(watching());

    expect(screen.getByRole("button", { name: "Sound" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("slider", { name: "Volume" })).toHaveValue("0.3");
  });
});
