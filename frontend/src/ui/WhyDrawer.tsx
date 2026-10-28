import { useEffect, useState } from "react";

import type { Explain } from "../net/explain";
import { traceUrl } from "../net/traces";
import type { Explanation, ModelCall } from "../protocol";
import { describeEvent } from "./describeEvent";
import { FallbackNote } from "./FallbackNote";
import { attemptLabel } from "./labels";

type Asked =
  | { state: "asking" }
  | { state: "answered"; explanation: Explanation }
  | { state: "failed"; message: string };

/**
 * The decision behind one event: the exact prompt and raw answer of every model attempt.
 *
 * Everything is shown as plain text, never as markup, because it is written by models.
 * Give it a `key` of the event's sequence number so a new event starts a new request.
 */
export function WhyDrawer({ seq, explain, onClose }: { seq: number; explain: Explain; onClose: () => void }) {
  const [asked, setAsked] = useState<Asked>({ state: "asking" });

  useEffect(() => {
    let wanted = true;
    explain(seq).then(
      (explanation) => {
        if (wanted) setAsked({ state: "answered", explanation });
      },
      (error: unknown) => {
        if (wanted) setAsked({ state: "failed", message: error instanceof Error ? error.message : String(error) });
      },
    );
    return () => {
      wanted = false;
    };
  }, [explain, seq]);

  return (
    <section aria-label="Why?" className="mt-3 rounded border border-stone-700 bg-stone-900 p-3 text-sm">
      <header className="mb-2 flex items-center justify-between">
        <h4 className="font-semibold text-amber-200">Why?</h4>
        <button type="button" onClick={onClose} className="text-stone-400 hover:text-stone-200">
          Close
        </button>
      </header>
      {asked.state === "asking" && <p className="text-stone-400">Asking the server…</p>}
      {asked.state === "failed" && <p role="alert">{asked.message}</p>}
      {asked.state === "answered" && <ExplanationView explanation={asked.explanation} />}
    </section>
  );
}

function ExplanationView({ explanation }: { explanation: Explanation }) {
  const { event, attempts, fallback_reason: fallbackReason } = explanation;
  return (
    <div className="space-y-3">
      <p className="text-stone-300">{describeEvent(event)}</p>
      {fallbackReason && <FallbackNote reason={fallbackReason} />}
      {attempts.length === 0 ? (
        <p className="text-stone-400">A scripted bot made this decision, so no model was asked.</p>
      ) : (
        <>
          <p className="text-xs text-stone-500">
            Details from outside the game, such as email addresses and file paths, appear as [hidden].
          </p>
          {attempts.map((attempt) => (
            <Attempt key={attempt.attempt} attempt={attempt} />
          ))}
        </>
      )}
    </div>
  );
}

function Attempt({ attempt }: { attempt: ModelCall }) {
  const title = `Attempt ${attempt.attempt}${attempt.attempt > 1 ? " (retry)" : ""}: ${attemptLabel[attempt.outcome]}`;
  return (
    <article aria-label={`Attempt ${attempt.attempt}`} className="space-y-1 border-t border-stone-800 pt-2">
      <h5 className="font-medium">{title}</h5>
      {attempt.problem && <p className="text-amber-300">{attempt.problem}</p>}
      <p className="text-xs text-stone-500">
        {attempt.model}, {attempt.effort} effort · {attempt.input_tokens} tokens in, {attempt.output_tokens} out
        <TraceLink traceId={attempt.trace_id} />
      </p>
      <details>
        <summary className="cursor-pointer text-stone-400">System prompt</summary>
        <pre className="whitespace-pre-wrap text-xs text-stone-300">{attempt.system}</pre>
      </details>
      <details>
        <summary className="cursor-pointer text-stone-400">Prompt</summary>
        <pre className="whitespace-pre-wrap text-xs text-stone-300">{attempt.prompt}</pre>
      </details>
      <p className="text-stone-400">Raw response</p>
      <pre className="whitespace-pre-wrap text-xs text-stone-200">{attempt.raw_text || "(none)"}</pre>
    </article>
  );
}

function TraceLink({ traceId }: { traceId: string | null }) {
  const url = traceUrl(traceId);
  if (!url) return null;
  return (
    <>
      {" · "}
      <a href={url} target="_blank" rel="noreferrer" className="text-amber-300 hover:underline">
        trace
      </a>
    </>
  );
}
