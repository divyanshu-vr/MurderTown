import type Phaser from "phaser";

import type { Point } from "../core/town/layout";
import { FALL_MS } from "./Actor";
import { GHOST, SHEETS, toPixels } from "./looks";

/** How long a ghost takes to appear once its Resident has fallen, and how see-through it is at most. */
const APPEAR_MS = 1200;
const SEEN = 0.8;
/** A ghost hovers a tile over its grave, rising and sinking a pixel every couple of seconds. */
const HOVER_TILES = 1;
const HOVER_MS = 2000;

/**
 * The ghosts of those found murdered, hovering over their graves for the rest of Dawn. A ghost
 * appears once its Resident has fallen, or at once with the layout; it hovers on game time.
 */
export class Ghosts {
  private readonly ghosts = new Map<string, { sprite: Phaser.GameObjects.Sprite; grave: Point; shown: number }>();

  constructor(private readonly scene: Phaser.Scene) {}

  /** Haunt these graves and no others; `snap` shows each new ghost at once. */
  haunt(graves: ReadonlyMap<string, Point>, snap: boolean): void {
    for (const [name, ghost] of this.ghosts) {
      if (graves.has(name)) continue;
      ghost.sprite.destroy();
      this.ghosts.delete(name);
    }
    for (const [name, grave] of graves) {
      // a new ghost waits for its Resident to finish falling
      const ghost = this.ghosts.get(name) ?? { sprite: this.scene.add.sprite(0, 0, SHEETS.people.key, GHOST), grave, shown: -FALL_MS };
      ghost.grave = grave;
      if (snap) ghost.shown = APPEAR_MS;
      this.ghosts.set(name, ghost);
    }
    this.update(0);
  }

  /** Move on by `gameMs` of game time. */
  update(gameMs: number): void {
    for (const ghost of this.ghosts.values()) {
      ghost.shown += gameMs;
      const hover = Math.round(Math.sin((2 * Math.PI * ghost.shown) / HOVER_MS));
      const { x, y } = toPixels({ x: ghost.grave.x, y: ghost.grave.y - HOVER_TILES });
      ghost.sprite
        .setPosition(x, y + hover)
        .setDepth(ghost.grave.y + 0.5)
        .setAlpha(SEEN * Math.min(1, Math.max(0, ghost.shown / APPEAR_MS)));
    }
  }
}
