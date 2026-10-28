import { type CostRow, costRows } from "../core/cost";
import type { ResidentView } from "../core/gameView";
import type { Cost, CostReport } from "../protocol";

const dollars = (amount: number) => `$${amount.toFixed(4)}`;
const tokens = (count: number) => count.toLocaleString("en-US");
const share = (rate: number | null) => (rate === null ? "-" : `${Math.round(rate * 100)}%`);

/**
 * What the game's model calls have cost so far, at the Claude API's list prices.
 *
 * Mystery mode hides each Resident's cost: who calls the model at Night shows who
 * has a Night role. The totals stay, since they reveal nothing about anyone.
 */
export function CostMeter({
  report,
  residents,
  mystery,
}: {
  report: CostReport;
  residents: readonly ResidentView[];
  mystery: boolean;
}) {
  return (
    <section aria-label="Cost" className="border-t border-stone-800 px-6 py-4">
      <h2 className="mb-3 text-sm uppercase tracking-wider text-stone-400">Cost</h2>
      {report.total.calls === 0 ? (
        <p className="text-sm text-stone-400">No model calls</p>
      ) : (
        <>
          <Totals cost={report.total} />
          {!mystery && <ByCaller rows={costRows(report, residents)} />}
        </>
      )}
    </section>
  );
}

function Totals({ cost }: { cost: Cost }) {
  const figures: [string, string][] = [
    ["Equivalent cost", dollars(cost.cost_usd)],
    ["Model calls", tokens(cost.calls)],
    ["Prompt tokens", tokens(cost.prompt_tokens)],
    ["Tokens out", tokens(cost.output_tokens)],
    ["From cache", share(cost.cache_hit_rate)],
  ];
  return (
    <ul aria-label="Totals" className="space-y-1 text-sm">
      {figures.map(([name, value]) => (
        <li key={name} className="flex justify-between gap-3">
          <span className="text-stone-400">{name}</span>
          <span className="tabular-nums">{value}</span>
        </li>
      ))}
    </ul>
  );
}

/** One row per Resident who called the model, then the Narrator, who is not a Resident. */
function ByCaller({ rows }: { rows: CostRow[] }) {
  const columns = ["Calls", "Prompt tokens", "Tokens out", "From cache", "Cost"];
  return (
    <table aria-label="Cost by caller" className="mt-4 w-full text-sm">
      <thead className="text-left text-xs text-stone-500">
        <tr>
          <th className="font-normal">Caller</th>
          {columns.map((column) => (
            <th key={column} className="text-right font-normal">
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map(({ label, cost }) => (
          <tr key={label}>
            <td>{label}</td>
            <td className="text-right tabular-nums">{tokens(cost.calls)}</td>
            <td className="text-right tabular-nums">{tokens(cost.prompt_tokens)}</td>
            <td className="text-right tabular-nums">{tokens(cost.output_tokens)}</td>
            <td className="text-right tabular-nums">{share(cost.cache_hit_rate)}</td>
            <td className="text-right tabular-nums">{dollars(cost.cost_usd)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
