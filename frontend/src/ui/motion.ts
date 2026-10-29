/** Whether the Spectator has asked their system for less motion. */
export function prefersReducedMotion(): boolean {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Whether the page was asked to play deterministically (`?deterministic=1`), as screenshot
 * tests do: the town stands still and the game is silent. */
export function deterministic(): boolean {
  return new URLSearchParams(window.location.search).get("deterministic") === "1";
}
