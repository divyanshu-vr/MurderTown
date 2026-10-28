import { useState } from "react";

import type { ResidentView } from "../core/gameView";
import type { Heat, HeatCell, Moment } from "../core/heat";
import { residentName, whenLabel } from "./labels";
import { shadeOf } from "./shade";

/** How a Suspicion changed since the last different Phase start, in words, or "" if it did not. */
function changeText(cell: HeatCell, since: Moment | null): string {
  if (!since) return "";
  if (cell.change === null) return "new";
  if (cell.change === 0) return "";
  return cell.change > 0 ? `up ${cell.change}` : `down ${-cell.change}`;
}

/**
 * Every Resident's Suspicion of every other at the start of the Phase the view is in: a table,
 * one row per suspecting Resident and one column per suspected. Each cell gives the number and
 * any change in words (the shade only repeats them), and choosing a cell, by mouse or keyboard,
 * tells its note and since when it changed.
 */
export function SuspicionHeatmap({ heat, residents }: { heat: Heat; residents: readonly ResidentView[] }) {
  const [chosen, setChosen] = useState<string | null>(null);
  const since = heat.since && whenLabel(heat.since.day, heat.since.phase);
  const label = (resident: ResidentView) => residentName(resident.name, resident.fate !== null);

  return (
    <div className="min-h-0 overflow-auto px-6 py-4">
      <table className="border-separate border-spacing-0.5 text-center text-xs">
        <caption className="mb-3 text-left text-sm text-stone-300">
          Suspicion at the start of {whenLabel(heat.day, heat.phase)}, from 0 (innocent) to 100 (a Murderer)
          {since && `; changes since the start of ${since}`}
        </caption>
        <thead>
          <tr>
            <th scope="col" className="sticky left-0 bg-stone-950">
              <span className="sr-only">Who suspects</span>
            </th>
            {residents.map((suspect) => (
              <th key={suspect.name} scope="col" className="px-1 font-normal text-stone-400">
                {label(suspect)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {residents.map((resident) => (
            <tr key={resident.name}>
              <th scope="row" className="sticky left-0 bg-stone-950 pr-2 text-left font-normal text-stone-300">
                {label(resident)}
              </th>
              {residents.map((suspect) => {
                if (suspect.name === resident.name) {
                  return (
                    <td key={suspect.name} className="text-stone-600">
                      —
                    </td>
                  );
                }
                const cell = heat.suspicions.get(resident.name)?.get(suspect.name);
                if (!cell) {
                  return (
                    <td key={suspect.name} className="min-w-10 rounded bg-stone-900">
                      <span className="sr-only">no opinion yet</span>
                    </td>
                  );
                }
                const { background, text } = shadeOf(cell.suspicion);
                const change = changeText(cell, heat.since);
                const description = `${resident.name} suspects ${suspect.name}: ${cell.suspicion}${change && `, ${change}${since && change !== "new" ? ` since ${since}` : ""}`}. ${cell.note}`;
                return (
                  <td key={suspect.name} className="min-w-10 p-0">
                    <button
                      type="button"
                      title={description}
                      onClick={() => setChosen(description)}
                      className="w-full rounded px-1 py-1 tabular-nums"
                      style={{ backgroundColor: background, color: text }}
                    >
                      {cell.suspicion}
                      {change && <span className="block text-[10px]">{change}</span>}
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p role="status" className="mt-3 text-sm text-stone-300">
        {chosen ?? "Choose a number to read why."}
      </p>
    </div>
  );
}
