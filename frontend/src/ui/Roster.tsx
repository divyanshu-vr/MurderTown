import type { ResidentView } from "../core/gameView";
import { fateLabel, roleLabel } from "./labels";

/** Every Resident, alive or dead. With `onInspect`, each name opens their Mind inspector. */
export function Roster({
  residents,
  inspected = null,
  onInspect,
}: {
  residents: readonly ResidentView[];
  inspected?: string | null;
  onInspect?: ((name: string) => void) | undefined;
}) {
  return (
    <aside className="border-l border-stone-800 px-6 py-4">
      <h2 className="mb-3 text-sm uppercase tracking-wider text-stone-400">Residents</h2>
      <ul aria-label="Residents" className="space-y-2">
        {residents.map((resident) => (
          <li
            key={resident.name}
            aria-label={resident.name}
            className={`flex items-baseline justify-between gap-3 ${resident.fate ? "text-stone-500" : ""}`}
          >
            <span>
              <Name resident={resident} inspected={inspected === resident.name} onInspect={onInspect} />
              <span className="ml-2 text-xs text-stone-500">{resident.occupation}</span>
            </span>
            <span className="text-sm">
              {resident.role && (
                <span className={resident.revealed ? "text-stone-300" : "text-stone-500 italic"}>
                  {roleLabel[resident.role]}
                  {!resident.revealed && " (secret)"}
                </span>
              )}
              <span className="ml-2">{resident.fate ? fateLabel[resident.fate] : "Alive"}</span>
            </span>
          </li>
        ))}
      </ul>
    </aside>
  );
}

function Name({
  resident,
  inspected,
  onInspect,
}: {
  resident: ResidentView;
  inspected: boolean;
  onInspect?: ((name: string) => void) | undefined;
}) {
  const style = resident.fate ? "line-through" : "font-medium";
  if (!onInspect) return <span className={style}>{resident.name}</span>;
  return (
    <button
      type="button"
      aria-pressed={inspected}
      title={`Inspect ${resident.name}'s mind`}
      onClick={() => onInspect(resident.name)}
      className={`${style} underline decoration-stone-600 underline-offset-4 hover:text-amber-200 ${inspected ? "text-amber-200" : ""}`}
    >
      {resident.name}
    </button>
  );
}
