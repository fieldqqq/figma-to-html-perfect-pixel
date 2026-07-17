# Build guide — extraction protocol, step gates, responsive rules

## 6.5 Figma Extraction & Reference Protocol (MANDATORY when a Figma link is provided)

This protocol exists because reconstructing a section from geometry alone **will**
produce a section that is the right size and completely the wrong design. Every rule
below was learned from a real failure. Follow them in order.

### 6.5.0 The Prime Rule

> **Never write code for a section you have not looked at.**

A reference image of a section is a *precondition* for implementing it, not a
nice-to-have. If you cannot obtain one, the section is **BLOCKED** — stop, report it,
and ask the user for a screenshot. Do not "build it from the JSON and hope".

Corollary: **numeric agreement is not visual agreement.** A build can match every
section's frame height to the pixel and still be the wrong design.

### 6.5.0.5 Discovery — find what you are about to ignore (MANDATORY, first)

Before the node dump, before the renders, before a line of CSS:

```bash
python3 scripts/figma_discover.py <fileKey> [--nodes figma/nodes] --json figma/discovery.json
```

**Show its output to the user.** It answers four questions that silently decide whether the
job is honest work or fabrication:

| Question | If you skip it |
|---|---|
| How many design widths does the file contain? | You *invent* a responsive layout the designer already drew |
| Is there an icon page / icon components? | You *hand-draw* icons that ship in the same file |
| Do `interactions[]` point at hover variants? | You *invent* hover states that are specified |
| How many page-sized frames exist? | You build one screen when the file holds a site |

Rules:

- **A second design width is a second design.** Run the entire per-section loop against it:
  its own references, its own spec, its own audit. Never derive it from the desktop with
  media queries you made up. If the file has a mobile frame and you write a guessed mobile
  layout, that is a fabrication, not a fallback.
- The width list is a **heuristic**: cards and scratch frames share widths with screens.
  Present the candidates and ask the user which are real breakpoints. Do not decide alone.
- **An icon that exists in the file may never be redrawn.** Export it (§0.5).
- Hover destinations live outside the section subtree; fetch those node ids before you
  write a single `:hover` rule (§9.0).
- If the file holds several page-sized frames, confirm the scope with the user before
  building one and calling it done.
- **Which VERSION is a question only the user can answer.** A design file routinely holds
  a dozen superseded revisions of one screen; the file carries NO reliable "this is live"
  flag. `figma_discover.py` prints the same-width frames with their node-id, canvas order
  and any name hint (`APPR`/`Final`/`Ready`/date) — surface that list verbatim and let the
  user pick. The newest date or the largest frame is a hint, never a decision. Building the
  wrong revision is a silent, total failure the audits cannot catch (they compare against
  whatever frame you chose).

### 6.5.1 Access preflight (1 call, before any planning)

Probe access before promising anything:

- Fetch one cheap endpoint (e.g. `GET /v1/files/:key?depth=1`).
- Interpret failures precisely:
  - `403 "File not exportable"` → the file owner disabled export/copy/share. **No API,
    no manual export, no duplicate-to-drafts will work.** Only the owner (or someone
    with edit access) can lift it. Say so and stop.
  - `429` → read the **`Retry-After` header** and report it in human units. If it is
    hours or days, do not plan around "it'll reset soon".
  - MCP seat limits are **separate** from REST API quotas, and file-edit permission is
    separate from both. Do not assume fixing one fixes another.

### 6.5.2 Reference capture — spend the scarce budget FIRST

Rendering is the rate-limited resource. Asset bytes are not. Spend accordingly.

**Do, in this order:**

1. Node JSON once — `GET /v1/files/:key/nodes?ids=…` (or MCP `get_metadata`) →
   section inventory (ids, order, sizes) **and** every value you will need later.
   Use `scripts/figma_pull.py`.
2. `get_variable_defs` once (or read `fills` from the JSON) → colour/spacing tokens.
3. **One render per section** (`/v1/images?ids=…` or `get_screenshot`). This is the
   budget that matters. Render *every* section before you build *any* of them.
4. **Open and look at every render.** A render you did not view is worth nothing.
5. Only now download assets — and only the `imageRef`s actually used by the sections
   you are building.

**Never:**

- Bulk-download every image fill in the file "to be safe". It burns the shared quota
  that the renders need.
- Proceed past a failed render. If N sections failed to render, N sections are BLOCKED.

**Fail loudly:** run extraction in the foreground, or flush/stream output. A background
job whose stdout is buffered will hide "N of M renders failed" until it is too late.

#### Which endpoint is rate-limited (know this before you panic)

Only the **render** endpoint is scarce. Do not assume a `429` blocks everything:

| Source | Gives you | Rate-limited? |
|---|---|---|
| REST `GET /v1/images/:key?ids=…` | **rendered section PNGs** | **Yes — exhausts first, by far** |
| REST `GET /v1/files/:key/nodes?ids=…` | node JSON: exact px, auto-layout, tokens, `characters`, `textCase`, `imageRef` | Yes, but a much larger budget |
| REST `GET /v1/files/:key/images` | the real photos (image fills) | Yes, but a much larger budget |
| MCP `get_screenshot` / `get_design_context` | same renders, different quota | Yes (per seat) |

**Every REST endpoint shares a budget.** The render endpoint runs out first, which makes it
easy to believe the others are free — they are not; `/files` and `/nodes` will 429 after
enough calls. **Cache every response to disk on first fetch and read from that cache
afterwards.** A run that dies because a metadata call was refused is a run that wasted its
render budget for nothing.

So when renders are blocked, you have **not** lost values or assets — only the visual
ground truth. Get that from the user instead (below).

#### Fallback: ask the user to export (when renders are quota-blocked)

This is a first-class path, not a last resort. It has no quota.

1. **PNG = the visual reference.** Ask for the top-level page frame exported as
   **PNG @2x** (or @1x if the frame is very tall). Slice it locally into sections using
   the `y`/`height` offsets you already have from the node JSON.
2. **SVG = icons and logo only.** Export those as SVG to stop hand-drawing them.
3. **JSON = every value.** Keep using the API for geometry, tokens, text and image refs —
   never ask the user to hand you numbers you can fetch.

> **If SVG is used as a visual reference, "Outline text" MUST be enabled on export.**
> Otherwise the SVG carries `font-family="<premium font>"`, your machine substitutes a
> different face, and the "reference" silently shows wrong glyphs, wrong line breaks and
> wrong widths — corrupting exactly what you are trying to verify. PNG has no such
> failure mode; prefer it.

Ask for exports with this template:

> Renders are quota-blocked (`Retry-After: …`). To continue I need the visual reference:
> select the page frame → Export → **PNG, 2x**. Optionally select the logo/icons →
> Export → **SVG**. I already have all values and photos from the API; I only need the
> rendered image.

Cache every response to disk (`figma/nodes/*.json`, `figma/renders/*.png`, `assets/`) so
a quota reset never forces a refetch.

### 6.5.3 Node-JSON reading contract

The JSON is trustworthy only if you read these fields. Each bullet is a bug that
shipped:

- **Text content is `characters`, never `name`.** The two routinely disagree: a node whose
  layer `name` was copied from an old label can carry entirely different `characters`.
  Shipping the `name` puts wrong words on the page.
- **Honour `style.textCase`.** `UPPER` is real. In one file *every* heading, eyebrow and
  button was `UPPER`; rendering them title-case broke the whole page's identity.
- **Skip `visible: false`** nodes, and skip their subtrees. Hidden variants and stale
  copy live there.
- **`visible: false` is not the only way a node is hidden.** Multiply `opacity` down the
  ancestor chain and drop anything whose effective opacity is `0`; also respect
  `clipsContent` on ancestors. A node can be `visible: true` and still render nothing.
  This matters beyond layout: an opacity-0 node made one build ask the user for a
  licensed font that the design never actually shows.
- **`style.textAlignHorizontal` describes alignment *inside the text box*,** not on the
  page. A `LEFT`-aligned box inside a centred auto-layout renders centred. Use
  `absoluteBoundingBox.x` relative to the container to decide real alignment.
- Read `fills`, `strokes` + `strokeWeight`, `cornerRadius`, `opacity`, and gradient
  paints. Rings, badges, scrims and pills live in these, not in the layout tree.
- **`imageTransform` on an IMAGE fill can rotate/flip/crop the photo.** A negative scale
  means the asset must be transformed before use; `background-position` alone will not
  reproduce it.
- **Selecting the right `imageRef`:** filter candidates by the *node's own* bounding box
  (e.g. only 108×108 tiles), explicitly exclude the section background (large bbox), and
  for stacked carousel slides take the **last** (topmost) fill in paint order. An
  off-by-one here silently shuffles every photo on the page.

**Identify each section by its heading text, never by index, order or height.** Frame
frame names are meaningless (Figma auto-names like `Frame 1234567890`). In one real file the
sections were mislabeled by one position, which silently swapped two of them and dropped a
whole section that nobody noticed until the renders were viewed. Print the largest
`characters` value inside each node and name the section from that:

```bash
# name every section by what it actually says
for f in figma/nodes/*.json; do python3 scripts/figma_spec.py "$f" 4 | head -8; done
```

**Placeholder copy is a finding, not an invitation.** If `characters` reads `"Label"`,
`"Lorem ipsum"`, or the same blog title three times, that *is* the design. Ship it
verbatim and record it in the difference log. Do **not** invent category names, brand
names or headlines to fill the gap — inventing copy is the same class of error as
inventing a section.

Write this as a reusable script (`spec.py`) that prints, per node: type, position
relative to the section, size, `characters`, font family/weight/size/line-height/case,
fill, stroke, radius, and layout mode. Read its output before coding the section.

### 6.5.4 Fonts: measure, never eyeball

1. Extract the real font family and weight from the JSON.
2. If it is unavailable (premium/no CDN), **measure** candidates instead of guessing:
   take a long heading, and compare rendered width at the design's font-size/weight
   against the Figma text-box width (`canvas.measureText`, after `document.fonts.load`).
3. Choose the candidate that matches **both** the metric and the *classification*
   (Didone ≠ Garamond ≠ transitional). A metric-close font of the wrong classification
   still looks wrong.
4. Record the substitution and the measured delta in the difference log.
5. Offer the user an `@font-face` swap if they hold a licence for the real file.

### 6.5.5 The per-section build loop

For each section, in page order — never batch:

1. **Look** at the section's reference render. *(What it looks like.)*
2. **Read** the `figma_spec.py` dump for that node. *(What the numbers are.)*
   You need both. The render alone makes you guess numbers; the JSON alone makes you
   build the right-sized box around the wrong design.
3. **Build from the spec, not from the picture** — see §6.5.5.1.
4. **Lint** before you look: `python3 scripts/figma_lint.py --css … --html … --nodes …`
   It fails on any spacing, size or colour that exists nowhere in the design.
5. **Verify visually**: serve the page, isolate the section, screenshot it at the design
   frame width, compare against the render.
6. **Verify per section, live**: `python3 scripts/figma_report.py --only <section>` — this
   runs the *text audit* (§18.0) for that one section. Do not defer it to the end; a
   hundred small offsets are cheap to fix one section at a time and brutal in bulk.
7. Record residual differences in the difference log. Only then move to section N+1.

Do not proceed to section N+1 while section N is unverified.

### 6.5.5.1 Build from the spec — the rules that prevent the offsets

Every number in the design exists in the JSON. If a value in your CSS is not in the file,
you invented it, and the text audit will find it later as an offset.

- **Spacing.** `gap` and `padding` come from `itemSpacing` and `padding*` on the
  auto-layout frames. Do not eyeball rhythm from the render, and do not reach for a
  spacing scale you like. `figma_lint.py` rejects any value the design never uses.
- **Type.** `font-size`, `font-weight`, `line-height`, `letter-spacing` and `text-transform`
  come from each TEXT node's `style` (and its `styleOverrideTable`). Never retype a size
  from memory.
- **At the design width, every declared value must resolve to the Figma number.** Put
  responsive behaviour in media queries. Hiding the design value inside `clamp()` makes it
  unauditable and invites drift.
- **Colour.** Take the hex from the node's own `fills`. Do not pick "the token that looks
  right" — two golds that differ by one step read as identical to you and as a defect to
  the audit.
- **Copy is verbatim `characters`.** Insert `<br>` **only** where the string contains a
  newline. Inventing a line break changes the copy and silently breaks every text-based
  check. `figma_lint.py` counts them.
- **Position.** Reproduce the section's own container offsets, not a global container you
  reused. Different sections legitimately have different gutters.
- **Icons are exported assets, never hand-drawn.** An inline `<svg>` you wrote from memory
  is a different icon: different stroke weight, different metaphor, different silhouette.
  It reads as "close enough" to you and as wrong to the person who drew it. Export every
  vector (§0.5) and reference it. If the design draws something you genuinely reproduce in
  CSS (a dot, a rule, a circle), that is an exception you must *declare* — pass it to
  `figma_lint.py --allow-inline-svg N` and list it in the difference log.


**Before the browser, run `figma_lint.py`. Two of its checks decide the whole text audit:**

- *missing copy* — every visible `characters` string must appear verbatim in the HTML source
  (page text, or `placeholder`/`aria-label`/`value`/`alt`). If it fails, you dropped,
  reworded or invented copy; fix it now, not after a hundred "not found in DOM" rows.
- *invented spacing* — a `gap` or `padding` that exists nowhere in the design is the single
  cause of the position failures the text audit reports. When the report later says "223
  present, 12 positioned", the 211 are almost always downstream of one guessed gap. Transcribe
  every spacing value from `figma_spec.py`; invent none.
### 6.5.6 Blocked-section reporting

When a reference is unobtainable, say exactly this, per section, and stop:

> **BLOCKED — [section]**: no reference image (reason: `429`, `Retry-After 4.6 days`).
> Copy and geometry are extracted, but the visual composition is unverified. I will not
> implement it from geometry alone. Options: (a) send me a screenshot of this frame,
> (b) grant an account with render quota, (c) wait for the limit to reset.

Never present a geometry-only reconstruction as a finished section.

---

## 7. Pixel-Accuracy Workflow

Follow this sequence.

### Step -1 — Discovery (gate)

Run `figma_discover.py` and report breakpoints, icon library, hover variants and page count
to the user (§6.5.0.5). Everything downstream assumes you know the answers.

### Step 0 — Reference Capture (gate)

Follow §6.5.2. Obtain and **view** one reference image per section before any coding.
Sections without a viewed reference are BLOCKED (§6.5.6) and must not be implemented.

### Step 1 — Inventory

Create a checklist of:

- pages;
- frames;
- components;
- assets;
- fonts;
- breakpoints;
- interactions;
- unknowns.

### Step 2 — Extract Design Tokens

Build a centralized token system before styling individual sections.

### Step 3 — Build Semantic Structure

Use semantic elements where appropriate:

- `header`
- `nav`
- `main`
- `section`
- `article`
- `aside`
- `footer`
- `button`
- `form`
- correctly ordered headings

Avoid unnecessary wrapper elements.

### Step 4 — Implement From Large to Small

Recommended order:

1. global reset and tokens;
2. page container and grid;
3. header/navigation;
4. major sections;
5. reusable components;
6. typography;
7. imagery;
8. interaction states;
9. responsive behavior;
10. animation after approval.

### Step 5 — Visual Comparison

Do this **per section, immediately after building it** — not once at the end. Serve the
page, isolate the section (hide the others), screenshot at the design frame width, and
compare against that section's reference.

> Numeric agreement is not visual agreement. Matching every frame height to the pixel
> proves nothing about whether the design is right.

Inspect:

- horizontal alignment;
- vertical rhythm;
- element dimensions;
- text wrapping;
- line breaks;
- image cropping;
- border radius;
- shadows;
- colors;
- icon alignment;
- section height;
- responsive transitions.

### Step 5.5 — Numeric Verification Matrix (mandatory, per section)

Measure in the browser (`getBoundingClientRect`/`getComputedStyle`) and assert against the
Figma values. Font/colour checks alone NEVER count as "verified".

| Element class | Must assert |
|---|---|
| Repeated items (tabs, cards, chips, logos) | each item w×h; EVERY inter-item gap; container width, border colour+width, shadow presence |
| Buttons / badges | rendered w×h ±1 (border-box incl border); text letterSpacing/weight/size/textCase; computed `display`+`justify-content` measured IN PLACE (nested), not in isolation |
| Multi-line headings | per-line start-x equal (`Range.getClientRects()`); `text-align`; `text-indent`; `margin-inline` reset when extending a centred base class |
| Divider → next row | rendered gap = Figma `nextNode.y − divider.y` (±2) |
| Card rows with shared baselines | trailing elements' tops equal across the row |
| Side-by-side panels | tops equal when Figma y is equal |
| Images / media | pager dots present when the frame contains dot ELLIPSEs; directional photo orientation matches |
| Icon sets | exactly one container shape per icon (SVG internals vs wrapper), consistent across the SET |
| Fonts | `document.fonts.check` true for every family+weight used |
| Raster logos | visible ink (content bbox), group opacity, rendered colour unified with siblings |

Run the matrix at the design width, one wider viewport (≥1920) and one narrower.
After editing any shared CSS (base class, container rule, specificity), re-run on every
sibling in that container — not just the element you fixed.
Verify a CSS edit only after hard-navigating to a fresh URL (`?cb=<n>`) and asserting the
changed property's computed value first (FM92).

### Step 6 — Difference Log

Maintain a concise list:

| Area | Difference | Cause | Fix |
|---|---|---|---|
| Hero heading | Wraps one line earlier | Font metric mismatch | Load correct font or adjust width |
| Card gap | 4 px too large | Grid gap token | Change 28 px to 24 px |

### Step 7 — Final Verification

Do not declare completion until the acceptance checklist passes.

---

## 8. Responsive Implementation Rules

Never treat mobile as a scaled-down desktop layout.

**When a breakpoint's DOM ORDER differs from desktop, do not bend the desktop markup with
`display:contents` + `order:` + `:nth-of-type()`. Author the mobile structure directly.**
This is the single biggest time-sink and the biggest source of oscillation in a build. If
the mobile frame stacks nodes in an order the desktop DOM cannot produce with simple flex
wrapping (e.g. two desktop columns interleave into one mobile column), you have two honest
options, in order of preference:
  1. **Reorder the source DOM** so the mobile order is natural, then place the desktop
     layout with grid/`order` at the *fixed* desktop width (stable) — never the reverse.
  2. If desktop is already green and shipped and you must not touch its DOM, build the
     mobile version from **row-major source order + flex-wrap `width:50%`** (works when the
     design's two columns are filled left-to-right, top-to-bottom) rather than
     `:nth-of-type()` grid placement. `:nth-of-type()` keys off the element *tag*, silently
     mismatches when siblings differ, and collapses when the flex/`contents` parent doesn't
     stretch (FM115). A `display:grid` inside a `display:contents` / shrink-wrapped flex
     item routinely gets a `1fr` track that collapses to a few px — verify the *container
     width* first, not the track template.
Reproduce a component's per-breakpoint default state (an accordion the mobile frame draws
expanded but desktop draws collapsed) with a `matchMedia` open/close sync — that is Mode A,
it reproduces the design's state, it adds no behaviour (FM116).

For each breakpoint, verify:

- navigation transformation;
- content stacking;
- section order;
- text size and wrapping;
- container padding;
- grid column count;
- button width;
- touch target size;
- card density;
- image crop;
- overflow;
- fixed and sticky behavior.

Use content-driven breakpoints where possible. When the design supplies explicit frame sizes, reproduce those first.

Re-run the Step 5.5 verification matrix at EVERY breakpoint you ship, plus one width
wider than the design frame. Alignment bugs that depend on container width (a `margin:auto`
block centring inside a wider column, a fixed-width row overflowing) are invisible at the
design width — they only appear wider or narrower (FM103).

**Fixed pixel columns copied from Figma are a desktop-only truth.** A rule like
`grid-template-columns: <a>px <b>px`, lifted straight from the frame, is exact at the
design width and overflows the moment the container is narrower than `a + b + gap`. Every such rule needs a breakpoint
above the point where it breaks — not just at the usual 1024 px — converting it to `fr`,
`minmax()` or a stack. Check for overflow at the design width **and** at each step down,
not only at the mobile preset.

Suggested baseline only when the design has no breakpoint specification:

```css
/* Mobile first */
@media (min-width: 640px) { }
@media (min-width: 768px) { }
@media (min-width: 1024px) { }
@media (min-width: 1280px) { }
```

Do not use these blindly. Adapt breakpoints to the actual design.

---

