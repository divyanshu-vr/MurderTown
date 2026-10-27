/** One line of the town feed for each event, or null for events the feed does not show. */
import type { Event } from "../protocol";
import { deathLabel, decisionLabel, phaseLabel, roleLabel, victoryLabel } from "./labels";

export function describeEvent(event: Event): string | null {
  const payload = event.payload;
  switch (payload.type) {
    case "game_started":
      return `${payload.residents.length} Residents move into town.`;
    case "role_assigned":
      return null; // roles live in the roster
    case "phase_started":
      return `Day ${payload.day}: ${phaseLabel[payload.phase]}`;
    case "bid_placed":
      return payload.urgency > 0 // a bid of 0 only means listening, so the feed leaves it out
        ? `${payload.resident} bids ${payload.urgency} to speak next: ${payload.reason}`
        : null;
    case "statement_made":
      return `${payload.speaker}: "${payload.text}"`;
    case "sheriff_fired":
      return `${payload.sheriff}, the Sheriff, fires at ${payload.target}!`;
    case "last_words_spoken":
      return `${payload.resident}'s last words: "${payload.text}"`;
    case "ballot_cast":
      return payload.target === null
        ? `${payload.voter} votes to skip.`
        : `${payload.voter} votes for ${payload.target}.`;
    case "vote_resolved":
      return payload.banished ? `${payload.banished} is banished.` : "Nobody is banished.";
    case "resident_died":
      return `${payload.resident} ${deathLabel[payload.cause]}. They were a ${roleLabel[payload.role]}.`;
    case "reflection_written":
      return null; // private notes belong in the Mind inspector, not the town feed
    case "decision_fell_back":
      return `${payload.resident}'s ${decisionLabel[payload.kind]} used a safe default: ${payload.reason}`;
    case "game_ended":
      return `${victoryLabel[payload.winner]}. ${payload.reason}`;
  }
}
