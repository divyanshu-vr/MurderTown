import type { ResidentView } from "../core/gameView";
import { fateLabel, roleLabel } from "./labels";

export function Roster({ residents }: { residents: readonly ResidentView[] }) {
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
            <span className={resident.fate ? "line-through" : "font-medium"}>{resident.name}</span>
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
