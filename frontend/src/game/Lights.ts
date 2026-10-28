import Phaser from "phaser";

import { middleOf, type Point } from "../core/town/layout";
import type { TownPlan } from "../core/town/plan";
import type { Phase } from "../protocol";
import { toPixels } from "./looks";

/** How long the light takes to change from one Phase's to the next's, in game time. */
const CHANGE_MS = 2500;

/** How dark each shade gets at its darkest. */
const DUSK_SHADE = 0.22;
const NIGHT_SHADE = 0.55;

/** Shades and glows draw over everyone in town, under the ballots and the Sheriff's shot. */
const SHADE_DEPTH = 900;
const GLOW_DEPTH = 950;

const WARM = 0xffb84d;

/**
 * The light in town: a warm dimming at Dusk, darkness at Night with pools of light round the
 * lanterns, and the Den's window lit while the Murderers meet there. Each light eases towards
 * what the Phase calls for on game time, or snaps there with the layout.
 */
export class Lights {
  private readonly duskShade: Phaser.GameObjects.Rectangle;
  private readonly nightShade: Phaser.GameObjects.Rectangle;
  private readonly lanternGlow: Phaser.GameObjects.Graphics;
  private readonly windowGlow: Phaser.GameObjects.Graphics;
  /** How far each light is on, from 0 to 1, and how far it is meant to be. */
  private readonly levels = { dusk: 0, night: 0, den: 0 };
  private readonly wanted = { dusk: 0, night: 0, den: 0 };

  constructor(scene: Phaser.Scene, plan: TownPlan) {
    const { x: width, y: height } = toPixels({ x: plan.grid.width, y: plan.grid.height });
    this.duskShade = scene.add.rectangle(0, 0, width, height, 0x7c2d12).setOrigin(0).setDepth(SHADE_DEPTH);
    this.nightShade = scene.add.rectangle(0, 0, width, height, 0x0b1033).setOrigin(0).setDepth(SHADE_DEPTH + 1);
    this.lanternGlow = scene.add.graphics().setDepth(GLOW_DEPTH).setBlendMode(Phaser.BlendModes.ADD);
    this.windowGlow = scene.add.graphics().setDepth(GLOW_DEPTH).setBlendMode(Phaser.BlendModes.ADD);
    for (const lantern of plan.lanterns) {
      const lamp = lanternPost(scene, middleOf(lantern));
      glow(this.lanternGlow, lamp, 30);
    }
    glow(this.windowGlow, toPixels(middleOf(plan.denWindow)), 20);
    this.show();
  }

  /** Light the town for a Phase, the Den's window too if the Murderers are there; `snap` changes it at once. */
  set(phase: Phase, denLit: boolean, snap: boolean): void {
    Object.assign(this.wanted, {
      dusk: phase === "dusk" || phase === "night" ? 1 : 0,
      night: phase === "night" ? 1 : 0,
      den: phase === "night" && denLit ? 1 : 0,
    });
    if (snap) Object.assign(this.levels, this.wanted);
    this.show();
  }

  /** Change the light on by `gameMs` of game time. */
  update(gameMs: number): void {
    const step = gameMs / CHANGE_MS;
    for (const light of ["dusk", "night", "den"] as const) {
      const [now, wanted] = [this.levels[light], this.wanted[light]];
      this.levels[light] = now < wanted ? Math.min(wanted, now + step) : Math.max(wanted, now - step);
    }
    this.show();
  }

  private show(): void {
    const { dusk, night, den } = this.levels;
    this.duskShade.setAlpha(DUSK_SHADE * dusk * (1 - night));
    this.nightShade.setAlpha(NIGHT_SHADE * night);
    this.lanternGlow.setAlpha(night);
    this.windowGlow.setAlpha(den);
  }
}

/**
 * A lantern on its post, standing in the middle of a tile: a pole a pixel wide, and on top a dark
 * frame round a yellow flame. The tiles have no lanterns of their own, so the town draws them.
 * Returns where the flame is, in pixels.
 */
function lanternPost(scene: Phaser.Scene, at: Point): { x: number; y: number } {
  const { x, y } = toPixels(at);
  const pole = { height: 13, top: y - 9 };
  const flame = { x, y: pole.top - 1 };
  scene.add
    .graphics()
    .setDepth(at.y + 0.1)
    .fillStyle(0x3f2a1d)
    .fillRect(x - 0.5, pole.top, 1, pole.height)
    .fillStyle(0x1c1917)
    .fillRect(flame.x - 2, flame.y - 2, 4, 4)
    .fillStyle(0xfcd34d)
    .fillRect(flame.x - 1, flame.y - 1, 2, 2);
  return flame;
}

/** A soft pool of warm light: rings that fade towards the edge. */
function glow(graphics: Phaser.GameObjects.Graphics, { x, y }: { x: number; y: number }, radius: number): void {
  for (const [share, alpha] of [[1, 0.08], [0.7, 0.1], [0.4, 0.16], [0.15, 0.3]] as const) {
    graphics.fillStyle(WARM, alpha).fillCircle(x, y, radius * share);
  }
}
