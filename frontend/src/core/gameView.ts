/**
 * What a Spectator sees at a given moment, folded from the events received so far.
 *
 * Pure TypeScript: no React, no Phaser, no I/O. The same fold serves live games
 * and replays, so both always show the same thing for the same events.
 */
import type { Event, GameConfig, Phase, PayloadOf, Role, Side } from "../protocol";

export interface ResidentView {
  name: string;
  seat: number;
  occupation: string;
  /** Spectators see every role; `revealed` says whether the town has learned it too. */
  role: Role | null;
  revealed: boolean;
  fate: PayloadOf<"resident_died">["cause"] | null;
}

export interface GameView {
  config: GameConfig | null;
  residents: ResidentView[];
  day: number;
  phase: Phase;
  /** Statements made so far on the Open floor, or null while it is not under way. */
  openFloorStatements: number | null;
  outcome: { winner: Side; reason: string } | null;
}

export const emptyView: GameView = {
  config: null,
  residents: [],
  day: 0,
  phase: "setup",
  openFloorStatements: null,
  outcome: null,
};

export function foldEvents(events: readonly Event[]): GameView {
  return events.reduce(applyEvent, emptyView);
}

/** Whether the whole town perceived an event. Mystery mode shows only these. */
export function isPublic(event: Event): boolean {
  return event.visibility.scope === "everyone";
}

export function applyEvent(view: GameView, event: Event): GameView {
  const payload = event.payload;
  switch (payload.type) {
    case "game_started":
      return {
        ...view,
        config: payload.config,
        residents: payload.residents.map(({ name, seat, occupation }) => ({
          name,
          seat,
          occupation,
          role: null,
          revealed: false,
          fate: null,
        })),
      };
    case "role_assigned":
      return { ...view, residents: change(view.residents, payload.resident, { role: payload.role }) };
    case "phase_started":
      return { ...view, day: payload.day, phase: payload.phase, openFloorStatements: null };
    case "bid_placed": // Residents bid only on the Open floor, so the first bid opens it
      return { ...view, openFloorStatements: view.openFloorStatements ?? 0 };
    case "statement_made":
      return payload.part === "open_floor"
        ? { ...view, openFloorStatements: (view.openFloorStatements ?? 0) + 1 }
        : view;
    case "resident_died":
      return {
        ...view,
        residents: change(view.residents, payload.resident, {
          role: payload.role,
          revealed: true,
          fate: payload.cause,
        }),
      };
    case "game_ended":
      return { ...view, phase: "ended", outcome: { winner: payload.winner, reason: payload.reason } };
    case "sheriff_fired": // the deaths that follow change the roster
    case "sheriff_held_fire":
    case "den_message_posted":
    case "kill_vote_cast":
    case "victim_chosen": // a murder changes the roster only when Dawn announces it
    case "resident_protected":
    case "resident_investigated":
    case "attack_thwarted":
    case "recap_narrated":
    case "last_words_spoken":
    case "ballot_cast":
    case "vote_resolved":
    case "reflection_written":
    case "decision_fell_back":
      return view; // these only appear in the feed or, later, the Mind inspector
  }
}

function change(residents: ResidentView[], name: string, update: Partial<ResidentView>) {
  return residents.map((resident) => (resident.name === name ? { ...resident, ...update } : resident));
}
