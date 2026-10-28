import { useEffect, useState } from "react";

import { forgetHostToken, heldHostToken, keepHostToken, takeHostTokenFromLink } from "./net/hostToken";
import { GameFilePage, GamePage } from "./ui/GamePage";
import { HomePage } from "./ui/HomePage";
import { gameAt } from "./ui/paths";
import { SetupPage } from "./ui/SetupPage";

/** The Host token, kept from a link that just handed it over or from before. */
function handedOver(): string | null {
  takeHostTokenFromLink();
  return heldHostToken();
}

/**
 * Pages by path: a game followed live (`/games/<id>`) or replayed (`/games/<id>/replay`),
 * a game file replayed with no server (`/replay?file=<url>`), the setup form, or the game list.
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
  const game = gameAt(path);
  if (game) return <GamePage key={path} gameId={game.gameId} hostToken={token} replay={game.replay} />;
  const file = new URLSearchParams(window.location.search).get("file");
  if (path === "/replay" && file) return <GameFilePage file={file} />;
  if (path === "/setup") return <SetupPage hostToken={token} />;
  return <HomePage hostToken={token} onSignIn={signIn} onSignOut={signOut} />;
}
