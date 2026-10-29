/**
 * What the game sounds like as playback shows it: which music plays, which sting marks a moment,
 * and when a voice blips. Pure decisions; src/sound plays them.
 *
 * The Soundtrack follows playback a frame at a time. It plays what the Spectator watches happen:
 * once each, and nothing for events a jump passes over or while playback is held; words that
 * appear by a jump, or by a step while held, show whole and are not voiced. A frame of fast
 * playback can show several events; only the most telling sting plays, and words typing out make
 * at most one blip a frame, so sounds never pile up.
 */
import type { Event, Phase } from "../protocol";
import type { GameView } from "./gameView";
import { decider } from "./involved";
import type { SinceShown } from "./playback";
import { typedAfter, typesOut } from "./presentation";

export type Theme = "day" | "night";

/** The stings, most telling first: the one that plays when a frame shows several. */
const TELLING = ["town-wins", "murderers-win", "murder", "shot", "banishment", "vote-result", "phase", "ballot"] as const;

export type Sting = (typeof TELLING)[number];

/** Letters typed out from one voice blip to the next: about a syllable. */
export const LETTERS_PER_BLIP = 3;

/** What playback shows in a frame. */
export interface Frame {
  events: readonly Event[];
  /** The view they make, for the Phase and the Residents' seats. */
  view: GameView;
  /** How many times the view has jumped rather than played on. */
  cuts: number;
  held: boolean;
  /** Mystery mode changes what is shown at once, as a jump does. */
  mystery: boolean;
  sinceShown: SinceShown;
}

/** What to sound in a frame: the music, and at most one sting and one voice blip. */
export interface Sounds {
  theme: Theme | null;
  sting: Sting | null;
  /** The note of a voice blip, as a MIDI number (60 is middle C). */
  blip: number | null;
}

export function themeOf(phase: Phase): Theme | null {
  if (phase === "setup" || phase === "ended") return null;
  return phase === "night" ? "night" : "day";
}

export function stingOf({ payload }: Event): Sting | null {
  switch (payload.type) {
    case "phase_started":
      return "phase";
    case "ballot_cast":
      return "ballot";
    case "vote_resolved":
      return "vote-result";
    case "sheriff_fired":
      return "shot";
    case "resident_died": // a murder is found at Dawn; a shot has its own sting
      if (payload.cause === "murdered") return "murder";
      return payload.cause === "banished" ? "banishment" : null;
    case "game_ended":
      return payload.winner === "town" ? "town-wins" : "murderers-win";
    case "game_configured":
    case "game_started":
    case "role_assigned":
    case "bid_placed":
    case "statement_made":
    case "open_floor_timed_out":
    case "sheriff_held_fire":
    case "den_message_posted":
    case "kill_vote_cast":
    case "victim_chosen":
    case "resident_protected":
    case "resident_investigated":
    case "attack_thwarted":
    case "recap_narrated":
    case "dusk_intent_chosen":
    case "conversation_started":
    case "conversation_message_posted":
    case "last_words_spoken":
    case "reflection_written":
    case "decision_fell_back":
    case "decision_unanswered":
    case "roles_revealed":
    case "game_aborted":
      return null; // words have their voices; the rest pass quietly
  }
}

/** A Resident's voice: each seat a note of the major scale from C3 up, so no two in a town sound
 * alike. The Narrator, who has no seat, speaks lower than any of them. */
export function voiceOf(seat: number | null): number {
  if (seat === null) return 43; // G2
  const degrees = [0, 2, 4, 5, 7, 9, 11];
  return 48 + 12 * Math.floor(seat / degrees.length) + (degrees[seat % degrees.length] ?? 0);
}

/** How many blips words make after `ms` on screen, as they type out; none for an event not said aloud. */
function blipsAfter(event: Event, ms: number): number {
  const words = typesOut(event) && "text" in event.payload ? event.payload.text : "";
  return Math.ceil(typedAfter(0, ms, words.length) / LETTERS_PER_BLIP);
}

export class Soundtrack {
  /** How many of the events shown have been heard. */
  private heard = 0;
  private cuts = 0;
  private mystery = false;
  /** The words being voiced, and how many blips they have made. */
  private speaking: { seq: number; blips: number } | null = null;

  next({ events, view, cuts, held, mystery, sinceShown }: Frame): Sounds {
    const jumped = cuts !== this.cuts || mystery !== this.mystery || events.length < this.heard;
    const fresh = jumped ? [] : events.slice(this.heard);
    [this.heard, this.cuts, this.mystery] = [events.length, cuts, mystery];
    const silent = jumped || held;
    const blip = this.voice(events, view, sinceShown, silent);
    return { theme: themeOf(view.phase), sting: silent ? null : mostTelling(fresh), blip };
  }

  /** A blip when the latest words have typed out a few more letters since the last frame. */
  private voice(events: readonly Event[], view: GameView, sinceShown: SinceShown, silent: boolean): number | null {
    const latest = events.at(-1);
    const since = latest ? sinceShown(latest.seq) : null;
    if (!latest || since === null) return null;
    const due = blipsAfter(latest, since);
    const voiced = this.speaking?.seq === latest.seq ? this.speaking.blips : silent ? Infinity : 0;
    this.speaking = { seq: latest.seq, blips: Math.max(due, voiced) };
    if (silent || due <= voiced) return null;
    const speaker = decider(latest.payload);
    return voiceOf(view.residents.find(({ name }) => name === speaker)?.seat ?? null);
  }
}

function mostTelling(events: readonly Event[]): Sting | null {
  const stings = new Set(events.map(stingOf));
  return TELLING.find((sting) => stings.has(sting)) ?? null;
}
