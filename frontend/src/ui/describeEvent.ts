/** One line for each event, in the words the feed and the Mind inspector use. */
import type { Event, Role } from "../protocol";
import { activityLabel, deathLabel, decisionLabel, phaseLabel, roleLabel, victoryLabel } from "./labels";

export function describeEvent(event: Event): string {
  const payload = event.payload;
  switch (payload.type) {
    case "game_configured":
      return `The Host sets up a game of ${payload.config.residents} Residents with seed ${payload.config.seed}.`;
    case "game_started":
      return `${payload.residents.length} Residents move into town.`;
    case "role_assigned":
      return `${payload.resident} is secretly a ${roleLabel[payload.role]}.`;
    case "phase_started":
      return `Day ${payload.day}: ${phaseLabel[payload.phase]}`;
    case "bid_placed":
      return payload.urgency > 0
        ? `${payload.resident} bids ${payload.urgency} to speak next: ${payload.reason}`
        : `${payload.resident} bids 0 and listens: ${payload.reason}`;
    case "statement_made":
      return `${payload.speaker}: "${payload.text}"`;
    case "open_floor_timed_out":
      return "Time is up on the Open floor.";
    case "sheriff_fired":
      return `${payload.sheriff}, the Sheriff, fires at ${payload.target}!`;
    case "sheriff_held_fire":
      return `${payload.sheriff}, the Sheriff, holds fire.`;
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
    case "den_message_posted":
      return `${payload.murderer}, in the Den: "${payload.text}"${
        payload.proposed_victim ? ` (proposes ${payload.proposed_victim})` : ""
      }`;
    case "kill_vote_cast":
      return `${payload.murderer} votes to kill ${payload.target}.`;
    case "victim_chosen":
      return `The Murderers choose ${payload.victim}.`;
    case "resident_protected":
      return `${payload.doctor}, the Doctor, protects ${payload.target}.`;
    case "resident_investigated":
      return `${payload.detective}, the Detective, learns that ${payload.target} is ${
        payload.found_murderer ? "a Murderer" : "not a Murderer"
      }.`;
    case "attack_thwarted":
      return `${payload.saved ?? "Someone"} was attacked in the night, but the Doctor saved them.`;
    case "recap_narrated":
      return `Narrator: ${payload.text}`;
    case "dusk_intent_chosen":
      return payload.activity === "talk"
        ? `${payload.resident} hopes to talk with ${listed(payload.partners, "or")} about ${payload.topic}.`
        : `${payload.resident} means to ${activityLabel[payload.activity]}.`;
    case "conversation_started":
      return `${listed(payload.residents)} slip away to talk privately.`;
    case "conversation_message_posted":
      return `${payload.speaker} to ${payload.partner}: "${payload.text}"`;
    case "reflection_written":
      return `${payload.resident} writes a reflection.`;
    case "decision_fell_back":
      return `${payload.resident}'s ${decisionLabel[payload.kind]} ${fellBack(payload.reason)}`;
    case "roles_revealed":
      return `Every role is revealed: ${whoWasWho(payload.roles)}.`;
    case "game_ended":
      return `${victoryLabel[payload.winner]}. ${payload.reason}`;
    case "decision_unanswered":
      return `${payload.resident}'s ${decisionLabel[payload.kind]} got no answer: ${payload.reason}`;
    case "game_aborted":
      return `The game is aborted: ${payload.reason}`;
  }
}

/**
 * Whether the town feed shows an event. It leaves out the Host's setup, role assignments
 * (the roster shows roles), private reflections (the Mind inspector shows them) and bids to listen.
 */
export function inFeed(event: Event): boolean {
  const payload = event.payload;
  return !(
    payload.type === "game_configured" ||
    payload.type === "role_assigned" ||
    payload.type === "reflection_written" ||
    (payload.type === "bid_placed" && payload.urgency === 0)
  );
}

/** Names as a sentence lists them: "Cora", "Cora and Rosa", "Cora, Rosa and Kit" (or "or"). */
function listed(names: readonly string[], conjunction: "and" | "or" = "and"): string {
  return names.length > 1 ? `${names.slice(0, -1).join(", ")} ${conjunction} ${names.at(-1)}` : (names[0] ?? "");
}

/**
 * Who held each role: the Murderers first, then the holder of every other role in the order
 * `roleLabel` lists them, then the Civilians, unnamed.
 */
function whoWasWho(roles: Readonly<Record<string, Role>>): string {
  const holders = (role: Role) => Object.keys(roles).filter((name) => roles[name] === role);
  const murderers = holders("murderer");
  const others = (Object.keys(roleLabel) as Role[])
    .filter((role) => role !== "murderer" && role !== "civilian")
    .flatMap((role) => holders(role).map((name) => `${name} the ${roleLabel[role]}`));
  const told = [`${listed(murderers)} ${murderers.length > 1 ? "were the Murderers" : "was the Murderer"}`, ...others];
  return `${listed(told)}${holders("civilian").length > 0 ? "; the rest were Civilians" : ""}`;
}

/** How every view words a Fallback. */
export function fellBack(reason: string): string {
  return `fell back to a safe default: ${reason}`;
}
