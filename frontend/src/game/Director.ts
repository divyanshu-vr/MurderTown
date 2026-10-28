import type Phaser from "phaser";

import { isShortcut } from "../core/keys";
import type { Point } from "../core/town/layout";
import type { Area } from "../core/town/plan";
import { TILE, toPixels } from "./looks";

/** The closest the camera zooms in. */
const MOST_ZOOM = 4;
/** How fast the keys pan, in screen pixels a second. */
const PAN_PER_SECOND = 420;
/** How quickly the camera catches up with what it follows: most of the way in about this long. */
const CATCH_UP_MS = 300;
/** How far a press moves before it is a drag rather than a click, in screen pixels. */
const DRAG_FROM = 4;
const PAN_KEYS: Record<string, Point> = { w: { x: 0, y: -1 }, a: { x: -1, y: 0 }, s: { x: 0, y: 1 }, d: { x: 1, y: 0 } };

type Following = { kind: "action" } | { kind: "resident"; name: string } | { kind: "nothing" };

export interface Cast {
  /** Who stands at a spot, in tiles, if anyone does. */
  residentAt(at: Point): string | null;
  /** Where a Resident is now, in tiles. */
  whereIs(name: string): Point | null;
}

/**
 * Where the town's camera looks. It follows the action unless the Spectator takes it: a drag or
 * W, A, S and D pan, the wheel zooms in whole steps (or to the whole town on a small screen), a
 * click on a Resident follows them, and F follows the action again. Following the action frames
 * the area the scene asks for, as closely as a whole zoom step allows. The zoom jumps from step to
 * step, never resting between them, while the view glides; when `still`, the view jumps too. A
 * minimap in the corner shows the whole town and the part in view.
 */
export class Director {
  private following: Following = { kind: "action" };
  /** The zoom the Spectator chose with the wheel, kept until they press F. */
  private chosenZoom: number | null = null;
  private readonly panning = new Set<string>();
  private press: { x: number; y: number; scrollX: number; scrollY: number; dragging: boolean } | null = null;
  private readonly minimap: Phaser.Cameras.Scene2D.Camera;
  private readonly inView: Phaser.GameObjects.Graphics;
  private readonly world: { width: number; height: number };

  constructor(
    private readonly scene: Phaser.Scene,
    tiles: { width: number; height: number },
    private readonly cast: Cast,
    private readonly still: boolean,
  ) {
    this.world = { width: tiles.width * TILE, height: tiles.height * TILE };
    const main = scene.cameras.main;
    this.minimap = scene.cameras.add(0, 0, 1, 1).setName("minimap").setBackgroundColor(0x0c0a09);
    this.inView = scene.add.graphics().setDepth(Number.MAX_SAFE_INTEGER);
    main.ignore(this.inView);
    this.fit(scene.scale.width, scene.scale.height);
    scene.scale.on("resize", ({ width, height }: { width: number; height: number }) => this.fit(width, height));

    scene.input.on("pointerdown", (pointer: Phaser.Input.Pointer) => {
      this.press = { x: pointer.x, y: pointer.y, scrollX: main.scrollX, scrollY: main.scrollY, dragging: false };
    });
    scene.input.on("pointermove", (pointer: Phaser.Input.Pointer) => this.drag(pointer));
    scene.input.on("pointerup", (pointer: Phaser.Input.Pointer) => this.release(pointer));
    scene.input.on("wheel", (_pointer: unknown, _over: unknown, _dx: number, dy: number) => this.zoomStep(dy < 0 ? 1 : -1));
    window.addEventListener("keydown", this.onKeyDown);
    window.addEventListener("keyup", this.onKeyUp);
    window.addEventListener("blur", this.onBlur);
  }

  /** Move the camera on by a frame of `realMs`, framing `focus` (in tiles) while following the action. */
  update(realMs: number, focus: Area): void {
    const main = this.scene.cameras.main;
    this.pan(realMs);
    const target = this.target(focus);
    if (target) {
      const share = this.still ? 1 : 1 - Math.exp(-realMs / CATCH_UP_MS);
      main.setZoom(target.zoom);
      const centre = this.centre();
      main.centerOn(centre.x + (target.x - centre.x) * share, centre.y + (target.y - centre.y) * share);
    }
    this.keepTheTownInView();
    const view = main.worldView;
    this.inView.clear().lineStyle(2 / this.minimap.zoom, 0xfcd34d).strokeRect(view.x, view.y, view.width, view.height);
  }

  destroy(): void {
    window.removeEventListener("keydown", this.onKeyDown);
    window.removeEventListener("keyup", this.onKeyUp);
    window.removeEventListener("blur", this.onBlur);
  }

  private centre(): Point {
    const main = this.scene.cameras.main;
    return { x: main.scrollX + main.width / 2, y: main.scrollY + main.height / 2 };
  }

  /** Keep the camera over the town: in the middle of it, along any side the town is narrower than the view. */
  private keepTheTownInView(): void {
    const main = this.scene.cameras.main;
    const centre = this.centre();
    const within = (at: number, view: number, town: number) =>
      view >= town ? town / 2 : Math.min(Math.max(at, view / 2), town - view / 2);
    main.centerOn(
      within(centre.x, main.width / main.zoom, this.world.width),
      within(centre.y, main.height / main.zoom, this.world.height),
    );
  }

  /** Where to look and how closely, unless the Spectator has taken the camera. */
  private target(focus: Area): { x: number; y: number; zoom: number } | null {
    const main = this.scene.cameras.main;
    if (this.following.kind === "resident") {
      const at = this.cast.whereIs(this.following.name);
      return at && { ...toPixels(at), zoom: this.chosenZoom ?? main.zoom };
    }
    if (this.following.kind === "nothing") return null;
    const fits = Math.min(main.width / (focus.width * TILE), main.height / (focus.height * TILE));
    return {
      ...toPixels({ x: focus.x + focus.width / 2, y: focus.y + focus.height / 2 }),
      zoom: this.chosenZoom ?? (fits >= 1 ? Math.min(MOST_ZOOM, Math.floor(fits)) : fits),
    };
  }

  /** The zoom steps on offer: whole steps up to the closest, and the whole town if that needs less than one. */
  private zoomSteps(): number[] {
    const main = this.scene.cameras.main;
    const whole = Math.min(main.width / this.world.width, main.height / this.world.height);
    return [...(whole < 1 ? [whole] : []), ...Array.from({ length: MOST_ZOOM }, (_, step) => step + 1)];
  }

  private zoomStep(notches: 1 | -1): void {
    const zoom = this.scene.cameras.main.zoom;
    const steps = this.zoomSteps();
    const next = notches > 0 ? steps.find((step) => step > zoom + 0.01) : steps.findLast((step) => step < zoom - 0.01);
    this.chosenZoom = next ?? this.chosenZoom ?? zoom;
    if (this.following.kind === "nothing") this.scene.cameras.main.setZoom(this.chosenZoom);
  }

  private drag(pointer: Phaser.Input.Pointer): void {
    const press = this.press;
    if (!press || !pointer.isDown) return;
    const [dx, dy] = [pointer.x - press.x, pointer.y - press.y];
    if (!press.dragging && Math.hypot(dx, dy) < DRAG_FROM) return;
    press.dragging = true;
    this.following = { kind: "nothing" };
    const main = this.scene.cameras.main;
    main.setScroll(press.scrollX - dx / main.zoom, press.scrollY - dy / main.zoom);
  }

  /** A press that did not drag is a click: on a Resident, follow them. */
  private release(pointer: Phaser.Input.Pointer): void {
    const press = this.press;
    this.press = null;
    if (!press || press.dragging) return;
    const world = this.scene.cameras.main.getWorldPoint(pointer.x, pointer.y);
    const name = this.cast.residentAt({ x: world.x / TILE, y: world.y / TILE });
    if (name) this.following = { kind: "resident", name };
  }

  private pan(realMs: number): void {
    if (this.panning.size === 0) return;
    const main = this.scene.cameras.main;
    const step = (PAN_PER_SECOND * realMs) / 1000 / main.zoom;
    for (const key of this.panning) {
      const way = PAN_KEYS[key];
      if (way) main.setScroll(main.scrollX + way.x * step, main.scrollY + way.y * step);
    }
  }

  private readonly onKeyDown = (event: KeyboardEvent) => {
    if (!isShortcut(event)) return;
    const key = event.key.toLowerCase();
    if (key in PAN_KEYS) {
      this.panning.add(key);
      this.following = { kind: "nothing" };
    } else if (key === "f") {
      this.following = { kind: "action" };
      this.chosenZoom = null;
    } else {
      return;
    }
    event.preventDefault();
  };

  private readonly onKeyUp = (event: KeyboardEvent) => {
    this.panning.delete(event.key.toLowerCase());
  };

  private readonly onBlur = () => this.panning.clear();

  /** Fit the minimap into the bottom right corner of a canvas this size. */
  private fit(width: number, height: number): void {
    this.scene.cameras.main.setSize(width, height);
    const across = Math.round(Math.min(176, Math.max(80, width * 0.22)));
    const zoom = across / this.world.width;
    const down = Math.round(this.world.height * zoom);
    this.minimap.setViewport(width - across - 8, height - down - 8, across, down).setZoom(zoom);
    this.minimap.centerOn(this.world.width / 2, this.world.height / 2);
  }
}
