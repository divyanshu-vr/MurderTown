import { fellBack } from "./describeEvent";

/** The note under a decision that fell back, worded as the feed words it. */
export function FallbackNote({ reason }: { reason: string }) {
  return <p className="text-amber-300 first-letter:uppercase">{fellBack(reason)}</p>;
}
