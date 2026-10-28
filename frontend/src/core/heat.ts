/**
 * The suspicion heatmap: every Resident's latest Suspicion of every other, as their dossiers
 * stood at the start of the latest Phase among the events reached (so nothing from later in
 * that Phase shows), with each one's change since the last Phase start at which any Suspicion
 * was different. Reflections come only at Dawn and the Vote, so most Phase starts repeat the
 * one before. Folded from reflections by the same rule as the Mind inspector's dossier.
 */
import type { Event, Phase, Suspicion } from "../protocol";
import { noteSuspicions } from "./mind";

export interface HeatCell {
  suspicion: number;
  note: string;
  /** Since `Heat.since`; null if there was no Suspicion of them then. */
  change: number | null;
}

export interface Moment {
  day: number;
  phase: Phase;
}

export interface Heat extends Moment {
  /** The earlier Phase start each change is measured from, or null if there was none. */
  since: Moment | null;
  /** By suspecting Resident, then by suspected Resident. */
  suspicions: ReadonlyMap<string, ReadonlyMap<string, HeatCell>>;
}

type Dossiers = Map<string, Map<string, Suspicion>>;

interface Snapshot extends Moment {
  dossiers: Dossiers;
}

/** The heatmap as of these events, or null before the first Phase. */
export function heatAt(reached: readonly Event[]): Heat | null {
  const dossiers: Dossiers = new Map();
  let latest: Snapshot | null = null;
  let different: Snapshot | null = null;
  for (const event of reached) {
    const payload = event.payload;
    if (payload.type === "reflection_written") {
      const dossier = dossiers.get(payload.resident) ?? new Map<string, Suspicion>();
      noteSuspicions(dossier, payload.suspicions);
      dossiers.set(payload.resident, dossier);
    } else if (payload.type === "phase_started") {
      const now = copied(dossiers);
      if (latest && levels(latest.dossiers) !== levels(now)) different = latest;
      latest = { day: payload.day, phase: payload.phase, dossiers: now };
    }
  }
  if (!latest) return null;
  const suspicions = new Map(
    [...latest.dossiers].map(([resident, dossier]) => [
      resident,
      new Map(
        [...dossier].map(([suspect, { suspicion, note }]) => {
          const before = different?.dossiers.get(resident)?.get(suspect);
          return [suspect, { suspicion, note, change: before ? suspicion - before.suspicion : null }];
        }),
      ),
    ]),
  );
  const since = different && { day: different.day, phase: different.phase };
  return { day: latest.day, phase: latest.phase, since, suspicions };
}

function copied(dossiers: Dossiers): Dossiers {
  return new Map([...dossiers].map(([resident, dossier]) => [resident, new Map(dossier)]));
}

/** Every level of Suspicion, without the notes: a reworded note changes nothing on the map. */
function levels(dossiers: Dossiers): string {
  return JSON.stringify(
    [...dossiers].map(([resident, dossier]) => [resident, [...dossier.values()].map((s) => [s.resident, s.suspicion])]),
  );
}
