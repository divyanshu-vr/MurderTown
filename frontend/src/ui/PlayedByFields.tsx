import type { ReactNode } from "react";

import type { Effort, PlayedByInput, SetupChoices } from "../protocol";
import { effortLabel } from "./labels";
import { fieldStyle, inputStyle } from "./styles";

/** The provider that means a scripted bot (the engine's `SCRIPTED_PROVIDER`). */
const SCRIPTED = "scripted";

/** The choices on offer, plus the one already made if the server did not list it. */
function offering(listed: readonly string[] | undefined, current: string | undefined): string[] {
  const options = [...(listed ?? [])];
  if (current && !options.includes(current)) options.unshift(current);
  return options;
}

/**
 * Who plays a Resident: a scripted bot, or an Agent on a provider's model, thinking with
 * some effort. A scripted bot needs no model or effort, so those are left as they were.
 */
export function PlayedByFields({
  legend,
  value,
  choices,
  onChange,
  children,
}: {
  legend: string;
  value: PlayedByInput;
  choices: SetupChoices | null;
  onChange: (value: PlayedByInput) => void;
  children?: ReactNode;
}) {
  const scripted = value.provider === SCRIPTED;
  return (
    <fieldset className="flex flex-wrap items-end gap-3 rounded border border-stone-800 p-3">
      <legend className="px-1 text-sm text-stone-300">{legend}</legend>
      {children}
      <label className={fieldStyle}>
        <span>Provider</span>
        <select
          className={inputStyle}
          value={value.provider}
          onChange={(event) => onChange({ ...value, provider: event.target.value })}
        >
          {offering(choices?.providers, value.provider).map((provider) => (
            <option key={provider}>{provider}</option>
          ))}
        </select>
      </label>
      <label className={fieldStyle}>
        <span>Model</span>
        <select
          className={inputStyle}
          disabled={scripted}
          value={value.model}
          onChange={(event) => onChange({ ...value, model: event.target.value })}
        >
          {offering(choices?.models, value.model).map((model) => (
            <option key={model}>{model}</option>
          ))}
        </select>
      </label>
      <label className={fieldStyle}>
        <span>Effort</span>
        <select
          className={inputStyle}
          disabled={scripted}
          value={value.effort}
          onChange={(event) => onChange({ ...value, effort: event.target.value as Effort })}
        >
          {Object.entries(effortLabel).map(([effort, label]) => (
            <option key={effort} value={effort}>
              {label}
            </option>
          ))}
        </select>
      </label>
    </fieldset>
  );
}
