# Setup — token, permission, fonts, assets, icons

## 0. Setup (one-time, before first use)

The skill needs read access to the Figma file. Walk the user through this once; do not
guess or skip it.

### 0.1 Figma personal access token (required)

The REST API is the source of every value (geometry, tokens, text, image refs). It is not
seat-limited like the MCP server, but it IS quota-limited per plan: **every endpoint —
including `/v1/files` (node JSON) — can 429 with a Retry-After of hours to days** (observed
live: /files 429 Retry-After 22,734s while the fill-URL endpoint still answered 200).
Therefore work **cache-first**: pull each node's JSON ONCE to `figma/nodes/`, then every
script reads the disk cache — never the API. `figma_pull.py` skips nodes already on disk
(`--force` to refresh). Scarcity order: `/v1/images` (renders) most scarce → `/v1/files`
also quota'd → `/v1/files/:key/images` (fill URLs) most tolerant → the S3 asset bytes
themselves are not metered at all.

1. figma.com → **Settings → Security → Personal access tokens** → generate
2. Scope: **`File content: Read`**
3. Store it *outside* the transcript — never ask the user to paste it into chat:

```bash
echo 'YOUR_TOKEN' > ~/.figma_token && chmod 600 ~/.figma_token
```

`scripts/figma_pull.py` reads `FIGMA_TOKEN` or `~/.figma_token`.

### 0.2 File export permission (required)

Run the preflight (§6.5.1). If it returns `403 "File not exportable"`, the file owner has
disabled export/copy/share. **No token, seat, plan, duplicate-to-drafts or manual export
will bypass it.** Only the owner (or someone with edit access) can re-enable
*"Allow viewers to copy, share and export"* in the Share dialog. Say so and stop.

### 0.3 Fonts — ask for the file, every time

Figma renders with the real font; you almost never have it. **Ask for the font file up
front, as a required input, not a nice-to-have.** It cannot be recovered any other way:

- the REST API does not serve font binaries;
- an SVG export with "Outline text" contains no font data at all;
- an SVG export *without* outlining only names the family — it does not embed it.

So: request `design/fonts/…` at the start (§0.4). Declare `@font-face` pointing there and
put the real family first in the stack, so the moment the file lands it takes over with no
code change. Until then, follow §6.5.4 (measure a substitute), disclose it, and never
claim type fidelity.

**You already know exactly which files to ask for.** Every TEXT node exposes
`style.fontPostScriptName` (§5.3) — that string *is* the file name. Never guess, never
copy a font list from a previous project: derive it from *this* file, every time.

```bash
python3 scripts/figma_fonts.py figma/nodes/*.json
```

The script skips `visible:false` subtrees **and** nodes whose cumulative ancestor
`opacity` is 0, reads per-character overrides, and splits the result into free (load from
a CDN yourself) and licensed (the user must supply).

**Report the result to the user in your first reply**, before writing any code. Fill this
in from the script's output — do not ship the placeholders:

> **Fonts this design needs**
>
> **Licensed — please drop these into `design/fonts/`:**
> `<PostScriptName>.woff2` (or `.otf`) — used for `<where>`
> …one line per licensed face…
>
> **Free — I load these myself, you don't need to send them:** `<Family> <weights>`
>
> They cannot be extracted from the Figma API or from an SVG export. Until the licensed
> files exist I substitute the closest **measured** match (§6.5.4) and the type will not
> be exact. Once you drop them in, they are picked up automatically — no code change.

Then declare `@font-face` for each licensed face pointing at `design/fonts/`, with the
real family first in the stack, so the page upgrades itself the moment the files land.

### 0.4 Project asset conventions (look here FIRST)

Everything the user hands over lives in a `design/` folder at the project root. **Check it
before asking for anything and before spending render quota.**

```text
design/
├── exports/
│   ├── page.png            # full page frame, PNG @2x  ← the visual reference
│   ├── sections/           # optional: one PNG per section, named <section>.png
│   └── icons/              # SVG exports: icon-<name>.svg, logo.svg
└── fonts/                  # licensed font files: *.woff2 / *.otf / *.ttf
```

Rules:

- On start, `ls design/` and use whatever is there. Never re-ask for a file that exists.
- `design/exports/page.png` replaces the render endpoint entirely (§6.5.2). Slice it into
  sections yourself using the `y`/`height` offsets from the node JSON; write the slices to
  `figma/renders/ref_<section>.png`.
- `design/fonts/*` means the real font is available — wire it with `@font-face` and **do
  not** substitute (§6.5.4 measuring is only for when this folder is empty).
- `design/exports/icons/*.svg` means real vector icons are available — use them and delete
  any hand-drawn placeholders.

Tell the user exactly this, once:

> Create `design/exports/` in the project and drop the page frame there as **`page.png`**
> (Export → PNG, 2x). If you have the licensed font, put the file in `design/fonts/`.
> For vector icons, select them → Export → SVG into `design/exports/icons/`.
> I'll pick everything up from those folders — you don't need to send me anything.

### 0.5 Real assets only

**What counts as an icon** (`scripts/figma_icons.py` implements all of this; the fidelity
report applies the same definition, so the two never disagree):

| Rule | Why |
|---|---|
| It contains a `VECTOR` or `BOOLEAN_OPERATION` | a subtree of bare `ELLIPSE`/`RECTANGLE` is a shape — carousel dots, a ring, a divider — that CSS draws |
| Nothing in it has an `IMAGE` fill | a shape with a photo fill is a photo, and exporting it sweeps up every path behind it |
| No later sibling with an opaque fill covers it | component placeholder artwork is routinely buried under a photo; it never renders |
| Its children are not several disjoint, icon-sized containers | that is a frame of icons — a pager's two arrows, a five-star row — and each is exported separately |
| Its `viewBox` is the node's box, and `width`/`height` are written into the file | crop to the ink and a 12px glyph fills a 40px button; omit the size and `<img>` falls back to 300×150 |

Read **every** shape element out of the page SVG — `path`, `rect`, `circle`, `ellipse`,
`line`, `polygon`, `polyline`. An icon whose circle is a `<circle>` comes out blank if you
only look at `<path>`.

Placeholders are a reporting state, never a deliverable. Specifically:

- **Icons:** never ship hand-drawn approximations if a vector source exists. Extract them
  from the SVG export (Figma sets `id` to the layer name, and coordinates are in page
  space, so wrapping the matching paths in `<svg viewBox="x y w h">` reproduces them
  exactly). Three traps:
  1. Strip the base64 `data:image` payloads first — a full-page export is mostly embedded
     photos and can be hundreds of megabytes; stripped, it is a couple of megabytes and
     only then is parseable.
  2. With `xml.etree`, call `register_namespace("", SVG_NS)` and **do not also pass an
     `xmlns` attribute** — you get a duplicate attribute and every icon fails to render.
  3. Locate icons by the node's bounding box from the JSON, not by layer name; names
     repeat (`icon`, `icon_2`, `Vector`). Then **open the icons and look at them** before
     wiring them in — a bad crop yields a plausible-looking blob.
  4. **Never estimate a path's bounding box by parsing the numbers out of its `d`.**
     Curves and relative commands make that answer wrong, and the failure is silent — a
     logo lockup crops down to just its ornament. Flatten the curves (`scripts/figma_icons.py`
     does this, and matches the browser's `getBBox()` to 0.00px), or measure with `getBBox()`.
  5. **A pure-vector subtree can still be a group of icons.** If one icon rect strictly
     contains another, the outer one is a container — exporting it stacks two icons on top
     of each other. Drop it and keep the inner rects.

**You never need the API to get the page's icons.** The page SVG export holds every vector
on that page in page coordinates; the node JSON says where each icon sits. Intersect them:

```bash
python3 scripts/figma_icons.py --svg design/exports/page.svg --nodes figma/nodes \
    --out design/exports/icons
```

"The icon library is behind a rate limit" is therefore never a reason to draw an icon by
hand. Then **open the icons and look at them** before wiring any of them in.
- **Photos:** always the real `imageRef` bytes, mapped to the right node (§6.5.3).
- **Logos:** never invent a brand. If the reference shows a wordmark, read it; if it is
  unreadable, use a neutral placeholder and say so.
- **Fonts:** use the licensed file when supplied; otherwise measure a substitute and
  record the delta. Declare `@font-face` pointing at `design/fonts/` up front and put the
  real family first in the stack — the moment the user drops the file it takes over with
  no code change. Until then the browser logs a 404 per source and falls back; say so
  rather than letting it look like a broken build.
- **Interactions:** static markup for a carousel/accordion/filter is Mode A. Wiring the
  behaviour is Mode C and needs an explicit request (§3.0).

Every remaining placeholder must appear in the difference log with the reason.

### 0.6 What to ask the user for, up front

- the Figma **frame URL** (must contain `node-id`)
- confirmation the token is stored
- the target framework (plain HTML/CSS unless told otherwise)
- the **licensed font files** — name them exactly, from `scripts/figma_fonts.py` (§0.3);
  do not ask for the free ones
- a **PNG export** of the page frame if renders turn out to be quota-blocked (§6.5.2)

---

