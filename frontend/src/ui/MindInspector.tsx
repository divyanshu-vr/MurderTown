import { useState } from "react";

import type { ResidentView } from "../core/gameView";
import { type DecisionView, type DossierRow, dossierRows, type MindView } from "../core/mind";
import type { Explain } from "../net/explain";
import { describeEvent } from "./describeEvent";
import { FallbackNote } from "./FallbackNote";
import { roleLabel, whenLabel } from "./labels";
import { WhyDrawer } from "./WhyDrawer";

/**
 * The Mind inspector: who a Resident is, what they remember and suspect, and every
 * decision they made, as of the moment being viewed. With `explain`, each decision
 * offers a "why?" drawer with the model attempts behind it.
 */
export function MindInspector({
  mind,
  residents,
  explain,
  onClose,
}: {
  mind: MindView;
  residents: readonly ResidentView[];
  explain?: Explain | undefined;
  onClose: () => void;
}) {
  const { persona, memory } = mind;
  return (
    <aside aria-label={`Mind of ${mind.resident}`} className="min-h-0 overflow-y-auto border-l border-stone-800 px-6 py-4">
      <header className="mb-4 flex items-baseline justify-between gap-3">
        <h2 className="text-lg">
          <span className="font-semibold text-amber-200">{mind.resident}</span>
          <span className="ml-2 text-sm text-stone-400">
            {roleLabel[mind.role]}, {persona.occupation}
          </span>
        </h2>
        <button type="button" onClick={onClose} className="text-sm text-stone-400 hover:text-stone-200">
          Close
        </button>
      </header>

      <Section title="Persona">
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
          <dt className="text-stone-500">Temperament</dt>
          <dd>{persona.temperament}</dd>
          <dt className="text-stone-500">Speaking style</dt>
          <dd>{persona.speaking_style}</dd>
          <dt className="text-stone-500">Quirk</dt>
          <dd>{persona.quirk}</dd>
        </dl>
        {mind.teammates.length > 0 && (
          <p className="mt-2 text-sm text-rose-300">Fellow Murderers: {mind.teammates.join(", ")}</p>
        )}
      </Section>

      <Section title="Notebook">
        <p className="whitespace-pre-wrap text-sm">{memory.notebook || "(empty)"}</p>
      </Section>

      <Section title="Journal">
        {memory.journal.length === 0 ? (
          <p className="text-sm text-stone-500">No entries yet.</p>
        ) : (
          <ol aria-label="Journal" className="space-y-1 text-sm">
            {memory.journal.map((entry, index) => (
              <li key={index}>
                <span className="text-stone-500">{whenLabel(entry.day, entry.phase)}:</span> {entry.text}
              </li>
            ))}
          </ol>
        )}
      </Section>

      <Section title="Dossier">
        <Dossier rows={dossierRows(mind, residents)} />
      </Section>

      <Section title="Decisions">
        <Decisions decisions={mind.decisions} explain={explain} />
      </Section>
    </aside>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-5">
      <h3 className="mb-2 text-sm uppercase tracking-wider text-stone-400">{title}</h3>
      {children}
    </section>
  );
}

/** A row for every other Resident: the latest suspicion and note, or no opinion yet. */
function Dossier({ rows }: { rows: readonly DossierRow[] }) {
  return (
    <ul aria-label="Dossier" className="space-y-2 text-sm">
      {rows.map(({ name, dead, suspicion }) => (
        <li key={name} aria-label={name} className={dead ? "text-stone-500" : ""}>
          <div className="flex items-baseline justify-between gap-2">
            <span>
              {name}
              {dead && " (dead)"}
            </span>
            {suspicion ? (
              <meter min={0} max={100} value={suspicion.suspicion} className="w-24" aria-label={`Suspicion of ${name}`} />
            ) : (
              <span className="text-stone-500">no opinion yet</span>
            )}
          </div>
          {suspicion && (
            <p className="text-stone-400">
              {suspicion.suspicion}/100: {suspicion.note}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

function Decisions({ decisions, explain }: { decisions: readonly DecisionView[]; explain?: Explain | undefined }) {
  const [asking, setAsking] = useState<number | null>(null);
  if (decisions.length === 0) return <p className="text-sm text-stone-500">None yet.</p>;
  return (
    <ol aria-label="Decisions" className="space-y-2 text-sm">
      {decisions.map(({ event, fallbackReason }) => (
        <li key={event.seq} aria-label={`Decision at event ${event.seq}`}>
          <div className="flex items-baseline justify-between gap-2">
            <span>
              <span className="text-stone-500">{whenLabel(event.day, event.phase)}:</span> {describeEvent(event)}
            </span>
            {explain && (
              <button type="button" onClick={() => setAsking(event.seq)} className="text-amber-300 hover:underline">
                why?
              </button>
            )}
          </div>
          {fallbackReason && <FallbackNote reason={fallbackReason} />}
          {explain && asking === event.seq && (
            <WhyDrawer key={event.seq} seq={event.seq} explain={explain} onClose={() => setAsking(null)} />
          )}
        </li>
      ))}
    </ol>
  );
}
