export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

const HOST_TOKEN_HEADER = "X-Host-Token";

/** The server refused a request, for the reason in the message. */
export class Refusal extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

interface Asking {
  method?: "GET" | "POST";
  /** Sent as JSON. */
  body?: unknown;
  /** Asks as the Host. */
  hostToken?: string | null;
}

/**
 * Asks the server for one JSON answer. If the server refuses, the error says what could not
 * be had, and the server's reason when it gives one.
 */
export async function fetchJson<T>(url: string, what: string, asking: Asking = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (asking.hostToken) headers[HOST_TOKEN_HEADER] = asking.hostToken;
  if (asking.body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(url, {
    method: asking.method ?? "GET",
    headers,
    ...(asking.body !== undefined && { body: JSON.stringify(asking.body) }),
  });
  if (!response.ok) {
    const reason = await reasonFor(response);
    throw new Refusal(response.status, `The server could not ${what} (${response.status})${reason ? `: ${reason}` : "."}`);
  }
  return (await response.json()) as T;
}

/** What to tell the Host when a request failed. */
export function failure(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** The server's reason for refusing: one sentence, or one per field it found wrong. */
async function reasonFor(response: Response): Promise<string | null> {
  try {
    const { detail } = (await response.json()) as { detail?: string | { msg: string }[] };
    if (typeof detail === "string") return detail;
    // a rule the server checks across fields reads "Value error, <the rule>"
    return detail?.map((problem) => problem.msg.replace(/^Value error, /, "")).join("; ") ?? null;
  } catch {
    return null;
  }
}
