import { useEffect, useReducer } from "react";

import type { Event } from "../protocol";
import { type ConnectionStatus, followGame } from "./followGame";

interface Followed {
  events: Event[];
  connection: ConnectionStatus;
}

type Change = { kind: "event"; event: Event } | { kind: "status"; status: ConnectionStatus };

function reduce(state: Followed, change: Change): Followed {
  switch (change.kind) {
    case "event":
      return { ...state, events: [...state.events, change.event] };
    case "status":
      return { ...state, connection: change.status };
  }
}

/** Every event of one game received so far, plus the state of the connection. With the Host
 * token it follows the game in full scope; without, in public scope. */
export function useFollowedGame(gameId: string, hostToken: string | null): Followed {
  const [state, dispatch] = useReducer(reduce, { events: [], connection: "connecting" });
  useEffect(
    () =>
      followGame(
        gameId,
        {
          onEvent: (event) => dispatch({ kind: "event", event }),
          onStatus: (status) => dispatch({ kind: "status", status }),
        },
        { hostToken },
      ),
    [gameId, hostToken],
  );
  return state;
}
