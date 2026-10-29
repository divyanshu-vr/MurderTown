/**
 * How long a Night Visit plays in the Town view, in game time: the visitors walk to the door at
 * the Night's hurried pace, do their deed there, walk home, and stand a moment once home. The
 * town plays each Visit before playback shows the next, so the longest a Visit can take must fit
 * well within the time playback waits for an animation (`ANIMATION_TIMEOUT_MS`).
 */
import { paceFor } from "./walk";

/** How long a Visit's deed at the door plays. */
export const DEED_MS = 1200;

/** Once whoever is going somewhere at Night has arrived, a moment to see them there. */
export const ARRIVED_MS = 300;

/** How long a Visit takes whose visitors walk `there` tiles to the door and `back` tiles home. */
export function visitMs(there: number, back: number): number {
  return ((there + back) * 1000) / paceFor("night") + DEED_MS + ARRIVED_MS;
}
