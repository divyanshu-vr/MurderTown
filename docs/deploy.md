# The replay site

The public site is a static build of the console that plays recorded games from files beside it. It has no server, no credentials and no model behind it, so visitors never use the Host's subscription: Anthropic's terms allow subscription use only for the subscriber's own, ordinary use. Live games run only on the Host's machine.

## What it holds

- `frontend/public/site/index.json`: the games the landing page lists, each with its file, a title and a blurb that does not give away who wins.
- `frontend/public/site/games/`: each game file (its whole event log, as `mm play --out` and `mm evaluate` write it) with its review beside it (`<name>.review.json`). Model calls stay out: replaying needs only the events.

To add a game, copy its `.ndjson` and `.review.json` there and list it in `index.json`. A test (`frontend/src/net/replaySite.test.ts`) checks that every listed game is whole, has its review and holds no email address or path from the Host's computer; game files keep only what happened in the town, as answers are scrubbed before they become events.

## Build and try it

```
cd frontend
pnpm build:site                                           # writes dist-site/
pnpm exec vite preview --mode site                        # serves it at http://localhost:4173
```

`pnpm e2e` builds it too, and checks that the site lists its games and plays them in the town, in full scope and in Mystery mode, and that no request ever leaves it. It plays only its own games: a link to a game file anywhere else shows its list instead.

## Deploy

Both hosts below build from the repository on every push to the branch you choose. Every address but a file the site holds must serve `index.html` (a game plays at `/replay?file=...`). The frontend pins its pnpm in `package.json` (`packageManager`) and its Node in `devEngines` (24), so tell each host to use those. These steps follow each host's documentation; they have not yet been run from this repository, so check the first build's log.

**Cloudflare Pages**: create a Pages project from the repository with root directory `frontend`, build command `pnpm build:site` and build output directory `dist-site`, and set the environment variables `NODE_VERSION` to `24` and `PNPM_VERSION` to the version `packageManager` names. Pages serves `index.html` for any address it holds no file for, since the site has no `404.html`.

**Vercel**: import the repository with root directory `frontend`. `frontend/vercel.json` sets the build command, the output directory and the fallback to `index.html`; set the Node.js version to 24 in the project's settings, and the environment variable `ENABLE_EXPERIMENTAL_COREPACK` to `1`, so the build uses the pnpm `packageManager` names.

Neither needs a secret: the build reads nothing but the repository.
