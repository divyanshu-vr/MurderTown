import { type ReactNode, useMemo, useState } from "react";

import { foldEvents, isPublic } from "../core/gameView";
import { mindOf } from "../core/mind";
import type { CostSource } from "../net/cost";
import type { Explain } from "../net/explain";
import type { ConnectionStatus, Scope } from "../net/followGame";
import { useCost } from "../net/useCost";
import type { Event } from "../protocol";
import { CostMeter } from "./CostMeter";
import { EventFeed } from "./EventFeed";
import { MindInspector } from "./MindInspector";
import { PhaseBar } from "./PhaseBar";
import { Roster } from "./Roster";

/**
 * The text console: phase bar, town feed, roster, cost meter and Mind inspector, for
 * whatever events have arrived.
 *
 * Mystery mode shows only what the whole town saw and has no inspector; a public-scope
 * page is always in mystery mode. The phase bar reads every event the page has, so its
 * Open-floor progress does not depend on private bids being shown. The cost meter
 * needs a `cost` source, and the Host's `controls` come from the page: only the Host's has them.
 */
export function GameConsole({
  events,
  connection,
  explain,
  cost,
  scope = "full",
  paused = false,
  controls,
}: {
  events: readonly Event[];
  connection: ConnectionStatus;
  explain?: Explain | undefined;
  cost?: CostSource | undefined;
  scope?: Scope;
  paused?: boolean;
  controls?: ReactNode;
}) {
  const [mysteryChosen, setMysteryChosen] = useState(false);
  const [inspected, setInspected] = useState<string | null>(null);
  const mystery = scope === "public" || mysteryChosen;

  const truth = useMemo(() => foldEvents(events), [events]);
  const shownEvents = useMemo(() => (mystery ? events.filter(isPublic) : events), [events, mystery]);
  const shown = useMemo(() => (mystery ? foldEvents(shownEvents) : truth), [mystery, shownEvents, truth]);
  const mind = useMemo(() => (inspected ? mindOf(events, inspected) : null), [events, inspected]);
  const report = useCost(cost, events.length);

  const chooseMystery = (on: boolean) => {
    setMysteryChosen(on);
    if (on) setInspected(null);
  };

  return (
    <div className="flex h-dvh flex-col bg-stone-950 text-stone-100">
      <PhaseBar
        view={truth}
        connection={connection}
        mystery={mystery}
        onMysteryChange={scope === "full" ? chooseMystery : undefined}
        paused={paused}
        controls={controls}
      />
      <main
        className={`grid min-h-0 flex-1 grid-cols-1 ${mind ? "lg:grid-cols-[1fr_18rem_28rem]" : "md:grid-cols-[1fr_20rem]"}`}
      >
        <EventFeed events={shownEvents} />
        <div className="min-h-0 overflow-y-auto border-l border-stone-800">
          <Roster residents={shown.residents} inspected={inspected} onInspect={mystery ? undefined : setInspected} />
          {report && <CostMeter report={report} residents={truth.residents} mystery={mystery} />}
        </div>
        {mind && (
          <MindInspector mind={mind} residents={truth.residents} explain={explain} onClose={() => setInspected(null)} />
        )}
      </main>
    </div>
  );
}
