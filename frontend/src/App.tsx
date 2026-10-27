import { useFollowedGame } from "./net/useFollowedGame";
import { GameConsole } from "./ui/GameConsole";

const GAME_PATH = /^\/games\/([0-9a-f]+)\/?$/;

export function App() {
  const gameId = GAME_PATH.exec(window.location.pathname)?.[1];
  return gameId ? <LiveGame key={gameId} gameId={gameId} /> : <Welcome />;
}

function LiveGame({ gameId }: { gameId: string }) {
  const { events, connection } = useFollowedGame(gameId);
  return <GameConsole events={events} connection={connection} />;
}

function Welcome() {
  return (
    <main className="mx-auto flex h-dvh max-w-xl flex-col justify-center gap-4 bg-stone-950 px-6 text-stone-200">
      <h1 className="font-serif text-4xl text-amber-200">MurderTown</h1>
      <p>A town where every Resident is played by an Agent. Start a game, then watch it here:</p>
      <pre className="rounded bg-stone-900 p-4 text-sm text-stone-300">
        {"cd backend\nuv run mm serve\nuv run mm new-game"}
      </pre>
    </main>
  );
}
