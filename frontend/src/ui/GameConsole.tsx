import { type ReactNode, useCallback, useMemo, useState } from "react";

import { foldEvents, isPublic } from "../core/gameView";
import { heatAt } from "../core/heat";
import { mindOf } from "../core/mind";
import { snapshotsOf, viewAt } from "../core/snapshots";
import type { CostSource } from "../net/cost";
import type { Explain } from "../net/explain";
import type { ConnectionStatus, Scope } from "../net/sources";
import { useCost } from "../net/useCost";
import type { Event, Review } from "../protocol";
import { CostMeter } from "./CostMeter";
import { EventFeed } from "./EventFeed";
import { MindInspector } from "./MindInspector";
import { PhaseBar } from "./PhaseBar";
import { PlaybackBar, usePlaybackKeys } from "./PlaybackBar";
import { PostGameReview } from "./PostGameReview";
import { Roster } from "./Roster";
import { SuspicionHeatmap } from "./SuspicionHeatmap";
import type { PlaybackView } from "./usePlayback";

type Tab = "feed" | "suspicion" | "review";

const tabLabel: Record<Tab, string> = { feed: "Feed", suspicion: "Suspicion", review: "Review" };

/**
 * The text console: phase bar, town feed, roster, cost meter and Mind inspector, for the
 * events received so far. With `playback`, it shows them only as far as playback has
 * reached (the view), with playback's controls; without, it shows them all.
 *
 * Mystery mode shows only what the whole town saw and has no inspector; a public-scope
 * page is always in mystery mode. The phase bar reads every event playback has reached,
 * mystery mode or not, so its Open-floor progress does not depend on private bids being
 * shown. The cost meter needs a `cost` source, and the Host's `controls` come from the
 * page: only the Host's has them. The cost meter shows what the game has cost so far,
 * not as of the view: the server adds up calls, not events.
 *
 * Outside mystery mode, a Suspicion tab shows the heatmap as of the view, and once the view
 * reaches the game's end the `review` opens in a Review tab. Both tell private beliefs, so
 * mystery mode (and so a public page) has neither.
 */
export function GameConsole({
  events,
  connection,
  explain,
  cost,
  scope = "full",
  paused = false,
  controls,
  playback,
  replayUrl,
  review,
}: {
  events: readonly Event[];
  connection: ConnectionStatus;
  explain?: Explain | undefined;
  cost?: CostSource | undefined;
  scope?: Scope;
  paused?: boolean;
  controls?: ReactNode;
  playback?: PlaybackView | undefined;
  /** Where to replay the game, offered once the view reaches its end. */
  replayUrl?: string | undefined;
  review?: Review | null | undefined;
}) {
  const [mysteryChosen, setMysteryChosen] = useState(false);
  const [inspected, setInspected] = useState<string | null>(null);
  const [chosenTab, setChosenTab] = useState<Tab | null>(null);
  const mystery = scope === "public" || mysteryChosen;

  const count = playback?.shown ?? events.length;
  const snapshots = useMemo(() => snapshotsOf(events), [events]);
  const view = useMemo(() => viewAt(events, snapshots, count), [events, snapshots, count]);
  const reached = useMemo(() => events.slice(0, count), [events, count]);
  const shownEvents = useMemo(() => (mystery ? reached.filter(isPublic) : reached), [reached, mystery]);
  const shownView = useMemo(() => (mystery ? foldEvents(shownEvents) : view), [mystery, shownEvents, view]);
  const mind = useMemo(() => (inspected ? mindOf(reached, inspected) : null), [reached, inspected]);
  const report = useCost(cost, events.length);
  const heat = useMemo(() => (mystery ? null : heatAt(reached)), [mystery, reached]);
  const ending = mystery ? null : view.outcome;
  const tabs: Tab[] = ["feed", ...(heat ? ["suspicion" as const] : []), ...(review && ending ? ["review" as const] : [])];
  const tab = chosenTab && tabs.includes(chosenTab) ? chosenTab : tabs.includes("review") ? "review" : "feed";

  const chooseMystery = useCallback((on: boolean) => {
    setMysteryChosen(on);
    if (on) setInspected(null);
  }, []);
  const toggleMystery = useCallback(() => chooseMystery(!mysteryChosen), [chooseMystery, mysteryChosen]);
  usePlaybackKeys(playback, scope === "full" ? toggleMystery : undefined);

  return (
    <div className="flex h-dvh flex-col bg-stone-950 text-stone-100">
      <PhaseBar
        view={view}
        connection={connection}
        mystery={mystery}
        onMysteryChange={scope === "full" ? chooseMystery : undefined}
        paused={paused}
        controls={controls}
        live={playback?.live ?? true}
      />
      {playback && (
        <PlaybackBar
          playback={playback}
          received={events.length}
          replayUrl={view.outcome ? replayUrl : undefined}
        />
      )}
      <main
        className={`grid min-h-0 flex-1 grid-cols-1 ${mind ? "lg:grid-cols-[1fr_18rem_28rem]" : "md:grid-cols-[1fr_20rem]"}`}
      >
        <div className="flex min-h-0 flex-col">
          {tabs.length > 1 && (
            <div role="tablist" aria-label="What to show" className="flex gap-1 border-b border-stone-800 px-6 pt-2">
              {tabs.map((name) => (
                <button
                  key={name}
                  type="button"
                  role="tab"
                  aria-selected={tab === name}
                  onClick={() => setChosenTab(name)}
                  className="rounded-t px-3 py-1 text-sm text-stone-400 aria-selected:bg-stone-800 aria-selected:text-amber-200"
                >
                  {tabLabel[name]}
                </button>
              ))}
            </div>
          )}
          {tab === "feed" && <EventFeed events={shownEvents} />}
          {tab === "suspicion" && heat && <SuspicionHeatmap heat={heat} residents={view.residents} />}
          {tab === "review" && review && ending && (
            <PostGameReview review={review} events={reached} outcome={ending} />
          )}
        </div>
        <div className="min-h-0 overflow-y-auto border-l border-stone-800">
          <Roster residents={shownView.residents} inspected={inspected} onInspect={mystery ? undefined : setInspected} />
          {report && <CostMeter report={report} residents={view.residents} mystery={mystery} />}
        </div>
        {mind && (
          <MindInspector mind={mind} residents={view.residents} explain={explain} onClose={() => setInspected(null)} />
        )}
      </main>
    </div>
  );
}
