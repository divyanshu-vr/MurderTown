import { everyRoleKnown, type Outcome, type ResidentView } from "../core/gameView";
import type { Event, Review } from "../protocol";
import { describeEvent } from "./describeEvent";
import { aRole, lieLabel, whenLabel } from "./labels";
import { OutcomeText } from "./Outcome";
import { ResidentList } from "./Roster";

type Lie = Review["lies"][number];
type TurningPoint = Review["turning_points"][number];

/** What a Lie did, beside what its speaker privately held. */
function didAndHeld(lie: Lie): { did: string; held: string } {
  if (lie.kind === "false_role") {
    return { did: `${lieLabel[lie.kind]} ${aRole(lie.claimed_role)}`, held: `is ${aRole(lie.true_role)}` };
  }
  const { resident, suspicion, note } = lie.belief;
  return { did: `${lieLabel[lie.kind]} ${resident}`, held: `${resident}: Suspicion ${suspicion}, ${note}` };
}

/** A turning point in words: a death or the Sheriff's shot as the feed tells it, or a swing. */
function told(point: TurningPoint, event: Event | undefined): string {
  if (point.kind === "swing") {
    return `${point.resident}'s Suspicion of ${point.suspect} swung from ${point.before} to ${point.after}.`;
  }
  return event ? describeEvent(event) : "";
}

/**
 * The game-over screen: how the game ended and, once a side has won, who everyone was (games
 * recorded before roles were revealed at the end show that only in full scope). With the
 * server's full-scope `review`, which tells private beliefs, also its turning points in order,
 * every Lie beside its speaker's private belief, and whose accusations the others' ballots
 * followed; this only shows it.
 */
export function PostGameReview({
  review,
  residents,
  events,
  outcome,
}: {
  review: Review | null;
  residents: readonly ResidentView[];
  events: readonly Event[];
  outcome: Outcome;
}) {
  return (
    <section aria-label="Post-game review" className="min-h-0 space-y-6 overflow-y-auto px-6 py-4">
      <p className="text-lg text-amber-200">
        <OutcomeText outcome={outcome} />
      </p>

      {outcome.ended === "won" && everyRoleKnown(residents) && (
        <section>
          <h3 className="mb-2 text-sm uppercase tracking-wider text-stone-400">Who everyone was</h3>
          <ResidentList residents={residents} />
        </section>
      )}

      {review && <FullReview review={review} events={events} />}
    </section>
  );
}

function FullReview({ review, events }: { review: Review; events: readonly Event[] }) {
  const bySeq = new Map(events.map((event) => [event.seq, event]));
  return (
    <>
      <section>
        <h3 className="mb-2 text-sm uppercase tracking-wider text-stone-400">Turning points</h3>
        <ol className="space-y-1">
          {review.turning_points.map((point) => {
            const event = bySeq.get(point.seq);
            const when = event ? whenLabel(event.day, event.phase) : "";
            const key = point.kind === "swing" ? `${point.seq}-${point.suspect}` : `${point.seq}`;
            return (
              <li key={key} aria-label={`Turning point, ${when}`}>
                <span className="text-stone-500">{when}: </span>
                {told(point, event)}
              </li>
            );
          })}
        </ol>
      </section>

      <section>
        <h3 className="mb-2 text-sm uppercase tracking-wider text-stone-400">Lies told</h3>
        {review.lies.length === 0 ? (
          <p className="text-stone-400">Nobody said what they did not believe.</p>
        ) : (
          <table aria-label="Lies told" className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wider text-stone-500">
              <tr>
                <th className="py-1 font-normal">Who</th>
                <th className="font-normal">Said</th>
                <th className="font-normal">Privately</th>
              </tr>
            </thead>
            <tbody>
              {review.lies.map((lie) => {
                const { did, held } = didAndHeld(lie);
                return (
                  <tr key={`${lie.seq}-${did}`} className="border-t border-stone-800 align-top">
                    <td className="py-1 pr-3">{lie.speaker}</td>
                    <td className="pr-3">
                      “{lie.said}” <span className="text-stone-500">({did})</span>
                    </td>
                    <td className="text-rose-200">{held}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h3 className="mb-2 text-sm uppercase tracking-wider text-stone-400">Influence</h3>
        <ol aria-label="Influence" className="space-y-1">
          {review.influence.map(({ resident, followed, ballots }) => (
            <li key={resident}>
              {resident}: {followed} of {ballots} ballots by others went against whom they accused
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}
