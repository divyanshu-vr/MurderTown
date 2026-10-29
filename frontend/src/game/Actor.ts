import type Phaser from "phaser";

import type { Placement, Point } from "../core/town/layout";
import type { ChoreKind } from "../core/town/plan";
import type { Grid } from "../core/town/path";
import { Walk } from "../core/town/walk";
import { CHORE_TOOLS, GRAVESTONE, type Look, lookOf, SHEETS, TILE, toPixels, type ToolMotion } from "./looks";

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
/** Someone doing a Chore bobs a pixel as they work, and their tool moves, to this beat. */
const WORK_MS = 380;
/** Where a tool is held: this far towards the work and this far below the middle, in tiles. */
const HELD_AHEAD = 0.55;
const HELD_LOW = 0.15;
/** How each motion holds a tool at a point of the beat (0 to 1): its turn towards the work, in degrees, and how far it has gone down, in pixels. */
const MOTIONS: Record<ToolMotion, (beat: number) => { angle: number; down: number }> = {
  dip: (beat) => ({ angle: 0, down: Math.round(beat * 3) }), // a bucket let down into the well
  tip: (beat) => ({ angle: 45 * beat, down: 0 }), // a bucket tipped over the plants
  swing: (beat) => ({ angle: 90 * beat - 45, down: 0 }), // an axe swung back and down
};

/**
 * A Resident in town: their picture where they stand, breathing while they stand (or working at
 * a Chore, their tool in hand), walking to wherever the layout puts them, and a gravestone once they have died. Everything moves on game
 * time, which the scene hands over each frame (none while stopped), so walking and falling keep
 * playback's pace.
 */
export class Actor {
  readonly name: string;
  readonly sprite: Phaser.GameObjects.Sprite;
  /** The tool in hand while they do a Chore. */
  private readonly tool: Phaser.GameObjects.Sprite;
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
    this.tool = scene.add.sprite(0, 0, SHEETS.town.key, 0).setVisible(false);
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

  /** How long until they get where they are walking, in game time; nothing if they are there. */
  get arrivingIn(): number {
    return this.walk?.timeLeft ?? 0;
  }

  /** Walk to where the layout puts them, if it has moved, at `tilesPerSecond`. */
  head(placement: Placement, grid: Grid, tilesPerSecond: number): void {
    const moved = placement.at.x !== this.placement.at.x || placement.at.y !== this.placement.at.y;
    this.placement = placement;
    if (moved) this.walk = new Walk(this.at, placement.at, grid, tilesPerSecond);
  }

  /** Fall where the layout says they died (still walking home, they are found there), then lie as a gravestone. */
  fallDown(): void {
    this.walk = null;
    this.at = this.placement.at;
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
    const chore = this.working();
    this.tool.setVisible(chore !== null);
    if (chore) this.drawTool(chore, x, y);
  }

  /** Take them out of town, tool and all. */
  destroy(): void {
    this.sprite.destroy();
    this.tool.destroy();
  }

  /** The Chore they are at, while they stand at it alive. */
  private working(): ChoreKind | null {
    return this.walk || this.placement.dead || this.falling !== null ? null : this.placement.chore;
  }

  /** Where they are in the beat of their work, from 0 to 1. */
  private workBeat(): number {
    return Math.abs(Math.sin((Math.PI * this.lived) / WORK_MS));
  }

  /** The tool in hand, between them and their work, moving to the beat of the Chore. */
  private drawTool(chore: ChoreKind, x: number, y: number): void {
    const { frame, motion } = CHORE_TOOLS[chore];
    const towards = this.placement.facing === "right" ? 1 : -1;
    const { angle, down } = MOTIONS[motion](this.workBeat());
    this.tool
      .setFrame(frame)
      .setFlipX(towards > 0) // the sheet draws tools facing left
      .setAngle(towards * angle)
      .setPosition(x + towards * TILE * HELD_AHEAD, y + TILE * HELD_LOW + down)
      .setDepth(this.at.y + 0.01); // in front of whoever holds it
  }

  /** How far off the ground they are, in pixels: mid-step while walking, at work or mid-breath while standing. */
  private lift(): number {
    if (this.walk) return Math.abs(Math.sin((Math.PI * this.lived) / STEP_MS)) * STEP_HEIGHT;
    if (this.placement.dead || this.falling !== null) return 0;
    if (this.working()) return Math.round(this.workBeat());
    return this.lived % BREATH_MS >= BREATH_MS - BREATH_HELD_MS ? 1 : 0;
  }
}
