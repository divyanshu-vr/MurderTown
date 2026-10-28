/** Asks the server for one JSON report, saying what could not be had if the server refuses. */
export async function fetchJson<T>(url: string, what: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`The server could not ${what} (${response.status}).`);
  return (await response.json()) as T;
}
