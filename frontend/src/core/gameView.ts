/**
 * What a Spectator sees at a given moment, folded from the events received so far.
 *
 * Pure TypeScript: no React, no Phaser, no I/O. The same fold serves live games
 * and replays, so both always show the same thing for the same events.
 */
import type { Event, Phase, PayloadOf, Role, Side } from "../protocol";

export interface ResidentView {
  name: string;
  seat: number;
  /** Spectators see every role; `revealed` says whether the town has learned it too. */
  role: Role | null;
  revealed: boolean;
  fate: PayloadOf<"resident_died">["cause"] | null;
}

export interface GameView {
  residents: ResidentView[];
  day: number;
  phase: Phase;
  outcome: { winner: Side; reason: string } | null;
}

export const emptyView: GameView = { residents: [], day: 0, phase: "setup", outcome: null };

export function foldEvents(events: readonly Event[]): GameView {
  return events.reduce(applyEvent, emptyView);
}

export function applyEvent(view: GameView, event: Event): GameView {
  const payload = event.payload;
  switch (payload.type) {
    case "game_started":
      return {
        ...view,
        residents: payload.residents.map(({ name, seat }) => ({
          name,
          seat,
          role: null,
          revealed: false,
          fate: null,
        })),
      };
    case "role_assigned":
      return { ...view, residents: change(view.residents, payload.resident, { role: payload.role }) };
    case "phase_started":
      return { ...view, day: payload.day, phase: payload.phase };
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
    case "statement_made":
    case "ballot_cast":
    case "vote_resolved":
      return view; // these only appear in the feed
  }
}

function change(residents: ResidentView[], name: string, update: Partial<ResidentView>) {
  return residents.map((resident) => (resident.name === name ? { ...resident, ...update } : resident));
}
