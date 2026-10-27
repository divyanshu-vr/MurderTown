import { useLayoutEffect, useRef } from "react";

import type { Event } from "../protocol";
import { describeEvent } from "./describeEvent";

const toneByKind: Partial<Record<Event["payload"]["type"], string>> = {
  phase_started: "mt-4 font-semibold text-amber-200",
  statement_made: "text-stone-100",
  ballot_cast: "text-sm text-stone-400",
  vote_resolved: "font-medium text-stone-200",
  resident_died: "font-medium text-rose-300",
  decision_fell_back: "text-sm italic text-stone-500",
  game_ended: "mt-4 text-lg font-semibold text-amber-300",
};

/** How close to the bottom (in pixels) still counts as "following along". */
const FOLLOW_THRESHOLD = 80;

export function EventFeed({ events }: { events: readonly Event[] }) {
  const scroller = useRef<HTMLDivElement>(null);
  const following = useRef(true);

  useLayoutEffect(() => {
    const element = scroller.current;
    if (element && following.current) element.scrollTop = element.scrollHeight;
  }, [events]);

  const noteScroll = () => {
    const element = scroller.current;
    if (!element) return;
    following.current = element.scrollHeight - element.scrollTop - element.clientHeight < FOLLOW_THRESHOLD;
  };

  return (
    <div
      ref={scroller}
      onScroll={noteScroll}
      role="log"
      aria-label="Town feed"
      className="min-h-0 overflow-y-auto px-6 py-4"
    >
      <ol className="space-y-1">
        {events.map((event) => {
          const line = describeEvent(event);
          return (
            line && (
              <li key={event.seq} data-kind={event.payload.type} className={toneByKind[event.payload.type]}>
                {line}
              </li>
            )
          );
        })}
      </ol>
    </div>
  );
}
