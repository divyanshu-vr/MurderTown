/**
 * Whether the focused control uses a key itself: typing, choosing from a list, moving a slider
 * with the arrows, or pressing a button with Space. Every other key is the page's shortcuts'
 * (playback's, and the town's camera's).
 */
export function keyBelongsToFocus(target: EventTarget | null, key: string): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable || target.tagName === "TEXTAREA" || target.tagName === "SELECT") return true;
  if (target instanceof HTMLInputElement) {
    return target.type === "range" ? key.startsWith("Arrow") : true;
  }
  return target.tagName === "BUTTON" && (key === " " || key === "Enter");
}

/** Whether a key press is a shortcut: no modifier held, and not a key the focused control uses. */
export function isShortcut(event: KeyboardEvent): boolean {
  return !(event.ctrlKey || event.metaKey || event.altKey || keyBelongsToFocus(event.target, event.key));
}
