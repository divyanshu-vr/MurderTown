/** Seam 3 (unit): what is said, voted and done on stage, from the recorded game. */
import { describe, expect, it } from "vitest";

import { present } from "../../../test/present";
import { eventsOf, recordedGame } from "../../../test/recordedGame";
import type { Event } from "../../protocol";
import { isPublic } from "../gameView";
import { stageOf } from "./stage";

const events = recordedGame();
const stageAt = ({ seq }: Event, shown: readonly Event[] = events) => stageOf(shown.filter((event) => event.seq <= seq));
const after = ({ seq }: Event, matching: (event: Event) => boolean, what: string) =>
  present(events.find((event) => event.seq > seq && matching(event)), what);
const nextPhaseAfter = (event: Event) => after(event, ({ payload }) => payload.type === "phase_started", "a later Phase");
const first = <T extends Event["payload"]["type"]>(type: T) => present(eventsOf(events, type)[0], `a ${type}`);

describe("what is on stage by day", () => {
  const [firstStatement, secondStatement] = eventsOf(events, "statement_made");

  it("shows the latest words said until someone else speaks or the Phase ends", () => {
    const statement = present(firstStatement, "a Statement");
    const next = present(secondStatement, "a second Statement");

    expect(stageAt(statement).said).toMatchObject([
      { seq: statement.seq, speaker: statement.payload.speaker, text: statement.payload.text },
    ]);
    expect(stageAt(next).said.map(({ speaker }) => speaker)).toEqual([next.payload.speaker]);
    expect(stageAt(nextPhaseAfter(statement)).said).toEqual([]);
  });

  it("gives the banished their last words", () => {
    const lastWords = first("last_words_spoken");

    expect(stageAt(lastWords).said).toMatchObject([{ speaker: lastWords.payload.resident, text: lastWords.payload.text }]);
  });

  it("draws each ballot cast so far in the Vote, counting them up to the Vote's own tally", () => {
    const resolved = first("vote_resolved");
    const ballots = eventsOf(events, "ballot_cast").filter((ballot) => ballot.seq < resolved.seq);
    const againstSomeone = present(ballots.find((ballot) => ballot.payload.target !== null), "a ballot against someone");
    const target = present(againstSomeone.payload.target, "a target");

    const early = stageAt(againstSomeone);
    expect(early.ballots.at(-1)).toEqual({ voter: againstSomeone.payload.voter, target });
    expect(early.counts.get(target)).toBe(1);

    const atTheEnd = stageAt(resolved);
    expect(Object.fromEntries(atTheEnd.counts)).toEqual(resolved.payload.tally);
    expect(atTheEnd.ballots).toHaveLength(ballots.length - resolved.payload.skips);
    expect(stageAt(nextPhaseAfter(resolved)).ballots).toEqual([]);
  });
});

describe("what is on stage at Dusk", () => {
  const [firstWave, , , secondWave] = eventsOf(events, "conversation_started");
  const conversationStarted = present(firstWave, "a Conversation");
  const laterWave = present(secondWave, "a later Conversation");
  const messages = eventsOf(events, "conversation_message_posted");
  const isTalk = ({ payload }: Event) => payload.type === "conversation_message_posted" || payload.type === "conversation_started";

  it("knows what each Resident chose to do", () => {
    const intents = eventsOf(events, "dusk_intent_chosen").filter((intent) => intent.seq < conversationStarted.seq);

    expect(Object.fromEntries(stageAt(conversationStarted).activities)).toEqual(
      Object.fromEntries(intents.map(({ payload }) => [payload.resident, payload.activity])),
    );
  });

  it("holds the latest wave's Conversations, each saying its latest words", () => {
    const firstWords = present(messages[0], "a message");
    const stage = stageAt(firstWords);

    expect(stage.pairs).toHaveLength(3);
    expect(stage.said).toMatchObject([{ speaker: firstWords.payload.speaker, text: firstWords.payload.text }]);
    expect(stageAt(laterWave).pairs).toEqual([laterWave.payload.residents]);
    expect(stageAt(laterWave).said).toEqual([]);
  });

  it("lets a Conversation that has ended be heard to its last words, then lets its pair go", () => {
    const ending = present(messages.find(({ payload }) => payload.ends_conversation), "a Conversation ending");
    const pairOf = ({ speaker, partner }: { speaker: string; partner: string }) => (pair: readonly string[]) =>
      pair.includes(speaker) && pair.includes(partner);

    expect(stageAt(ending).pairs.some(pairOf(ending.payload))).toBe(true);
    expect(stageAt(ending).said.map(({ text }) => text)).toContain(ending.payload.text);

    const next = after(ending, isTalk, "more talk");
    expect(stageAt(next).pairs.some(pairOf(ending.payload))).toBe(false);
  });

  it("in mystery mode still sees who is talking, but not what they say or chose to do", () => {
    const seen = stageAt(present(messages[0], "a message"), events.filter(isPublic));

    expect(seen.pairs).toHaveLength(3);
    expect(seen.said).toEqual([]);
    expect(seen.activities.size).toBe(0);
  });
});

describe("what is on stage at Night", () => {
  const firstDenMessage = first("den_message_posted");
  const victimChosen = first("victim_chosen");
  const protectedOne = first("resident_protected");
  const investigated = first("resident_investigated");

  it("has the Murderers meet in the Den, saying their latest words there", () => {
    const stage = stageAt(firstDenMessage);

    expect(stage.den).toEqual(firstDenMessage.payload.den);
    expect(stage.said).toMatchObject([{ speaker: firstDenMessage.payload.murderer, text: firstDenMessage.payload.text }]);
    expect(stage.visits).toEqual([]);
  });

  it("sends the Murderers to their Victim's house, then the Doctor and the Detective to theirs", () => {
    const murderers = victimChosen.payload.den.map((visitor) => ({ visitor, target: victimChosen.payload.victim }));
    const doctor = { visitor: protectedOne.payload.doctor, target: protectedOne.payload.target };
    const detective = { visitor: investigated.payload.detective, target: investigated.payload.target };

    expect(stageAt(victimChosen)).toMatchObject({ den: [], said: [], visits: murderers });
    expect(stageAt(investigated).visits).toEqual([...murderers, doctor, detective]);
  });

  it("sends a lone Murderer straight to their Victim, with no Den to meet in", () => {
    const alone = present(
      eventsOf(events, "victim_chosen").find(({ payload }) => payload.den.length === 1),
      "a lone Murderer's Victim",
    );
    const vote = present(eventsOf(events, "kill_vote_cast").findLast(({ seq }) => seq < alone.seq), "their kill vote");

    expect(stageAt(vote).den).toEqual([]);
    expect(stageAt(alone).visits).toEqual([{ visitor: alone.payload.den[0], target: alone.payload.victim }]);
  });

  it("in mystery mode shows no Den and no visits", () => {
    expect(stageAt(investigated, events.filter(isPublic))).toMatchObject({ den: [], visits: [], said: [] });
  });
});

describe("what is on stage at Dawn", () => {
  it("has the Narrator's Recap", () => {
    const recap = first("recap_narrated");

    expect(stageAt(recap).recap).toBe(recap.payload.text);
    expect(stageAt(nextPhaseAfter(recap)).recap).toBeNull();
  });

  it("knows who was found murdered, until the Phase ends", () => {
    const murder = present(
      eventsOf(events, "resident_died").find(({ payload }) => payload.cause === "murdered"),
      "a murder",
    );
    const banished = first("resident_died");

    expect(stageAt(murder).foundMurdered).toEqual([murder.payload.resident]);
    expect(stageAt(banished).foundMurdered).toEqual([]);
    expect(stageAt(nextPhaseAfter(murder)).foundMurdered).toEqual([]);
  });
});
