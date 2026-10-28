import { useEffect, useState } from "react";

import { setupChoices, startGame } from "../net/games";
import type { SetupChoices } from "../protocol";
import { Page } from "./Page";
import { SetupForm } from "./SetupForm";

/** Where the Host sets up a game, then watches it once the server has started it. */
export function SetupPage({ hostToken }: { hostToken: string | null }) {
  const [choices, setChoices] = useState<SetupChoices | null>(null);

  useEffect(() => {
    setupChoices().then(setChoices, () => undefined); // the form still offers what is already chosen
  }, []);

  return (
    <Page title="New game">
      {hostToken ? (
        <SetupForm
          choices={choices}
          onStart={async (config) => {
            const gameId = await startGame(config, hostToken);
            window.location.assign(`/games/${gameId}`);
          }}
        />
      ) : (
        <p className="text-stone-300">
          Only the Host may set up a game. <a href="/" className="text-amber-200 hover:underline">Sign in</a> first.
        </p>
      )}
    </Page>
  );
}
