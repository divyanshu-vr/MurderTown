import { type ReactNode, useCallback, useMemo, useState } from "react";

import { EVERYTHING, type FeedFilter, offeredKinds } from "../core/feedFilter";
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
import { TownView } from "./TownView";
import type { PlaybackView } from "./usePlayback";

type Tab = "feed" | "residents" | "suspicion" | "review" | "mind";

const tabLabel: Record<Tab, string> = {
  feed: "Feed",
  residents: "Residents",
  suspicion: "Suspicion",
  review: "Review",
  mind: "Mind",
};

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
 * Once the view reaches the end of a game a side won, a Review tab tells who won and who everyone
 * was. Outside mystery mode, a Suspicion tab shows the heatmap as of the view, and the Review tab
 * also holds the server's full-scope `review` (of an aborted game too) and opens by itself. The heatmap and the server's review
 * tell private beliefs, so mystery mode (and so a public page) shows neither.
 *
 * With the `townView` (and playback to play it), the Town view takes the main space and every
 * panel becomes a tab beside it, or below it on a narrow screen: the feed, the Residents with the
 * cost meter, and the Mind inspector while someone is inspected. The Town view shows what the
 * panels show, mystery mode included.
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
  townView = false,
  startsInMystery = false,
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
  /** Whether to draw the Town view: the page decides, as only a browser with WebGL can. */
  townView?: boolean;
  /** Whether to open in mystery mode, which the Spectator can leave. */
  startsInMystery?: boolean;
}) {
  const [mysteryChosen, setMysteryChosen] = useState(startsInMystery);
  const [inspected, setInspected] = useState<string | null>(null);
  const [chosenTab, setChosenTab] = useState<Tab | null>(null);
  const [feedFilter, setFeedFilter] = useState<FeedFilter>(EVERYTHING);
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
  const names = useMemo(() => shownView.residents.map((resident) => resident.name), [shownView.residents]);
  const ending = shownView.outcome;
  const fullReview = mystery ? null : (review ?? null);
  const withTownView = townView && playback !== undefined;

  // beside the Town view, the Mind inspector is a tab of its own, opened from the Residents tab
  const inspect = useCallback(
    (name: string) => {
      setInspected(name);
      if (withTownView) setChosenTab("mind");
    },
    [withTownView],
  );
  const closeMind = useCallback(() => {
    setInspected(null);
    if (withTownView) setChosenTab("residents");
  }, [withTownView]);
  const panels: Partial<Record<Tab, ReactNode>> = {
    feed: (
      <EventFeed
        events={shownEvents}
        residents={names}
        kinds={offeredKinds(mystery)}
        filter={feedFilter}
        onFilterChange={setFeedFilter}
        typing={playback && { pace: playback.pace, held: playback.held }}
      />
    ),
    residents: (
      <div className="min-h-0 overflow-y-auto">
        <Roster residents={shownView.residents} inspected={inspected} onInspect={mystery ? undefined : inspect} />
        {report && <CostMeter report={report} residents={view.residents} mystery={mystery} />}
      </div>
    ),
    ...(heat && { suspicion: <SuspicionHeatmap heat={heat} residents={view.residents} /> }),
    ...(ending && (ending.ended === "won" || fullReview) && {
      review: (
        <PostGameReview review={fullReview} residents={shownView.residents} events={reached} outcome={ending} />
      ),
    }),
    ...(mind && { mind: <MindInspector mind={mind} residents={view.residents} explain={explain} onClose={closeMind} /> }),
  };
  const tabs = (
    withTownView ? (["feed", "residents", "suspicion", "review", "mind"] as const) : (["feed", "suspicion", "review"] as const)
  ).filter((name) => panels[name]);
  const tab = chosenTab && tabs.includes(chosenTab) ? chosenTab : ending && fullReview ? "review" : "feed";
  const tabList = tabs.length > 1 && <TabList tabs={tabs} chosen={tab} onChoose={setChosenTab} />;

  const chooseMystery = useCallback((on: boolean) => {
    setMysteryChosen(on);
    if (on) setInspected(null);
    setFeedFilter((filter) => ({ ...filter, kinds: EVERYTHING.kinds })); // the kinds on offer change
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
      {withTownView ? (
        <main className="flex min-h-0 flex-1 flex-col md:flex-row">
          <TownView
            view={shownView}
            shown={shownEvents}
            reached={reached.at(-1)?.seq ?? 0}
            playback={playback}
            mystery={mystery}
          />
          <div className="flex min-h-0 flex-1 flex-col border-stone-800 md:w-[26rem] md:flex-none md:border-l">
            {tabList}
            {panels[tab]}
          </div>
        </main>
      ) : (
        <main
          className={`grid min-h-0 flex-1 grid-cols-1 ${mind ? "lg:grid-cols-[1fr_18rem_28rem]" : "md:grid-cols-[1fr_20rem]"}`}
        >
          <div className="flex min-h-0 flex-col">
            {tabList}
            {panels[tab]}
          </div>
          <div className="flex min-h-0 flex-col border-l border-stone-800">{panels.residents}</div>
          {panels.mind}
        </main>
      )}
    </div>
  );
}

function TabList({ tabs, chosen, onChoose }: { tabs: readonly Tab[]; chosen: Tab; onChoose(tab: Tab): void }) {
  return (
    <div role="tablist" aria-label="What to show" className="flex flex-wrap gap-1 border-b border-stone-800 px-6 pt-2">
      {tabs.map((name) => (
        <button
          key={name}
          type="button"
          role="tab"
          aria-selected={chosen === name}
          onClick={() => onChoose(name)}
          className="rounded-t px-3 py-1 text-sm text-stone-400 aria-selected:bg-stone-800 aria-selected:text-amber-200"
        >
          {tabLabel[name]}
        </button>
      ))}
    </div>
  );
}
