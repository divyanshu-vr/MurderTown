/** One line of the town feed for each event, or null for events the feed does not show. */
import type { Event } from "../protocol";
import { phaseLabel, roleLabel, victoryLabel } from "./labels";

export function describeEvent(event: Event): string | null {
  const payload = event.payload;
  switch (payload.type) {
    case "game_started":
      return `${payload.residents.length} Residents move into town.`;
    case "role_assigned":
      return null; // roles live in the roster
    case "phase_started":
      return `Day ${payload.day}: ${phaseLabel[payload.phase]}`;
    case "statement_made":
      return `${payload.speaker}: "${payload.text}"`;
    case "ballot_cast":
      return payload.target === null
        ? `${payload.voter} votes to skip.`
        : `${payload.voter} votes for ${payload.target}.`;
    case "vote_resolved":
      return payload.banished ? `${payload.banished} is banished.` : "Nobody is banished.";
    case "resident_died":
      return `${payload.resident} leaves town forever. They were a ${roleLabel[payload.role]}.`;
    case "game_ended":
      return `${victoryLabel[payload.winner]}. ${payload.reason}`;
  }
}
