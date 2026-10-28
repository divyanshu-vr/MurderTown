import { useEffect, useState } from "react";

import type { Review } from "../protocol";
import type { ReviewSource } from "./review";

/** The review, asked for once the game has ended. */
export function useReview(source: ReviewSource | undefined, ended: boolean): Review | null {
  const [review, setReview] = useState<Review | null>(null);
  useEffect(() => {
    if (!source || !ended) return;
    let current = true;
    source().then(
      (answer) => {
        if (current) setReview(answer);
      },
      () => undefined, // no review: the game still replays
    );
    return () => {
      current = false;
    };
  }, [source, ended]);
  return review;
}
