/**
 * The town's clock. Everything in town (walks, falls, typing, moments) runs on game time: real
 * time at playback's speed, slower while the Sheriff's shot plays, and none at all while
 * playback holds or the town stands still. So a walk takes half as long at double speed and
 * stops where it is when held.
 */

/** How fast game time runs in slow motion. */
export const SLOW_MOTION = 0.3;

export function gameTime(realMs: number, pace: { speed: number; stopped: boolean; slowMotion: boolean }): number {
  if (pace.stopped) return 0;
  return realMs * pace.speed * (pace.slowMotion ? SLOW_MOTION : 1);
}
