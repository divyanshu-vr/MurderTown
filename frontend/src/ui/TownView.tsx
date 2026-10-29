import { Component, lazy, type ReactNode, Suspense, useMemo, useState } from "react";

import type { GameView } from "../core/gameView";
import type { Event } from "../protocol";
import { deterministic, prefersReducedMotion } from "./motion";
import type { PlaybackView } from "./usePlayback";

/** Phaser comes with the town, in a chunk of its own, loaded only when the town is drawn. */
const TownCanvas = lazy(() => import("../game/TownCanvas"));

/** Whether this browser can draw the Town view: it needs WebGL. Without it, the console goes on alone. */
function canDrawTheTown(): boolean {
  try {
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
    context?.getExtension("WEBGL_lose_context")?.loseContext(); // only asked; give the context back
    return context !== null;
  } catch {
    return false;
  }
}

/** Whether to draw the Town view on this page, decided once. */
export function useCanDrawTownView(): boolean {
  const [drawable] = useState(canDrawTheTown);
  return drawable;
}

/** How to move the camera, shown over the town as the playback controls show their keys. */
const CAMERA_CONTROLS =
  "Drag or W, A, S, D to pan; the wheel, E and Q, or a pinch to zoom; click a Resident to follow them; F to follow the action again";

/**
 * The Town view as of the view, played back with the console. It keeps the map's shape on a
 * narrow screen, with the panels below it, and fills the space beside them on a wide one. If the
 * town fails to load or start, it says so and the console goes on.
 *
 * It stands still (everyone snaps into place, nothing plays out) for a Spectator who prefers
 * reduced motion, and with `?deterministic=1`, so a screenshot of it is always the same.
 */
export function TownView({
  view,
  shown,
  reached,
  playback,
  mystery,
}: {
  view: GameView;
  shown: readonly Event[];
  /** The latest event playback has reached, shown or not. */
  reached: number;
  playback: PlaybackView;
  mystery: boolean;
}) {
  const still = useMemo(() => deterministic() || prefersReducedMotion(), []);
  return (
    // the map's shape, 40 by 28 tiles (town.spec.ts checks it against the map, which the console does not load)
    <section
      aria-label="Town view"
      title={CAMERA_CONTROLS}
      className="relative aspect-[40/28] w-full shrink-0 bg-stone-950 md:aspect-auto md:min-h-0 md:flex-1"
    >
      <WhenTheTownFails>
        <Suspense fallback={<p className="p-6 text-sm text-stone-500">Drawing the town…</p>}>
          <TownCanvas
            view={view}
            shown={shown}
            reached={reached}
            pace={playback.pace}
            held={playback.held}
            cuts={playback.cuts}
            mystery={mystery}
            still={still}
            setWaitForAnimations={playback.setWaitForAnimations}
            animated={playback.animated}
          />
        </Suspense>
      </WhenTheTownFails>
    </section>
  );
}

/** A town that fails to load or start leaves a note in its place, rather than taking the console down. */
class WhenTheTownFails extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return <p className="p-6 text-sm text-stone-500">The town could not be drawn here. The console goes on.</p>;
  }
}
