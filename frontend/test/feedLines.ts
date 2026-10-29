import type { Event } from "../src/protocol";

type Kind = Event["payload"]["type"];

/** What only some saw by day or at Dusk, as the feed's Private filter should show it. */
export const PRIVATE_LINES: readonly Kind[] = [
  "bid_placed",
  "dusk_intent_chosen",
  "conversation_message_posted",
  "sheriff_held_fire",
];

/** The Night's secret actions, as the feed's Night filter should show them. */
export const NIGHT_LINES: readonly Kind[] = [
  "den_message_posted",
  "kill_vote_cast",
  "victim_chosen",
  "resident_protected",
  "resident_investigated",
];
