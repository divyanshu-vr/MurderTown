/** Seam 3 (unit): the bubbles over the town, in full and in mystery mode, from the recorded game. */
import { describe, expect, it } from "vitest";

import { present } from "../../../test/present";
import { eventsOf, recordedGame } from "../../../test/recordedGame";
import type { Event } from "../../protocol";
import { isPublic } from "../gameView";
import { bubblesOf } from "./bubbles";
import { stageOf } from "./stage";

const events = recordedGame();
const stageAt = ({ seq }: Event, shown: readonly Event[] = events) => stageOf(shown.filter((event) => event.seq <= seq));
const firstMessage = present(eventsOf(events, "conversation_message_posted")[0], "a Conversation's message");
const secondMessage = present(eventsOf(events, "conversation_message_posted")[1], "its reply");

describe("the bubbles over the town", () => {
  it("types each Conversation's words over its speaker, in one bubble the Conversation keeps", () => {
    const [first] = bubblesOf(stageAt(firstMessage), false);
    const [reply] = bubblesOf(stageAt(secondMessage), false);

    expect(first).toMatchObject({ over: [firstMessage.payload.speaker], text: firstMessage.payload.text, seq: firstMessage.seq });
    expect(reply).toMatchObject({ key: first?.key, over: [secondMessage.payload.speaker], text: secondMessage.payload.text });
  });

  it("in mystery mode muffles every Conversation under way, over both of its pair", () => {
    const shown = events.filter(isPublic);
    const stage = stageAt(firstMessage, shown);

    expect(bubblesOf(stage, true)).toEqual(stage.pairs.map((pair) => expect.objectContaining({ over: pair, text: null })));
  });

  it("in mystery mode still shows what is said aloud by day", () => {
    const statement = present(eventsOf(events, "statement_made")[0], "a Statement");

    expect(bubblesOf(stageAt(statement, events.filter(isPublic)), true)).toMatchObject([{ text: statement.payload.text }]);
  });
});
