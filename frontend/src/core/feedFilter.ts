/**
 * Which lines of the feed a Spectator chose to see: by kind of line and by Resident.
 *
 * Pure TypeScript: no React, no I/O.
 */
import type { Event, Payload } from "../protocol";
import { isPublic } from "./gameView";
import { involves } from "./involved";

/** What the whole town saw, what only some saw, the Night's secret actions, and the game's own notices. */
export type FeedKind = "public" | "private" | "night" | "system";

const EVERY_KIND: readonly FeedKind[] = ["public", "private", "night", "system"];
const WHAT_THE_TOWN_SAW: readonly FeedKind[] = ["public", "system"];

/** System lines are the game's own notices: the town filling, Fallbacks and unanswered decisions, and the end. */
function isSystemLine(type: Payload["type"]): boolean {
  switch (type) {
    case "game_started":
    case "open_floor_timed_out":
    case "decision_fell_back":
    case "decision_unanswered":
    case "roles_revealed":
    case "game_ended":
    case "game_aborted":
      return true;
    case "phase_started": // a heading, kept above whichever lines under it are shown
    case "game_configured":
    case "role_assigned":
    case "bid_placed":
    case "statement_made":
    case "sheriff_fired":
    case "sheriff_held_fire":
    case "ballot_cast":
    case "vote_resolved":
    case "last_words_spoken":
    case "resident_died":
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
    case "reflection_written":
      return false;
  }
}

/** A line the whole town perceived is public; the rest is secret, at Night, or private otherwise. */
function feedKind(event: Event): FeedKind {
  if (isSystemLine(event.payload.type)) return "system";
  if (isPublic(event)) return "public";
  return event.phase === "night" ? "night" : "private";
}

export interface FeedFilter {
  kinds: ReadonlySet<FeedKind>;
  /** One Resident to follow, or null for everyone. */
  resident: string | null;
}

export const EVERYTHING: FeedFilter = { kinds: new Set(EVERY_KIND), resident: null };

/** The kinds a Spectator may choose among: in mystery mode, only what the whole town saw and the game's notices. */
export function offeredKinds(mystery: boolean): readonly FeedKind[] {
  return mystery ? WHAT_THE_TOWN_SAW : EVERY_KIND;
}

/** The filter with one kind of line shown if it was hidden, or hidden if it was shown. */
export function flipKind(filter: FeedFilter, kind: FeedKind): FeedFilter {
  const kinds = new Set(filter.kinds);
  if (!kinds.delete(kind)) kinds.add(kind);
  return { ...filter, kinds };
}

/** One string per choice, the same for the same choice. */
export function filterKey({ kinds, resident }: FeedFilter): string {
  return `${[...kinds].sort().join(",")}/${resident ?? ""}`;
}

/** Whether the filter leaves anything on offer out. */
export function isFiltered({ kinds, resident }: FeedFilter, offered: readonly FeedKind[]): boolean {
  return resident !== null || offered.some((kind) => !kinds.has(kind));
}

function passes(event: Event, { kinds, resident }: FeedFilter): boolean {
  return kinds.has(feedKind(event)) && (resident === null || involves(event.payload).includes(resident));
}

/**
 * The feed's lines the filter keeps. While it leaves something out, each Phase heading stays
 * above the lines kept under it, whatever the filter, and goes when none are.
 */
export function chosenLines(lines: readonly Event[], filter: FeedFilter, offered: readonly FeedKind[]): readonly Event[] {
  if (!isFiltered(filter, offered)) return lines;
  const kept: Event[] = [];
  let heading: Event | null = null;
  for (const line of lines) {
    if (line.payload.type === "phase_started") heading = line;
    else if (passes(line, filter)) {
      if (heading) kept.push(heading);
      heading = null;
      kept.push(line);
    }
  }
  return kept;
}
