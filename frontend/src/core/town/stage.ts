/**
 * What is happening on stage as of the events shown, for the town to draw over the layout.
 * Everything starts afresh with each Phase:
 * - by day, the latest words said (a Statement or Last words) and the ballots cast so far in a Vote;
 * - at Dusk, what each Resident chose to do, and the Conversations under way, each with its latest words;
 * - at Night, the Murderers meeting in the Den and what they say there, then who visits whose house;
 * - at Dawn, who was found murdered, and the Narrator's Recap.
 *
 * Mystery mode shows the town only what everyone saw, so its stage has no Den, no visits, no Dusk
 * activities and no words said in private: just who is talking to whom.
 */
import type { Event, PayloadOf } from "../../protocol";

export type DuskActivity = PayloadOf<"dusk_intent_chosen">["activity"];
export type Pair = PayloadOf<"conversation_started">["residents"];

/**
 * Words said aloud: a Statement, Last words, a Conversation's message or one in the Den. Words said
 * in the same place share a `key` (the day's speaker, each Conversation, the Den), so the town can
 * keep one bubble for them.
 */
export interface Words {
  key: string;
  seq: number;
  speaker: string;
  text: string;
}

export interface Ballot {
  voter: string;
  target: string;
}

/** A Night action seen as a visit: the Murderers to their Victim, the Doctor and the Detective to whom they chose. */
export interface Visit {
  visitor: string;
  target: string;
}

export interface Stage {
  /** What is being said: one Resident's words by day, each Conversation's latest at Dusk, the Den's latest at Night. */
  said: Words[];
  /** The ballots against someone so far this Phase, in the order cast; a vote to skip draws nothing. */
  ballots: Ballot[];
  /** How many ballots each Resident has against them so far. */
  counts: Map<string, number>;
  activities: Map<string, DuskActivity>;
  /** The Conversations under way: the latest wave's, until each has been heard to its end. */
  pairs: Pair[];
  /** The Murderers meeting in the Den (when there are two or more), until they set out for their Victim. */
  den: readonly string[];
  /** Night actions so far, in the order they happened. */
  visits: Visit[];
  foundMurdered: string[];
  recap: string | null;
  /** How many events this Phase has had so far: how far along it is. */
  eventsThisPhase: number;
}

/** Where the day's words are said, and the Den's. */
const SQUARE = "square";
const DEN = "den";

export function stageOf(events: readonly Event[]): Stage {
  const start = events.findLastIndex((event) => event.payload.type === "phase_started");
  const phase = events.slice(start + 1);
  const stage: Stage = {
    said: [],
    ballots: [],
    counts: new Map(),
    activities: new Map(),
    pairs: [],
    den: [],
    visits: [],
    foundMurdered: [],
    recap: null,
    eventsThisPhase: phase.length,
  };
  const talks = new Talks();
  for (const { seq, payload } of phase) {
    switch (payload.type) {
      case "statement_made":
        stage.said = [{ key: SQUARE, seq, speaker: payload.speaker, text: payload.text }];
        break;
      case "last_words_spoken":
        stage.said = [{ key: SQUARE, seq, speaker: payload.resident, text: payload.text }];
        break;
      case "ballot_cast":
        if (payload.target === null) break;
        stage.ballots.push({ voter: payload.voter, target: payload.target });
        stage.counts.set(payload.target, (stage.counts.get(payload.target) ?? 0) + 1);
        break;
      case "dusk_intent_chosen":
        stage.activities.set(payload.resident, payload.activity);
        break;
      case "conversation_started":
        talks.start(payload.residents);
        [stage.pairs, stage.said] = [talks.pairs(), talks.said()];
        break;
      case "conversation_message_posted":
        talks.say({ seq, speaker: payload.speaker, text: payload.text }, payload.partner, payload.ends_conversation);
        [stage.pairs, stage.said] = [talks.pairs(), talks.said()];
        break;
      case "den_message_posted":
        stage.den = payload.den;
        stage.said = [{ key: DEN, seq, speaker: payload.murderer, text: payload.text }];
        break;
      case "kill_vote_cast":
        stage.den = payload.den.length > 1 ? payload.den : [];
        break;
      case "victim_chosen":
        stage.den = [];
        stage.said = [];
        stage.visits.push(...payload.den.map((visitor) => ({ visitor, target: payload.victim })));
        break;
      case "resident_protected":
        stage.visits.push({ visitor: payload.doctor, target: payload.target });
        break;
      case "resident_investigated":
        stage.visits.push({ visitor: payload.detective, target: payload.target });
        break;
      case "resident_died":
        if (payload.cause === "murdered") stage.foundMurdered.push(payload.resident);
        break;
      case "recap_narrated":
        stage.recap = payload.text;
        break;
    }
  }
  return stage;
}

/**
 * The Conversations of Dusk's latest wave. A wave's Conversations all start before anyone in it
 * speaks, and nobody is in two at once, so a Conversation starting after words were said, or with
 * someone already talking, starts the next wave. A Conversation that has ended stays until the
 * next words or Conversation, so its last words are heard. (Mystery mode sees no words, so waves
 * with no one in common can run together there.)
 */
class Talks {
  private wave: { pair: Pair; words: Words | null; ended: boolean }[] = [];
  private spoken = false;

  start(pair: Pair): void {
    this.letTheEndedGo();
    const alreadyTalking = this.wave.some((talk) => talk.pair.some((resident) => pair.includes(resident)));
    if (this.spoken || alreadyTalking) {
      this.wave = [];
      this.spoken = false;
    }
    this.wave.push({ pair, words: null, ended: false });
  }

  say(words: Omit<Words, "key">, to: string, ends: boolean): void {
    this.letTheEndedGo();
    this.spoken = true;
    const talk = this.wave.find(({ pair }) => pair.includes(words.speaker) && pair.includes(to));
    if (!talk) return;
    talk.words = { key: keyOf(talk.pair), ...words };
    talk.ended = ends;
  }

  pairs(): Pair[] {
    return this.wave.map(({ pair }) => pair);
  }

  said(): Words[] {
    return this.wave.flatMap(({ words }) => (words ? [words] : []));
  }

  private letTheEndedGo(): void {
    this.wave = this.wave.filter(({ ended }) => !ended);
  }
}

/** The key the words of a Conversation share. */
export function keyOf(pair: Pair): string {
  return `talk ${pair.join(" ")}`;
}
