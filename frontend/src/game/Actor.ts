import type Phaser from "phaser";

import type { Placement, Point } from "../core/town/layout";
import type { Grid } from "../core/town/path";
import { Walk } from "../core/town/walk";
import { GRAVESTONE, type Look, lookOf, SHEETS, toPixels } from "./looks";

/** How long a fall takes, in game time. */
export const FALL_MS = 900;

/** How high a step lifts a walker, in pixels, and how long a step takes, in game time. */
const STEP_HEIGHT = 1.5;
const STEP_MS = 260;
/**
 * Someone standing breathes: up a pixel for a moment at the end of every few seconds, each to their
 * own rhythm. Fifteen rhythms all start before the first breath, so a town standing still holds none.
 */
const BREATH_MS = 2400;
const BREATH_HELD_MS = 300;
const BREATH_OFFSET_MS = 140;

/**
 * A Resident in town: their picture where they stand, breathing while they stand, walking to
 * wherever the layout puts them, and a gravestone once they have died. Everything moves on game
 * time, which the scene hands over each frame (none while stopped), so walking and falling keep
 * playback's pace.
 */
export class Actor {
  readonly name: string;
  readonly sprite: Phaser.GameObjects.Sprite;
  private readonly look: Look;
  /** Where the layout puts them. */
  private placement: Placement;
  private at: Point;
  private walk: Walk | null = null;
  /** How long they have been in town, for the rhythm of their steps and breaths. */
  private lived: number;
  /** How far through a fall they are, from 0 to 1, while falling. */
  private falling: number | null = null;

  constructor(scene: Phaser.Scene, placement: Placement) {
    this.name = placement.name;
    this.look = lookOf(placement.seat);
    this.sprite = scene.add.sprite(0, 0, SHEETS.people.key, this.look.frame);
    this.placement = placement;
    this.at = placement.at;
    this.lived = placement.seat * BREATH_OFFSET_MS;
    this.draw();
  }

  /** Where they are now, in tiles. */
  get position(): Point {
    return this.at;
  }

  /** Whether they lie as a gravestone: dead, and done falling. */
  get resting(): boolean {
    return this.placement.dead && this.falling === null;
  }

  /** Be where the layout puts them, at once: no walk, and any fall already over. */
  place(placement: Placement): void {
    this.placement = placement;
    this.at = placement.at;
    this.walk = null;
    this.endFall();
    this.draw();
  }

  /** Walk to where the layout puts them, if it has moved. */
  head(placement: Placement, grid: Grid): void {
    const moved = placement.at.x !== this.placement.at.x || placement.at.y !== this.placement.at.y;
    this.placement = placement;
    if (moved) this.walk = new Walk(this.at, placement.at, grid);
  }

  /** Fall where they stand, then lie as a gravestone. */
  fallDown(): void {
    this.walk = null;
    this.falling = 0;
  }

  /** Move on by `gameMs` of game time. */
  update(gameMs: number): void {
    this.lived += gameMs;
    if (this.walk) {
      this.walk.advance(gameMs);
      this.at = this.walk.at;
      if (this.walk.arrived) this.walk = null;
    }
    if (this.falling !== null) {
      this.falling = Math.min(1, this.falling + gameMs / FALL_MS);
      if (this.falling >= 1) this.endFall();
    }
    this.draw();
  }

  /** End a fall under way: the gravestone stands where the layout says they died. */
  private endFall(): void {
    if (this.falling === null) return;
    this.falling = null;
    this.at = this.placement.at;
  }

  private draw(): void {
    const sprite = this.sprite;
    if (this.resting) {
      sprite.setFrame(GRAVESTONE).clearTint().setFlipX(false).setAngle(0);
    } else {
      sprite.setFrame(this.look.frame).setFlipX((this.walk?.facing ?? this.placement.facing) === "right");
      if (this.look.tint === null) sprite.clearTint();
      else sprite.setTint(this.look.tint);
      sprite.setAngle(90 * (this.falling ?? 0));
    }
    const { x, y } = toPixels(this.at);
    sprite.setPosition(x, y - this.lift()).setDepth(this.at.y);
  }

  /** How far off the ground they are, in pixels: mid-step while walking, mid-breath while standing. */
  private lift(): number {
    if (this.walk) return Math.abs(Math.sin((Math.PI * this.lived) / STEP_MS)) * STEP_HEIGHT;
    const standing = !this.placement.dead && this.falling === null;
    return standing && this.lived % BREATH_MS >= BREATH_MS - BREATH_HELD_MS ? 1 : 0;
  }
}
