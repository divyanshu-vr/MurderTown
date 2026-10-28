/**
 * The cost meter's rows, from a game's cost report and its roster. Pure TypeScript.
 *
 * The Residents come in seat order, then the Narrator, who is not a Resident but
 * also calls the model, so the rows always add up to the total.
 */
import type { Cost, CostReport } from "../protocol";
import type { ResidentView } from "./gameView";

export interface CostRow {
  label: string;
  cost: Cost;
}

export function costRows(report: CostReport, residents: readonly ResidentView[]): CostRow[] {
  const called = residents.flatMap(({ name }) => {
    const cost = report.residents[name];
    return cost ? [{ label: name, cost }] : [];
  });
  return [...called, { label: "Narrator", cost: report.narrator }];
}
