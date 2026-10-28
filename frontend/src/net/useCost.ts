import { useEffect, useRef, useState } from "react";

import type { CostReport } from "../protocol";
import type { CostSource } from "./cost";

/**
 * The latest cost report, asked for again as events arrive.
 *
 * At most one request is out at a time. Events that arrive while it is out make
 * the hook ask once more when it returns, so a fast game does not flood the server.
 * A failed request leaves the last report showing.
 */
export function useCost(source: CostSource | undefined, eventCount: number): CostReport | null {
  const [report, setReport] = useState<CostReport | null>(null);
  const asking = useRef({ out: false, stale: false, mounted: true });

  useEffect(() => {
    const state = asking.current;
    state.mounted = true;
    return () => {
      state.mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!source) return;
    const state = asking.current;
    const ask = () => {
      state.out = true;
      state.stale = false;
      source()
        .then((answer) => {
          if (state.mounted) setReport(answer);
        })
        .catch(() => undefined)
        .finally(() => {
          state.out = false;
          if (state.mounted && state.stale) ask();
        });
    };
    if (state.out) state.stale = true;
    else ask();
  }, [source, eventCount]);

  return report;
}
