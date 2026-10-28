/**
 * The Host token this browser holds, which lets it start and control games and see a
 * game's full scope. `mm serve` prints a link that hands it over (#host-token=...), or the
 * Host pastes it in. It is kept in this browser only; storage may be blocked, so every
 * read and write may fail quietly, leaving the browser a Spectator.
 */
const KEY = "murdertown.host-token";
const HANDED_OVER = /^#host-token=(.+)$/;

export function heldHostToken(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function keepHostToken(token: string): void {
  try {
    localStorage.setItem(KEY, token);
  } catch {
    // a Spectator, then
  }
}

export function forgetHostToken(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // nothing kept
  }
}

/** Keep the token a link handed over, and take it out of the address bar. */
export function takeHostTokenFromLink(): void {
  const handed = HANDED_OVER.exec(window.location.hash)?.[1];
  if (!handed) return;
  keepHostToken(decodeURIComponent(handed));
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
}
