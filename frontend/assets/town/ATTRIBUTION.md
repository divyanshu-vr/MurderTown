# The town's art

The town is drawn with two packs by Kenney ([kenney.nl](https://www.kenney.nl)), both released under
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/): free to use, with credit welcome but not
required. We credit them gladly.

| File | Pack | Where it comes from | Licence |
| --- | --- | --- | --- |
| `tiny-town.png` | Tiny Town 1.1, `Tilemap/tilemap_packed.png` | [kenney.nl/assets/tiny-town](https://kenney.nl/assets/tiny-town), also on [OpenGameArt](https://opengameart.org/content/tiny-town) | CC0 1.0 |
| `tiny-dungeon.png` | Tiny Dungeon 1.0, `Tilemap/tilemap_packed.png` | [kenney.nl/assets/tiny-dungeon](https://kenney.nl/assets/tiny-dungeon), also on [OpenGameArt](https://opengameart.org/content/tiny-dungeon) | CC0 1.0 |

Both sheets are 12 by 11 frames of 16 by 16 pixels, packed with no margin or spacing. The townsfolk,
the gravestone and (from #16) the ghost come from Tiny Dungeon; everything else from Tiny Town.

`town.json` is this project's own map, made from Tiny Town's tiles. It is a Tiled map in Tiled's JSON
format with its tileset embedded, and opens and edits in [Tiled](https://www.mapeditor.org) 1.10 or
later. What the game reads from it, and what it needs to keep, is described in
`frontend/src/core/town/plan.ts`. After editing it, run `pnpm check:assets`.
