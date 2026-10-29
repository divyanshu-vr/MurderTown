import type { ResidentView } from "../core/gameView";
import type { Bubble } from "../core/town/bubbles";
import type { Point } from "../core/town/layout";
import { typedAfter } from "../core/presentation";

/** What a Conversation sounds like to those who cannot hear it. */
const MUFFLED = "· · ·";

/** Below this zoom the town is too small to name everyone over their heads; the houses keep their names. */
const NAMES_FROM_ZOOM = 2;

/** The space between bubbles stacked over one another, in CSS pixels. */
const BUBBLE_GAP = 2;

/** Where a label sits over the canvas, in CSS pixels, given a spot in town in tiles. */
export type ToScreen = (at: Point) => { x: number; y: number };

/** A bubble on screen: its words typed so far, the rest kept invisible so the bubble keeps its size. */
interface ShownBubble {
  over: readonly string[];
  text: string;
  seq: number | null;
  typed: number;
  /** How many characters are showing, or none yet. */
  showing: number | null;
  element: HTMLElement;
  said: HTMLElement;
  unsaid: HTMLElement;
  /** Measured once its words are in, to stack it without measuring every frame. */
  size: { width: number; height: number } | null;
}

/**
 * The town's words, drawn as HTML over the canvas so they stay crisp at any zoom: each living
 * Resident's name over their head, each house's owner over its roof, bubbles typing out what is
 * said (or muffled, when it cannot be heard), a Raised hand for each Bid on the Open floor, the
 * running count of Ballots against each Resident, whom the head of a Vote line voted against,
 * what a Night Visit does at the door, and the Narrator's banner. The scene says where everything is after each frame; the overlay
 * moves its labels there without React.
 *
 * Each name carries where its Resident stands (`data-x`, `data-y`, in tiles) so a test can
 * check the town against the map.
 */
export class Overlay {
  private readonly names = new Map<string, HTMLElement>();
  private readonly houses = new Map<string, HTMLElement>();
  private readonly counts = new Map<string, HTMLElement>();
  private readonly hands = new Map<string, HTMLElement>();
  private readonly deeds = new Map<string, HTMLElement>();
  private readonly tags = new Map<string, HTMLElement>();
  private readonly bubbles = new Map<string, ShownBubble>();
  private readonly banner: HTMLElement;

  constructor(private readonly root: HTMLElement) {
    this.banner = document.createElement("p");
    this.banner.className =
      "pointer-events-none absolute left-1/2 top-3 w-max max-w-[80%] -translate-x-1/2 rounded bg-amber-50/95 px-3 py-1.5 text-center text-sm italic text-stone-900 shadow-lg";
    this.banner.hidden = true;
    root.append(this.banner);
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
    const named = new Set(residents.map(({ name }) => name));
    dropAllBut(this.names, named);
    dropAllBut(this.houses, named);
  }

  /** The bubbles to show; new words type out from the start, unless `whole` shows them all at once. */
  say(bubbles: readonly Bubble[], whole: boolean): void {
    dropAllBut(this.bubbles, new Set(bubbles.map(({ key }) => key)));
    for (const { key, over, text, seq } of bubbles) {
      const bubble = this.bubbles.get(key) ?? this.addBubble(key, text === null);
      bubble.over = over;
      if (bubble.seq !== seq || bubble.text !== (text ?? MUFFLED)) {
        Object.assign(bubble, { text: text ?? MUFFLED, seq, typed: 0, showing: null, size: null });
      }
      if (whole) bubble.typed = bubble.text.length;
    }
    this.type(0);
  }

  /** Ballots against each Resident so far. */
  count(counts: ReadonlyMap<string, number>): void {
    dropAllBut(this.counts, new Set(counts.keys()));
    for (const [name, count] of counts) {
      const label = this.counts.get(name) ?? this.addTo(this.counts, name, "rounded-full bg-amber-300 px-1.5 text-[10px] font-bold text-stone-900");
      label.textContent = String(count);
      label.title = `${count} ${count === 1 ? "ballot" : "ballots"} against ${name}`;
    }
  }

  /** A Raised hand beside each Resident who Bid this Turn, with how urgently. */
  raise(hands: ReadonlyMap<string, number>): void {
    dropAllBut(this.hands, new Set(hands.keys()));
    for (const [name, urgency] of hands) {
      const hand = this.hands.get(name) ?? this.addTo(this.hands, name, "rounded bg-sky-200 px-1 text-[10px] font-bold text-stone-900");
      hand.textContent = `✋${urgency}`;
      hand.title = `${name} Bids ${urgency} to speak next`;
    }
  }

  /** What `visitors` do at the door on a Night Visit, marked beside each of them; none for no one. */
  markDeeds(visitors: readonly string[], mark: string, meaning: string): void {
    dropAllBut(this.deeds, new Set(visitors));
    for (const name of visitors) {
      const deed = this.deeds.get(name) ?? this.addTo(this.deeds, name, "text-base drop-shadow motion-safe:animate-bounce");
      deed.textContent = mark;
      deed.title = `${name} ${meaning}`;
    }
  }

  /** Whom each head of a Vote line voted against, tagged beside them: voter to target. */
  tag(ballots: ReadonlyMap<string, string>): void {
    dropAllBut(this.tags, new Set(ballots.keys()));
    for (const [voter, target] of ballots) {
      const tag = this.tags.get(voter) ?? this.addTo(this.tags, voter, "rounded bg-amber-300/90 px-1 text-[10px] font-bold text-stone-900");
      tag.textContent = `→ ${target}`;
      tag.title = `${voter} voted against ${target}`;
    }
  }

  /** The Narrator's words across the top, or nothing. */
  announce(text: string | null): void {
    this.banner.hidden = text === null;
    this.banner.textContent = text ?? "";
  }

  /** Type on for `gameMs` of game time. */
  type(gameMs: number): void {
    for (const bubble of this.bubbles.values()) {
      bubble.typed = typedAfter(bubble.typed, gameMs, bubble.text.length);
      const showing = Math.ceil(bubble.typed);
      if (showing === bubble.showing) continue;
      bubble.showing = showing;
      bubble.said.textContent = bubble.text.slice(0, showing);
      bubble.unsaid.textContent = bubble.text.slice(showing);
    }
  }

  /**
   * Put every label over what it names: names over heads (the dead have none, and nobody does
   * when the town is too small to read them), house names over roofs, bubbles over whoever they
   * are about, stacked rather than covering one another, Ballot counts and Visits' deeds after
   * names, raised hands and the heads' tags before them.
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
    placeBeside(this.counts, standing, toScreen, 0.9);
    placeBeside(this.hands, standing, toScreen, -0.9);
    placeBeside(this.deeds, standing, toScreen, 0.9);
    placeBeside(this.tags, standing, toScreen, -0.9);
    const taken: Box[] = [];
    for (const bubble of this.bubbles.values()) {
      const heads = bubble.over.flatMap((name) => standing.get(name) ?? []);
      bubble.element.hidden = heads.length === 0;
      if (!heads.length) continue;
      const sum = heads.reduce((total, at) => ({ x: total.x + at.x, y: total.y + at.y }), { x: 0, y: 0 });
      const spot = toScreen({ x: sum.x / heads.length, y: sum.y / heads.length - 1.3 });
      bubble.size ??= { width: bubble.element.offsetWidth, height: bubble.element.offsetHeight };
      const box = stacked(spot, bubble.size, taken);
      taken.push(box);
      place(bubble.element, { x: spot.x, y: box.bottom });
    }
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

  private addBubble(key: string, muffled: boolean): ShownBubble {
    const tone = muffled ? "italic text-stone-500" : "text-stone-900";
    const element = this.add(`max-w-56 rounded-lg bg-stone-50 px-2 py-1 text-xs leading-snug shadow-lg ${tone}`);
    const [said, unsaid] = [document.createElement("span"), document.createElement("span")];
    unsaid.className = "invisible";
    element.append(said, unsaid);
    const bubble = { over: [], text: "", seq: null, typed: 0, showing: null, element, said, unsaid, size: null };
    this.bubbles.set(key, bubble);
    return bubble;
  }
}

/** Where a bubble sits over the canvas, in CSS pixels. */
interface Box {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

/** A bubble's box over `spot`, moved above any box it would cover, but never off the top. */
function stacked(spot: { x: number; y: number }, { width, height }: { width: number; height: number }, taken: readonly Box[]): Box {
  let box = { left: spot.x - width / 2, right: spot.x + width / 2, top: spot.y - height, bottom: spot.y };
  let covered = taken.find((other) => overlap(box, other));
  while (covered && covered.top - BUBBLE_GAP - height >= 0) {
    box = { ...box, top: covered.top - BUBBLE_GAP - height, bottom: covered.top - BUBBLE_GAP };
    covered = taken.find((other) => overlap(box, other));
  }
  return box.top >= 0 ? box : { ...box, top: 0, bottom: height };
}

function overlap(a: Box, b: Box): boolean {
  return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
}

/** Remove every label but those named. */
function dropAllBut(labels: Map<string, HTMLElement | { element: HTMLElement }>, keep: ReadonlySet<string>): void {
  for (const [name, label] of labels) {
    if (keep.has(name)) continue;
    ("element" in label ? label.element : label).remove();
    labels.delete(name);
  }
}

/** Sit a label's bottom middle on a point of the canvas. */
/** Each label beside whom it names, `dx` tiles to the right (or left); hidden for anyone not in town. */
function placeBeside(
  labels: ReadonlyMap<string, HTMLElement>,
  standing: ReadonlyMap<string, Point>,
  toScreen: ToScreen,
  dx: number,
): void {
  for (const [name, label] of labels) {
    const at = standing.get(name);
    label.hidden = !at;
    if (at) place(label, toScreen({ x: at.x + dx, y: at.y - 0.2 }));
  }
}

function place(label: HTMLElement, { x, y }: { x: number; y: number }): void {
  label.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px) translate(-50%, -100%)`;
}
