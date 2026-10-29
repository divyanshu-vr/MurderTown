/** Seam 3 (unit): what following the action frames, from the recorded game. */
import { describe, expect, it } from "vitest";

import town from "../../../assets/town/town.json";
import { present } from "../../../test/present";
import { countOf, countWhen, eventsOf, recordedGame } from "../../../test/recordedGame";
import type { Event } from "../../protocol";
import { foldEvents, isPublic } from "../gameView";
import { focusOf } from "./focus";
import { layoutFor, middleOf, type Point } from "./layout";
import { type Area, planOf } from "./plan";
import { stageOf } from "./stage";

const plan = planOf(town);
const events = recordedGame();
const wholeTown = { x: 0, y: 0, width: plan.grid.width, height: plan.grid.height };

function at(count: number, shown: readonly Event[] = events) {
  const happened = shown.filter((event) => event.seq <= (events[count - 1]?.seq ?? 0));
  const [view, stage] = [foldEvents(happened), stageOf(happened)];
  const placed = layoutFor(view, stage, plan);
  return { view, stage, placed, focus: focusOf(view, stage, plan, placed) };
}

const holds = (area: Area, { x, y }: Point) => x > area.x && y > area.y && x < area.x + area.width && y < area.y + area.height;

describe("following the action", () => {
  it("frames everyone gathered in the square by day", () => {
    const { view, stage, focus } = at(countWhen(events, "discussion", 1));

    expect(focus).not.toEqual(wholeTown);
    const gathered = layoutFor(view, stage, plan).filter(({ dead }) => !dead); // the first Night's Victim lies at home
    expect(gathered.every(({ at: spot }) => holds(focus, spot))).toBe(true);
  });

  it("shows the whole town at Dawn, and at Dusk until a Conversation talks", () => {
    expect(at(countWhen(events, "dawn", 2)).focus).toEqual(wholeTown);
    const firstWords = present(eventsOf(events, "conversation_message_posted")[0], "a Conversation's first words");
    expect(at(countOf(events, firstWords) - 1).focus).toEqual(wholeTown);
  });

  it("frames the Conversation talking at Dusk, one after another", () => {
    const messages = eventsOf(events, "conversation_message_posted");
    const nextTalk = present(
      messages.find(({ day, payload }, i) => {
        const before = messages[i - 1];
        return before?.day === day && ![before.payload.speaker, before.payload.partner].includes(payload.speaker);
      }),
      "the first words of a Dusk's second Conversation",
    );
    const { placed, focus } = at(countOf(events, nextTalk));

    const pair = placed.filter(({ name }) => [nextTalk.payload.speaker, nextTalk.payload.partner].includes(name));
    expect(pair).toHaveLength(2);
    expect(pair.every(({ at: spot }) => holds(focus, spot))).toBe(true);
    expect(focus).not.toEqual(wholeTown);
  });

  it("goes to the Den while the Murderers meet there, then to each house visited at Night", () => {
    const denMessage = present(eventsOf(events, "den_message_posted")[0], "a Den message");
    const investigated = present(eventsOf(events, "resident_investigated")[0], "an investigation");
    const visited = at(countOf(events, investigated));
    const seat = present(visited.view.residents.find(({ name }) => name === investigated.payload.target), "the visited").seat;

    expect(holds(at(countOf(events, denMessage)).focus, middleOf(plan.den))).toBe(true);
    expect(holds(visited.focus, middleOf(present(plan.doors[seat], "their door")))).toBe(true);
  });

  it("in mystery mode shows the whole town all Night, seeing no Den and no visits", () => {
    const investigated = present(eventsOf(events, "resident_investigated")[0], "an investigation");

    expect(at(countOf(events, investigated), events.filter(isPublic)).focus).toEqual(wholeTown);
  });
});
