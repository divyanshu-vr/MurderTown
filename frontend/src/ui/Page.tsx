import type { ReactNode } from "react";

/** The frame of every page but a game's console: the town's name, linking home, then the page. */
export function Page({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-stone-950 text-stone-100">
      <main className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-8 sm:px-6">
        <header className="flex items-baseline gap-4">
          <a href="/" className="font-serif text-3xl text-amber-200">
            MurderTown
          </a>
          <h1 className="text-lg text-stone-300">{title}</h1>
        </header>
        {children}
      </main>
    </div>
  );
}
