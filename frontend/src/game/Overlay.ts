import type { ResidentView } from "../core/gameView";
import type { Point } from "../core/town/layout";
import type { Words } from "../core/town/stage";

/** How fast words appear in their bubble, in characters a second of game time. */
const TYPING_PER_SECOND = 45;

/** Where a label sits over the canvas, in CSS pixels, given a spot in town in tiles. */
export type ToScreen = (at: Point) => { x: number; y: number };

/** Below this zoom the town is too small to name everyone over their heads; the houses keep their names. */
const NAMES_FROM_ZOOM = 2;

/**
 * The town's words, drawn as HTML over the canvas so they stay crisp at any zoom: each living
 * Resident's name over their head, each house's owner over its roof, a bubble typing out the
 * latest words said, and the running count of ballots against each Resident. The scene says
 * where everything is after each frame; the overlay moves its labels there without React.
 *
 * Each name carries where its Resident stands (`data-x`, `data-y`, in tiles) so a test can
 * check the town against the map.
 */
export class Overlay {
  private readonly names = new Map<string, HTMLElement>();
  private readonly houses = new Map<string, HTMLElement>();
  private readonly counts = new Map<string, HTMLElement>();
  private readonly bubble: HTMLElement;
  private words: Words | null = null;
  private typed = 0;

  constructor(private readonly root: HTMLElement) {
    this.bubble = this.add(
      "max-w-56 rounded-lg bg-stone-50 px-2 py-1 text-xs leading-snug text-stone-900 shadow-lg",
    );
    this.bubble.hidden = true;
  }

  /** The Residents to name, and whose names to colour: Murderers, where the view knows them. */
  setResidents(residents: readonly ResidentView[]): void {
    for (const { name, role } of residents) {
      const label = this.names.get(name) ?? this.addTo(this.names, name, "rounded bg-stone-950/75 px-1 text-[10px] leading-tight");
      label.textContent = name;
      label.dataset.resident = name;
      label.classList.toggle("text-red-300", role === "murderer");
      label.classList.toggle("text-stone-100", role !== "murderer");
      if (!this.houses.has(name)) {
        this.addTo(this.houses, name, "text-[9px] font-semibold text-amber-100 drop-shadow").textContent = name;
      }
    }
    this.removeAllBut(residents.map(({ name }) => name));
  }

  /** The words being said, typed out from the start when they are new; `whole` shows them all at once. */
  say(words: Words | null, whole: boolean): void {
    if (words?.seq !== this.words?.seq) this.typed = 0;
    this.words = words;
    if (whole) this.typed = words?.text.length ?? 0;
    this.bubble.hidden = words === null;
    this.bubble.textContent = words?.text.slice(0, Math.ceil(this.typed)) ?? "";
  }

  /** Ballots against each Resident so far. */
  count(counts: ReadonlyMap<string, number>): void {
    for (const [name, label] of this.counts) {
      if (!counts.has(name)) {
        label.remove();
        this.counts.delete(name);
      }
    }
    for (const [name, count] of counts) {
      const label = this.counts.get(name) ?? this.addTo(this.counts, name, "rounded-full bg-amber-300 px-1.5 text-[10px] font-bold text-stone-900");
      label.textContent = String(count);
      label.title = `${count} ${count === 1 ? "ballot" : "ballots"} against ${name}`;
    }
  }

  /** Type on for `gameMs` of game time. */
  type(gameMs: number): void {
    const words = this.words;
    if (!words || this.typed >= words.text.length) return;
    this.typed = Math.min(words.text.length, this.typed + (gameMs * TYPING_PER_SECOND) / 1000);
    this.bubble.textContent = words.text.slice(0, Math.ceil(this.typed));
  }

  /**
   * Put every label over what it names: names over heads (the dead have none, and nobody does
   * when the town is too small to read them), house names over roofs, the bubble over the
   * speaker, counts beside names.
   */
  position(where: {
    zoom: number;
    toScreen: ToScreen;
    standing: ReadonlyMap<string, Point>;
    dead: ReadonlySet<string>;
    roofs: ReadonlyMap<string, Point>;
  }): void {
    const { zoom, toScreen, standing, dead, roofs } = where;
    for (const [name, label] of this.names) {
      const at = standing.get(name);
      label.hidden = !at || dead.has(name) || zoom < NAMES_FROM_ZOOM;
      if (!at) continue;
      place(label, toScreen({ x: at.x, y: at.y - 0.55 }));
      const [x, y] = [at.x.toFixed(2), at.y.toFixed(2)];
      if (label.dataset.x !== x || label.dataset.y !== y) Object.assign(label.dataset, { x, y });
      label.dataset.dead = String(dead.has(name));
    }
    for (const [name, label] of this.houses) {
      const roof = roofs.get(name);
      label.hidden = !roof;
      if (roof) place(label, toScreen(roof));
    }
    for (const [name, label] of this.counts) {
      const at = standing.get(name);
      label.hidden = !at;
      if (at) place(label, toScreen({ x: at.x + 0.9, y: at.y - 0.2 }));
    }
    const speaker = this.words && standing.get(this.words.speaker);
    if (speaker) place(this.bubble, toScreen({ x: speaker.x, y: speaker.y - 1.3 }));
  }

  destroy(): void {
    this.root.replaceChildren();
  }

  private add(classes: string): HTMLElement {
    const element = document.createElement("div");
    element.className = `pointer-events-none absolute left-0 top-0 ${classes}`;
    this.root.append(element);
    return element;
  }

  private addTo(labels: Map<string, HTMLElement>, name: string, classes: string): HTMLElement {
    const label = this.add(`whitespace-nowrap ${classes}`);
    labels.set(name, label);
    return label;
  }

  private removeAllBut(names: readonly string[]): void {
    for (const labels of [this.names, this.houses]) {
      for (const [name, label] of labels) {
        if (names.includes(name)) continue;
        label.remove();
        labels.delete(name);
      }
    }
  }
}

/** Sit a label's bottom middle on a point of the canvas. */
function place(label: HTMLElement, { x, y }: { x: number; y: number }): void {
  label.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px) translate(-50%, -100%)`;
}
