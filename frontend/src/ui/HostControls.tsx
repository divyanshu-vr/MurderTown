import { useState } from "react";

import { failure } from "../net/fetchJson";
import type { Control } from "../protocol";
import { controlLabel } from "./labels";

/**
 * The Host's controls over a game being played, as the server offers them: pause it before
 * its next decisions, then step it one batch of decisions at a time, or resume it.
 */
export function HostControls({
  offered,
  onControl,
}: {
  offered: readonly Control[];
  onControl: (control: Control) => Promise<unknown>;
}) {
  const [refusal, setRefusal] = useState<string | null>(null);
  if (offered.length === 0) return null;

  const act = (control: Control) => {
    setRefusal(null);
    onControl(control).catch((error: unknown) => setRefusal(failure(error)));
  };
  return (
    <div role="group" aria-label="Host controls" className="flex items-center gap-2">
      {offered.map((control) => (
        <button
          key={control}
          type="button"
          onClick={() => act(control)}
          className="rounded-full border border-amber-300/60 px-3 py-1 text-sm text-amber-200 hover:bg-amber-300/10"
        >
          {controlLabel[control]}
        </button>
      ))}
      {refusal && (
        <p role="alert" className="text-sm text-rose-300">
          {refusal}
        </p>
      )}
    </div>
  );
}
