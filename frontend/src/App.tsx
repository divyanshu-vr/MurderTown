import { useEffect, useState } from "react";

import { forgetHostToken, heldHostToken, keepHostToken, takeHostTokenFromLink } from "./net/hostToken";
import { HomePage } from "./ui/HomePage";
import { LiveGamePage } from "./ui/LiveGamePage";
import { SetupPage } from "./ui/SetupPage";

const GAME_PATH = /^\/games\/([0-9a-f]+)\/?$/;

/** The Host token, kept from a link that just handed it over or from before. */
function handedOver(): string | null {
  takeHostTokenFromLink();
  return heldHostToken();
}

/** Pages by path: a game's console, the setup form, or the game list. */
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
  const gameId = GAME_PATH.exec(path)?.[1];
  if (gameId) return <LiveGamePage key={gameId} gameId={gameId} hostToken={token} />;
  if (path === "/setup") return <SetupPage hostToken={token} />;
  return <HomePage hostToken={token} onSignIn={signIn} onSignOut={signOut} />;
}
