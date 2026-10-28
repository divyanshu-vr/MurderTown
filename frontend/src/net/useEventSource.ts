import { useEffect, useReducer } from "react";

import type { Event } from "../protocol";
import type { ConnectionStatus, EventSource } from "./sources";

interface Received {
  events: Event[];
  connection: ConnectionStatus;
}

type Change = { kind: "events"; events: readonly Event[] } | { kind: "status"; status: ConnectionStatus };

function reduce(state: Received, change: Change): Received {
  switch (change.kind) {
    case "events":
      return { ...state, events: [...state.events, ...change.events] };
    case "status":
      return { ...state, connection: change.status };
  }
}

/** Every event a source has sent so far, in order, plus how the source is doing. */
export function useEventSource(source: EventSource): Received {
  const [state, dispatch] = useReducer(reduce, { events: [], connection: "connecting" });
  useEffect(
    () =>
      source({
        receive: (events) => dispatch({ kind: "events", events }),
        status: (status) => dispatch({ kind: "status", status }),
      }),
    [source],
  );
  return state;
}
