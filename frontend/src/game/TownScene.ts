import Phaser from "phaser";

import type { GameView } from "../core/gameView";
import type { Speed } from "../core/playback";
import { blocks } from "../core/presentation";
import { gameTime } from "../core/town/clock";
import { IN_THE_SQUARE, layoutFor, middleOf, type Point } from "../core/town/layout";
import { type Area, planOf, type TownPlan } from "../core/town/plan";
import { type Stage, stageOf } from "../core/town/stage";
import type { Event } from "../protocol";
import { Actor, FALL_MS } from "./Actor";
import { Director } from "./Director";
import { SHEETS, TILE, toPixels, TOWN_MAP } from "./looks";
import { Overlay } from "./Overlay";

/** What the town shows: the view and the events shown, and where playback stands. */
export interface TownState {
  view: GameView;
  shown: readonly Event[];
  speed: Speed;
  held: boolean;
  cuts: number;
}

export interface TownOptions {
  /** Where the town's words go, over the canvas. */
  overlay: HTMLElement;
  /** Snap to every layout and play nothing out: for reduced motion, and for screenshots. */
  still: boolean;
  /** A blocking moment has played out. */
  onAnimated(seq: number): void;
  onReady(scene: TownScene): void;
}

/** How long each blocking moment plays, in game time. The Sheriff's shot slows the whole town while it plays. */
const SHOT_MS = 500;
const VOTE_MS = 900;
/** The ending, or a moment the town has no animation for, takes a beat to sink in. */
const BEAT_MS = 1500;

/** A blocking moment playing out: how much game time it has left, what to look at, and what to draw as it goes. */
interface Moment {
  seq: number;
  left: number;
  focus: Area | null;
  slows: boolean;
  draw?(left: number): void;
  end?(): void;
}

/**
 * The town: the map, a Resident on it for everyone in the view, and what the stage holds (the
 * words said, ballots so far), with the camera and the words over it. Each new view walks everyone
 * to their place in its layout; the first view, a cut, a step while held or `still` snaps them
 * there instead. Blocking events play out as moments (a fall, the Sheriff's shot, a Vote's
 * result, the ending), and each tells playback when it is done. All of it runs on game time
 * (clock.ts), so holding playback stops the town where it is.
 */
export class TownScene extends Phaser.Scene {
  private readonly plan: TownPlan = planOf(TOWN_MAP);
  private readonly actors = new Map<string, Actor>();
  private moments: Moment[] = [];
  private state: TownState | null = null;
  private stage: Stage = stageOf([]);
  /** The latest event the town has seen, so only events after it play as moments. */
  private latestSeq = 0;
  /** What `create` makes, once the art has loaded. */
  private created: { camera: Director; words: Overlay; ballots: Phaser.GameObjects.Graphics } | null = null;

  constructor(private readonly options: TownOptions) {
    super("town");
  }

  preload(): void {
    this.load.tilemapTiledJSON("town", TOWN_MAP);
    this.load.image(SHEETS.town.key, SHEETS.town.url);
    this.load.spritesheet(SHEETS.people.key, SHEETS.people.url, { frameWidth: TILE, frameHeight: TILE });
  }

  create(): void {
    const map = this.make.tilemap({ key: "town" });
    const tiles = map.addTilesetImage(SHEETS.town.key, SHEETS.town.key);
    if (!tiles) throw new Error("The town's map has no tileset named " + SHEETS.town.key);
    map.createLayer("ground", tiles);
    map.createLayer("props", tiles);
    const cast = { residentAt: (at: Point) => this.residentAt(at), whereIs: (name: string) => this.whereIs(name) };
    this.created = {
      camera: new Director(this, this.plan.grid, cast, this.options.still),
      words: new Overlay(this.options.overlay),
      ballots: this.add.graphics().setDepth(1000),
    };
    this.events.on(Phaser.Scenes.Events.RENDER, () => this.placeWords());
    // destroying the game destroys the scene without shutting it down first
    this.events.once(Phaser.Scenes.Events.DESTROY, () => {
      this.created?.camera.destroy();
      this.created?.words.destroy();
    });
    this.options.onReady(this);
  }

  /** Show a new view: walk to its layout, or snap there, and play what is new. */
  show(state: TownState): void {
    const created = this.created;
    if (!created) return;
    const latest = state.shown.at(-1)?.seq ?? 0;
    // the first view lands where it is, as does a cut or a step while held; holding alone just stops the clock
    const snap =
      this.options.still ||
      this.state === null ||
      state.cuts !== this.state.cuts ||
      (state.held && latest !== this.latestSeq);
    this.state = state;
    if (snap) this.endMoments();
    for (const event of state.shown.filter(({ seq }) => seq > this.latestSeq)) {
      if (!blocks(event)) continue;
      if (snap) this.options.onAnimated(event.seq);
      else this.play(event);
    }
    this.latestSeq = latest;

    const layout = layoutFor(state.view, this.plan);
    for (const placement of layout) {
      const actor = this.actors.get(placement.name);
      if (!actor) this.actors.set(placement.name, new Actor(this, placement));
      else if (snap) actor.place(placement);
      else actor.head(placement, this.plan.grid);
    }
    for (const [name, actor] of this.actors) {
      if (layout.some((placement) => placement.name === name)) continue;
      actor.sprite.destroy();
      this.actors.delete(name);
    }

    this.stage = stageOf(state.shown);
    created.words.setResidents(state.view.residents);
    created.words.say(this.stage.words, snap);
    created.words.count(this.stage.counts);
  }

  update(_time: number, realMs: number): void {
    const created = this.created;
    const state = this.state;
    if (!created || !state) return;
    const gameMs = gameTime(realMs, {
      speed: state.speed,
      stopped: state.held || this.options.still,
      slowMotion: this.moments.some((moment) => moment.slows),
    });
    for (const actor of this.actors.values()) actor.update(gameMs);
    this.playMoments(gameMs);
    created.words.type(gameMs);
    this.drawBallots(created.ballots);
    created.camera.update(realMs, this.focus(state.view));
  }

  /** Start the moment a blocking event just shown plays out. */
  private play({ seq, payload }: Event): void {
    const moment = (left: number, focus: Area | null = null): Moment => ({ seq, left, focus, slows: false });
    switch (payload.type) {
      case "resident_died":
        this.actors.get(payload.resident)?.fallDown();
        this.moments.push(moment(FALL_MS, this.areaAround(payload.resident)));
        return;
      case "sheriff_fired":
        this.moments.push(this.shot(seq, payload.sheriff, payload.target));
        return;
      case "vote_resolved":
        this.moments.push(moment(VOTE_MS, this.areaAround(payload.banished)));
        return;
      default:
        this.moments.push(moment(BEAT_MS));
    }
  }

  /** The Sheriff's shot: a trail from the Sheriff to the target, slowing the whole town, and a flash as it lands. */
  private shot(seq: number, sheriff: string, target: string): Moment {
    const trail = this.add.graphics().setDepth(1001);
    const from = this.whereIs(sheriff);
    const to = this.whereIs(target);
    return {
      seq,
      left: SHOT_MS,
      focus: this.areaAround(target),
      slows: true,
      draw: (left) => {
        if (!from || !to) return;
        const done = 1 - left / SHOT_MS;
        const start = toPixels(from);
        const end = toPixels({ x: from.x + (to.x - from.x) * done, y: from.y + (to.y - from.y) * done });
        trail.clear().lineStyle(1.5, 0xfef3c7).lineBetween(start.x, start.y, end.x, end.y);
      },
      end: () => {
        trail.destroy();
        if (!this.options.still) this.cameras.main.flash(180, 255, 244, 214).shake(220, 0.006);
      },
    };
  }

  private playMoments(gameMs: number): void {
    for (const moment of this.moments) {
      moment.left -= gameMs;
      moment.draw?.(Math.max(0, moment.left));
    }
    const over = this.moments.filter((moment) => moment.left <= 0);
    this.moments = this.moments.filter((moment) => moment.left > 0);
    for (const moment of over) this.endMoment(moment);
  }

  /** End every moment at once, as a snap does. */
  private endMoments(): void {
    const all = this.moments;
    this.moments = [];
    for (const moment of all) this.endMoment(moment);
  }

  private endMoment(moment: Moment): void {
    moment.end?.();
    this.options.onAnimated(moment.seq);
  }

  /** What following the action frames: a moment's place, the semicircle while the town gathers in the square, or the whole town. */
  private focus(view: GameView): Area {
    const moment = this.moments.findLast((each) => each.focus);
    if (moment?.focus) return moment.focus;
    const { square, well } = this.plan;
    if (IN_THE_SQUARE.has(view.phase)) {
      // the semicircle, with room above it for what is said and below it for the well
      const top = square.y - 2;
      return { x: square.x - 1, y: top, width: square.width + 2, height: well.y + 3 - top };
    }
    return { x: 0, y: 0, width: this.plan.grid.width, height: this.plan.grid.height };
  }

  /** Twelve by eight tiles round a Resident, or nothing to look at if there is none. */
  private areaAround(name: string | null): Area | null {
    const at = this.whereIs(name);
    return at ? { x: at.x - 6, y: at.y - 4.5, width: 12, height: 8 } : null;
  }

  /** A line from each voter to whom they voted against, and a ring round whoever is speaking. */
  private drawBallots(graphics: Phaser.GameObjects.Graphics): void {
    graphics.clear();
    for (const { voter, target } of this.stage.ballots) {
      const from = this.whereIs(voter);
      const to = this.whereIs(target);
      if (!from || !to) continue;
      const [start, end] = [toPixels(from), toPixels(to)];
      graphics.lineStyle(1, 0xfcd34d, 0.75).lineBetween(start.x, start.y, end.x, end.y);
      graphics.fillStyle(0xfcd34d, 0.9).fillCircle(end.x, end.y + 5, 1.5);
    }
    const speaker = this.whereIs(this.stage.words?.speaker ?? null);
    if (speaker) {
      const feet = toPixels(speaker);
      graphics.lineStyle(1, 0xfef3c7, 0.9).strokeEllipse(feet.x, feet.y + 7, 14, 5);
    }
  }

  /** Put the words over the canvas where everything now is, once the cameras have moved. */
  private placeWords(): void {
    const created = this.created;
    const view = this.state?.view;
    if (!created || !view) return;
    const main = this.cameras.main;
    const standing = new Map([...this.actors].map(([name, actor]) => [name, actor.position]));
    const dead = new Set([...this.actors].filter(([, actor]) => actor.resting).map(([name]) => name));
    const roofs = new Map(
      view.residents.flatMap(({ name, seat }) => {
        const door = this.plan.doors[seat];
        return door ? [[name, { x: middleOf(door).x, y: door.y - 3 }] as const] : [];
      }),
    );
    created.words.position({
      zoom: main.zoom,
      toScreen: (at) => {
        const { x, y } = toPixels(at);
        return { x: (x - main.worldView.x) * main.zoom, y: (y - main.worldView.y) * main.zoom };
      },
      standing,
      dead,
      roofs,
    });
  }

  private whereIs(name: string | null): Point | null {
    return (name && this.actors.get(name)?.position) || null;
  }

  private residentAt(at: Point): string | null {
    const near = [...this.actors].find(([, actor]) => Math.hypot(actor.position.x - at.x, actor.position.y - at.y) < 0.75);
    return near?.[0] ?? null;
  }
}

/** Draw the town in `parent`, its words in `options.overlay`. */
export function startTown(parent: HTMLElement, options: TownOptions): Phaser.Game {
  return new Phaser.Game({
    type: Phaser.WEBGL,
    parent,
    pixelArt: true,
    backgroundColor: "#0c0a09",
    banner: false,
    audio: { noAudio: true },
    input: { keyboard: false },
    scale: { mode: Phaser.Scale.RESIZE, width: parent.clientWidth, height: parent.clientHeight },
    scene: new TownScene(options),
  });
}
