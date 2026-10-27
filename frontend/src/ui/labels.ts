/** Every name the interface shows for a domain value, in one place. Vocabulary follows GLOSSARY.md. */
import type { PayloadOf, Phase, Role, Side } from "../protocol";

export const phaseLabel: Record<Phase, string> = {
  setup: "Setting up",
  dawn: "Dawn",
  discussion: "Discussion",
  showdown: "Showdown",
  vote: "Vote",
  dusk: "Dusk",
  night: "Night",
  ended: "Game over",
};

export const roleLabel: Record<Role, string> = {
  murderer: "Murderer",
  doctor: "Doctor",
  detective: "Detective",
  sheriff: "Sheriff",
  civilian: "Civilian",
};

export const victoryLabel: Record<Side, string> = {
  town: "The Town wins",
  murderers: "The Murderers win",
};

export const fateLabel: Record<PayloadOf<"resident_died">["cause"], string> = {
  banished: "Banished",
};
