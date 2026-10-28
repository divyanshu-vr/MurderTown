import { useLayoutEffect, useRef } from "react";

import type { Event } from "../protocol";
import { describeEvent, inFeed } from "./describeEvent";

const toneByKind: Partial<Record<Event["payload"]["type"], string>> = {
  phase_started: "mt-4 font-semibold text-amber-200",
  bid_placed: "text-sm text-stone-500",
  statement_made: "text-stone-100",
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
  game_ended: "mt-4 text-lg font-semibold text-amber-300",
  game_aborted: "mt-4 font-semibold text-rose-300",
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
        {events.filter(inFeed).map((event) => (
          <li key={event.seq} data-kind={event.payload.type} className={toneByKind[event.payload.type]}>
            {describeEvent(event)}
          </li>
        ))}
      </ol>
    </div>
  );
}
