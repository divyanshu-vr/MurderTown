import { useEffect, useRef, useState } from "react";

import { startTown, type TownScene, type TownState } from "./TownScene";

export interface TownCanvasProps extends TownState {
  /** Snap to every layout and play nothing out: for reduced motion, and for screenshots. */
  still: boolean;
  /** Whether blocking moments wait for the town to play them. */
  setWaitForAnimations(on: boolean): void;
  animated(seq: number): void;
}

/**
 * The Town view, drawn by Phaser, with its words in HTML over it. Phaser lives only in this
 * chunk, which the console loads lazily, so a console without the town never downloads it.
 * While the town is up (and moves), blocking moments wait for it to play them.
 */
export default function TownCanvas({
  view,
  shown,
  reached,
  speed,
  held,
  cuts,
  mystery,
  still,
  setWaitForAnimations,
  animated,
}: TownCanvasProps) {
  const canvas = useRef<HTMLDivElement>(null);
  const words = useRef<HTMLDivElement>(null);
  const [scene, setScene] = useState<TownScene | null>(null);

  useEffect(() => {
    if (!canvas.current || !words.current) return;
    let mounted = true;
    const game = startTown(canvas.current, {
      overlay: words.current,
      still,
      onAnimated: animated,
      onReady: (ready) => {
        if (mounted) setScene(ready); // a game destroyed while loading may still finish
      },
    });
    return () => {
      mounted = false;
      setScene(null);
      game.destroy(true);
    };
  }, [still, animated]);

  useEffect(() => {
    if (!scene || still) return;
    setWaitForAnimations(true);
    return () => setWaitForAnimations(false);
  }, [scene, still, setWaitForAnimations]);

  useEffect(() => {
    scene?.show({ view, shown, reached, speed, held, cuts, mystery });
  }, [scene, view, shown, reached, speed, held, cuts, mystery]);

  return (
    <div className="relative h-full w-full overflow-hidden">
      <div ref={canvas} className="absolute inset-0" />
      <div ref={words} aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden" />
    </div>
  );
}
