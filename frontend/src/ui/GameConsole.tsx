import { useMemo } from "react";

import { foldEvents } from "../core/gameView";
import type { ConnectionStatus } from "../net/followGame";
import type { Event } from "../protocol";
import { EventFeed } from "./EventFeed";
import { PhaseBar } from "./PhaseBar";
import { Roster } from "./Roster";

/** The text console: phase bar, town feed and roster, for whatever events have arrived. */
export function GameConsole({ events, connection }: { events: readonly Event[]; connection: ConnectionStatus }) {
  const view = useMemo(() => foldEvents(events), [events]);
  return (
    <div className="flex h-dvh flex-col bg-stone-950 text-stone-100">
      <PhaseBar view={view} connection={connection} />
      <main className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[1fr_20rem]">
        <EventFeed events={events} />
        <Roster residents={view.residents} />
      </main>
    </div>
  );
}
