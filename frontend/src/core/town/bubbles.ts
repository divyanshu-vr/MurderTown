/**
 * The bubbles over the town: whom each hangs over and what it says. A bubble keeps its key while
 * its words are said in the same place (the day's speaker, each Conversation, the Den), so new
 * words type out in the same bubble. Mystery mode hears no private words, so each Conversation
 * under way gets a muffled line over both of its pair instead.
 */
import { keyOf, type Stage } from "./stage";

export interface Bubble {
  key: string;
  over: readonly string[];
  /** The words to type out, and when they were said; none for a muffled line. */
  text: string | null;
  seq: number | null;
}

export function bubblesOf(stage: Stage, mystery: boolean): Bubble[] {
  const said = stage.said.map(({ key, seq, speaker, text }) => ({ key, over: [speaker], text, seq }));
  if (!mystery) return said;
  return [...said, ...stage.pairs.map((pair) => ({ key: keyOf(pair), over: pair, text: null, seq: null }))];
}
