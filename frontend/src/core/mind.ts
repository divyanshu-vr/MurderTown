/**
 * One Resident's mind as a Spectator inspects it, folded from the events held so far.
 *
 * Pure TypeScript, so live games and replays (even from a file, with no backend)
 * show the same mind for the same events. It follows the rules of the backend's
 * `remember` (backend/src/mm/agents/memory.py), which builds the Agent's prompts:
 * a reflection with an empty notebook keeps the previous one, empty journal
 * entries are skipped, and the latest suspicion about each Resident wins.
 */
import type { Event, JournalEntry, Mind, Payload, PayloadOf, Suspicion } from "../protocol";
import type { ResidentView } from "./gameView";

/** One decision the Resident made: the event it caused, and why it fell back, if it did. */
export interface DecisionView {
  event: Event;
  fallbackReason: string | null;
}

/** The backend's `Mind`, without the perceived events, plus the Resident's decisions. */
export type MindView = Omit<Mind, "perceived"> & { decisions: DecisionView[] };

export function mindOf(events: readonly Event[], resident: string): MindView | null {
  let assigned: PayloadOf<"role_assigned"> | null = null;
  let notebook = "";
  const journal: JournalEntry[] = [];
  const dossier = new Map<string, Suspicion>();
  const decisions = new Map<string, DecisionView>();

  for (const event of events) {
    const payload = event.payload;
    if (payload.type === "role_assigned" && payload.resident === resident) {
      assigned = payload;
    }
    if (payload.type === "reflection_written" && payload.resident === resident) {
      notebook = payload.notebook || notebook;
      if (payload.journal_entry) {
        journal.push({ day: event.day, phase: event.phase, text: payload.journal_entry });
      }
      for (const suspicion of payload.suspicions) dossier.set(suspicion.resident, suspicion);
    }
    const id = event.decision_id;
    if (id && decider(payload) === resident) {
      const decided = decisions.get(id);
      if (payload.type === "decision_fell_back" && decided) {
        decisions.set(id, { ...decided, fallbackReason: payload.reason });
      } else if (!decided) {
        decisions.set(id, { event, fallbackReason: null });
      }
    }
  }

  if (!assigned) return null;
  return {
    resident,
    role: assigned.role,
    persona: assigned.persona,
    teammates: assigned.teammates,
    memory: {
      notebook,
      journal,
      dossier: [...dossier.values()].sort(byName),
    },
    decisions: [...decisions.values()],
  };
}

/** Sorts by name in code-point order, as the backend does, so both folds give the same list. */
function byName(a: Suspicion, b: Suspicion): number {
  return a.resident < b.resident ? -1 : a.resident > b.resident ? 1 : 0;
}

/** One row of the Dossier as the inspector shows it: every other Resident, rated or not. */
export interface DossierRow {
  name: string;
  dead: boolean;
  suspicion: Suspicion | null;
}

export function dossierRows(mind: MindView, residents: readonly ResidentView[]): DossierRow[] {
  const latest = new Map(mind.memory.dossier.map((suspicion) => [suspicion.resident, suspicion]));
  return residents
    .filter((resident) => resident.name !== mind.resident)
    .map(({ name, fate }) => ({ name, dead: fate !== null, suspicion: latest.get(name) ?? null }));
}

/** The Resident whose decision an event records, or null for events no Resident decided. */
export function decider(payload: Payload): string | null {
  switch (payload.type) {
    case "bid_placed":
    case "last_words_spoken":
    case "reflection_written":
    case "decision_fell_back":
      return payload.resident;
    case "statement_made":
      return payload.speaker;
    case "sheriff_fired":
    case "sheriff_held_fire":
      return payload.sheriff;
    case "ballot_cast":
      return payload.voter;
    case "game_started":
    case "role_assigned":
    case "phase_started":
    case "vote_resolved":
    case "resident_died":
    case "game_ended":
      return null;
  }
}
