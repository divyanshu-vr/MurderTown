import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef } from "react";

import {
  chosenLines,
  EVERYTHING,
  type FeedFilter,
  type FeedKind,
  filterKey,
  flipKind,
  isFiltered,
} from "../core/feedFilter";
import type { Event } from "../protocol";
import { describeEvent, inFeed } from "./describeEvent";
import { feedKindLabel } from "./labels";
import { inputStyle, pillStyle, toggleStyle } from "./styles";

const toneByKind: Partial<Record<Event["payload"]["type"], string>> = {
  phase_started: "mt-4 font-semibold text-amber-200",
  bid_placed: "text-sm text-stone-500",
  statement_made: "text-stone-100",
  open_floor_timed_out: "text-sm text-stone-400",
  sheriff_fired: "font-semibold text-rose-200",
  sheriff_held_fire: "text-sm text-stone-500",
  last_words_spoken: "italic text-stone-200",
  den_message_posted: "text-rose-200/80",
  kill_vote_cast: "text-sm text-rose-300/70",
  victim_chosen: "text-rose-300",
  resident_protected: "text-sm text-sky-300/80",
  resident_investigated: "text-sm text-sky-300/80",
  attack_thwarted: "font-medium text-sky-200",
  recap_narrated: "italic text-amber-100",
  dusk_intent_chosen: "text-sm text-stone-500",
  conversation_started: "text-violet-200",
  conversation_message_posted: "text-violet-100/90",
  ballot_cast: "text-sm text-stone-400",
  vote_resolved: "font-medium text-stone-200",
  resident_died: "font-medium text-rose-300",
  decision_fell_back: "text-sm italic text-stone-500",
  roles_revealed: "mt-4 font-medium text-amber-200",
  game_ended: "mt-4 text-lg font-semibold text-amber-300",
  game_aborted: "mt-4 font-semibold text-rose-300",
};

/** How close to the bottom (in pixels) still counts as "following along". */
const FOLLOW_THRESHOLD = 80;

/**
 * The town feed: a line for each event, filtered by kind of line and by Resident as the
 * Spectator chooses (the console keeps the `filter`, so it lasts while another tab is open).
 * Every line stays in the page, so the log reads whole to a screen reader, but the browser lays
 * out and paints only the lines on screen, and a new event renders only its own line.
 */
export function EventFeed({
  events,
  residents,
  kinds,
  filter,
  onFilterChange,
}: {
  events: readonly Event[];
  residents: readonly string[];
  /** The kinds of line on offer. */
  kinds: readonly FeedKind[];
  filter: FeedFilter;
  onFilterChange(filter: FeedFilter): void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const following = useRef(true);
  const lines = useMemo(() => events.filter(inFeed), [events]);
  const shown = useMemo(() => chosenLines(lines, filter, kinds), [lines, filter, kinds]);
  const key = filterKey(filter);

  const pinToBottom = useCallback(() => {
    const element = scroller.current;
    if (element && following.current) element.scrollTop = element.scrollHeight;
  }, []);
  useLayoutEffect(pinToBottom, [shown, pinToBottom]);
  // a line grows from its stand-in size once it is first drawn, so pin again as the list grows
  useEffect(() => {
    const list = scroller.current?.firstElementChild;
    if (!list || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(pinToBottom);
    observer.observe(list);
    return () => observer.disconnect();
  }, [key, pinToBottom]);

  const noteScroll = () => {
    const element = scroller.current;
    if (!element) return;
    following.current = element.scrollHeight - element.scrollTop - element.clientHeight < FOLLOW_THRESHOLD;
  };
  const choose = (next: FeedFilter) => {
    following.current = true;
    onFilterChange(next);
  };

  return (
    <div className="flex min-h-0 flex-col">
      {lines.length > 0 && <FeedFilters kinds={kinds} residents={residents} filter={filter} onChange={choose} />}
      {/* a new choice is a new log, so a screen reader is not read every line it brings back */}
      <div
        key={key}
        ref={scroller}
        onScroll={noteScroll}
        role="log"
        aria-label="Town feed"
        className="min-h-0 overflow-y-auto px-6 py-4"
      >
        <ol className="space-y-1">
          {shown.map((event) => (
            <FeedLine key={event.seq} event={event} />
          ))}
        </ol>
      </div>
    </div>
  );
}

/** One line. A line off screen is neither laid out nor painted, and keeps its last size meanwhile. */
const FeedLine = memo(function FeedLine({ event }: { event: Event }) {
  return (
    <li
      data-kind={event.payload.type}
      className={`[contain-intrinsic-size:auto_1.5rem] [content-visibility:auto] motion-safe:animate-[appear_300ms_ease-out] ${toneByKind[event.payload.type] ?? ""}`}
    >
      {describeEvent(event)}
    </li>
  );
});

/** The kinds of line the feed holds, each shown or not, one Resident to follow, and a way back to everything. */
function FeedFilters({
  kinds,
  residents,
  filter,
  onChange,
}: {
  kinds: readonly FeedKind[];
  residents: readonly string[];
  filter: FeedFilter;
  onChange(filter: FeedFilter): void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-stone-800 px-6 py-2 text-sm">
      {kinds.length > 1 && (
        <div role="group" aria-label="Show" className="flex flex-wrap gap-1">
          {kinds.map((kind) => (
            <button
              key={kind}
              type="button"
              aria-pressed={filter.kinds.has(kind)}
              onClick={() => onChange(flipKind(filter, kind))}
              className={toggleStyle}
            >
              {feedKindLabel[kind]}
            </button>
          ))}
        </div>
      )}
      <label className="flex items-center gap-2 text-stone-400">
        Resident
        <select
          value={filter.resident ?? ""}
          onChange={(change) => onChange({ ...filter, resident: change.target.value || null })}
          className={inputStyle}
        >
          <option value="">Everyone</option>
          {residents.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </label>
      {isFiltered(filter, kinds) && (
        <button
          type="button"
          onClick={() => onChange(EVERYTHING)}
          className={pillStyle}
        >
          Show everything
        </button>
      )}
    </div>
  );
}
