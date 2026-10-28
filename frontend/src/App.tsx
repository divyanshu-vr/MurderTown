import { useEffect, useState } from "react";

import { forgetHostToken, heldHostToken, keepHostToken, takeHostTokenFromLink } from "./net/hostToken";
import { isSiteGame } from "./net/replaySite";
import { GameFilePage, GamePage } from "./ui/GamePage";
import { HomePage } from "./ui/HomePage";
import { gameAt, gameFileAt } from "./ui/paths";
import { SetupPage } from "./ui/SetupPage";
import { ReplaySitePage } from "./ui/ReplaySitePage";

/** Whether this is the replay site (`vite build --mode site`): a static build of recorded games,
 * with no server behind it. */
const REPLAY_SITE = import.meta.env.MODE === "site";

/** The Host token, kept from a link that just handed it over or from before. */
function handedOver(): string | null {
  takeHostTokenFromLink();
  return heldHostToken();
}

/**
 * Pages by path: a game followed live (`/games/<id>`) or replayed (`/games/<id>/replay`),
 * a game file replayed with no server (`/replay?file=<url>`, `&mystery=1` to start in mystery
 * mode), the setup form, or the game list. The replay site has only its own game files and its
 * list of them.
 */
export function App() {
  const [token, setToken] = useState(handedOver);
  useEffect(() => {
    // the Host's link opened in a tab already showing the console changes only the address's hash
    const onHashChange = () => setToken(handedOver());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);
  const signIn = (handed: string) => {
    keepHostToken(handed);
    setToken(handed);
  };
  const signOut = () => {
    forgetHostToken();
    setToken(null);
  };

  const path = window.location.pathname;
  const gameFile = gameFileAt(window.location);
  if (gameFile && (!REPLAY_SITE || isSiteGame(gameFile.file))) {
    return <GameFilePage file={gameFile.file} mystery={gameFile.mystery} />;
  }
  if (REPLAY_SITE) return <ReplaySitePage />;
  const game = gameAt(path);
  if (game) return <GamePage key={path} gameId={game.gameId} hostToken={token} replay={game.replay} />;
  if (path === "/setup") return <SetupPage hostToken={token} />;
  return <HomePage hostToken={token} onSignIn={signIn} onSignOut={signOut} />;
}
