# Report & completion — fidelity report contract, loop standard, speed discipline

### 18.0 Ship a fidelity report — evidence, not assurances (required)

Never close a build with a sentence like "it matches the design". Hand the user something
they can check without trusting you:

```bash
# 1. once per project: sign the icon set so identity (not just presence) is checked
python3 scripts/figma_icons.py --svg design/exports/page.svg --nodes figma/nodes --out figma/icons
# 2. every audit round:
python3 scripts/figma_report.py --page http://localhost:PORT/index.html \
        --nodes figma/nodes --selectors selectors.json --icons-dir figma/icons
```

`selectors.json` maps each Figma section frame to ONE CSS selector:
`{"hero": ".hero", "collection": ".collection", ...}` — keys must match the node JSON
filenames. Without it sections are matched by DOM order, which mis-maps silently; the
report header lists any selector matching 0 or 2+ elements — fix those before reading rows.
Skipping `--icons-dir` downgrades the icon audit to presence-only (it will say so).
`--assets-map figma/assets-map.json` (`{imageRef: filename}`) enables image IDENTITY —
without it the report cannot say the RIGHT photo is on the node (on the reference build
this check caught two cards silently reusing another card's photo). Known noise: a file
with stacked overlapping variants stamps the template's imageRef over real positions —
identity rows saying "expects <first-photo>" at spots that already pass with their own
ref are variant ghosts (FM99), not defects.

Version every stylesheet and script from the first commit (`styles.css?v=1`, `main.js?v=1`)
and bump on each edit — browsers heuristically cache unversioned assets and the report (and
you) will measure stale code (FM92).

It writes `fidelity-report.html`, which for every section shows the Figma reference beside
the **live** page, with a cross-fade slider and a *difference* blend (a perfect match goes
black), and computes — in the browser, at load time:

| Check | Why it exists |
|---|---|
| section height, Figma vs built | the obvious one |
| **content extents (left–right edge)** | heights match while a container is offset sideways; only this catches it |
| horizontal overflow | breaks silently below the design width |
| total page height | catches drift that per-section rounding hides |
| **every TEXT node: position, size, weight, colour** | the box can be perfect while the design inside it is wrong |
| **every icon: exported asset / hand-drawn / missing** | hand-drawn icons pass every geometric check and still look wrong |
| **every image: real photo / gradient placeholder / missing** | placeholders survive to production when nothing counts them |
| **every non-text box: fill colour, corner radius** | the text audit is blind to a panel with the wrong colour |
| **sections with no reference slice** | an unchecked section is how a whole section goes missing |
| **the section→selector mapping itself** | a selector matching 0 or 2 elements silently invalidates every row |
| **hover transition durations** vs `interactions[]` | the design states them; nothing else checks you shipped them |
| **stroke colour and drop shadows** on boxes | a rule the design draws as a stroke is easy to fake as an element |
| **image identity** (`--assets-map`) | "a photo is present" is not "the right photo is present" |
| **confirmed breakpoints not covered** (`--breakpoints`) | a second design silently never gets built |

**Do not stop at the geometry checks.** They pass on a page that looks nothing like the
design. In one build every section matched on height *and* content extents while only
**10 of 224 text nodes** matched on position, size, weight and colour. The geometry row is
a smoke test, not a verdict.

Three traps the text audit itself must avoid:

- Compare the **ink box** of the text (`Range.getBoundingClientRect()`), not the element
  box. A centred heading lives in a full-width block; comparing element rects reports a
  huge false offset.
- Only compare `font-weight` **within the same typeface**. And a declared `@font-face`
  whose file 404s still appears in `getComputedStyle().fontFamily` — ask
  `document.fonts.check(...)` whether the face actually loaded before trusting it.
- `text not found in DOM` is a real finding, not noise: it means your copy or your markup
  splits the string differently from the design.
- Group an icon at the **outermost pure-vector subtree**. Recurse further and every glyph
  outline of a logo is counted as its own missing icon.
- An icon reported `missing` may be a vector the design draws as a shape and you
  legitimately reproduce in CSS. That is a decision to record, not a row to ignore.

#### Guard the guards

An audit that can be fooled is worse than none, because it grants permission to stop
looking. Three holes are easy to leave open — close them:

- **Custom properties.** A linter that skips declarations containing `var()` can be
  defeated by moving the invented number into a token. Resolve `var()` before checking.
- **Section completeness.** A report that iterates over the references you happened to
  produce cannot notice a section you never sliced. Enumerate the design's sections and
  flag every one without a reference.
- **Selector mapping.** Require an explicit section→selector map, and fail if any selector
  matches zero or several elements. Falling back to DOM order will one day compare the
  wrong things and report green.

And in the box audit, separate a **wrong fill/radius** (a defect) from **no 1:1 element**
(a structural difference — Figma frames do not map one-to-one onto DOM elements). Reporting
them together produces a number that means nothing.

#### The audit runs in both directions

Every check that walks **design → DOM** ("the design has an icon here; is it in the page?")
is blind to whatever you *added*. That is not a small gap. A stray element, a doubled
control, a leftover from a refactor — none of them exist in the design, so nothing looks for
them, and the report keeps saying the build matches.

`figma_report.py` therefore also walks **DOM → design**: every graphic in a section that no
design node accounts for is listed as *not in the design*. Read that row. It is the only
place a mistake of commission can show up.

The same asymmetry applies to identity. "An icon is present at this node" and "the icon the
design puts at this node is present" are different claims, and only the second one is worth
anything. `figma_icons.py` stamps each exported icon with `data-icon-shape` (a scale- and
translation-invariant outline profile) and `data-icon-paint`; the report compares those,
with a tolerance on the shape and exactly on the paint. Two traps it exists to avoid:

- hashing the geometry — the same icon reused on the next card sits at sub-pixel-different
  coordinates, so a hash reports every legitimate reuse as a mismatch;
- comparing geometry alone — a filled star and an outlined star are the *same* outline and
  differ only in `fill`.

And because a comparator that always answers "different" makes a perfect build look broken,
the report proves it can recognise a file as itself before it reports a single verdict.

#### What this report still does *not* check

State this to the user, every time. A green report is evidence about what was measured and
nothing else.

- **the visual result of a hover state.** Durations are verified; what the variant *looks
  like* is not. Fetch the variants (`figma_pull.py --hover <destIds>`), look at them, and
  match your `:hover` by eye.
- opacity, gradients, z-order and overflow clipping
- focus and active states; keyboard behaviour
- accessibility and performance
- **regression** — there is no baseline diff; a fix that breaks another section shows up
  only if you read the whole report again
- anything at viewports other than the design width, and any breakpoint you did not build

Those need the difference-blend view, the reference frames, and your eyes.

Rules:

- The report's numbers are computed live from the page. **Do not paste a summary that the
  report does not show**, and do not claim a section matches while its row says *differs*.
- **Verify the verifier.** Before trusting a comparison view, confirm the reference and the
  live page are drawn at the same scale and offset; a mis-scaled overlay makes any build
  look correct. Confirm a known-bad section actually reports as bad.
- When you change CSS and re-measure through an iframe, **bust the cache** — a stale
  stylesheet will happily tell you the fix worked.
- Rows that legitimately differ (a decorative element you rendered as a shadow, a font
  substitution) belong in the difference log with the reason — not hidden by loosening the
  tolerance.
- A green report is *evidence about geometry*, not proof of visual fidelity. The
  difference-blend view is what proves that; look at it, and say what you saw.

At completion provide:



## 20.5 Completion Standard — audit until green, do not ask

**Do not stop at "structurally correct" and hand it over. Do not ask permission to keep
going. Iterate until the report is green or every remaining row is a proven, documented
non-defect.**

The loop is not optional and it is not "one pass":

```
build → figma_report.py → read EVERY row → fix the largest deltas → regenerate → repeat
```

**Speed discipline — the loop converges in rounds, and every round costs a browser
round-trip (~15-30s). The way to be fast with the same result is to need FEWER rounds,
never to skip the verify:**

1. **Extract-first, one-pass build.** Every value the section needs — y, x, w, h,
   font/weight/size/line-height, text-align, fills, radii, per-breakpoint image refs —
   is in the node JSON and readable in milliseconds. Dump the section's full spec table
   FIRST (figma_spec.py or a 10-line python walk), write the section's CSS to match ALL
   of it in ONE edit, then verify. If you find yourself nudging a value and re-measuring
   to see where it lands, you skipped the extraction — the design already told you the
   number. Target ≤2 rounds per section: build → verify (→ one fix round).
2. **Batch across sections.** One report read surfaces deltas in every section; fix ALL
   of them in one edit before regenerating. N sections is one round, not N rounds.
3. **Never use a browser round-trip to answer a node-JSON question.** Python on the
   cached JSON is ~100× faster than probe-iframe-and-wait. The browser is for: the
   verify gate, computed-style mysteries the cascade can't explain, and screenshots.
4. **Front-load the discovery checks** (split completeness FM119, per-breakpoint
   imageRef diff, per-breakpoint component-state diff FM116, §8 DOM-order check) BEFORE
   writing any CSS for a new breakpoint. Each one found late forces a rebuild of work
   already "done".
5. **Visual sweep twice, not per-round:** once right after the first full build (catches
   missing components while they're cheap) and once before declaring done. Numeric loop
   rounds in between don't need screenshots.
6. **Poll the report's READY signal, never sleep a fixed wait.** figma_report.py sets
   `document.title='fidelity-READY'` when every audit has landed; loop on the title with
   short sleeps. A fixed 12s wait either wastes time or reads a half-built table.
7. **Distrust deltas that move with no edit.** The report refuses to measure until fonts
   are loaded, images decoded and two layout samples agree — so a count that still changes
   between runs with no edit to that section means the verifier (or the page) is unstable.
   Fix that first; tuning CSS against unstable numbers is the most expensive way to wait.

Rules:

- **A section is done when its row says `match`**, not when it "looks about right" and not
  when the structure is in place. Structure without the per-section numeric pass is an
  unfinished section, and reporting it as finished is a false claim.
- **Never ask "shall I keep going?" while non-green rows remain.** The user asked for the
  design; the remaining rows *are* the difference between what you built and the design.
  Continue automatically. Only stop early for a genuine external blocker (quota, missing
  asset, missing font) — and then report the blocker, not a fake completion.
- **Every breakpoint the user confirmed gets its own full loop.** Split the second frame
  into per-section nodes (`figma/nodes-<width>/`) and run the same report against it; the
  design width is read from the nodes, so no tooling changes are needed. A breakpoint with
  no report is a breakpoint that was guessed.
- Stop only when: every row is green, **or** every non-green row is written into the
  difference log with evidence that it is noise (an overlapping design variant, a
  matcher artifact) rather than a build defect.
- If a fix makes another row worse, that is normal — re-read the whole report each round,
  not just the row you touched.
- **Fix section HEIGHT before section item-spacing, top to bottom.** Check the report's
  per-section `height figma/built` row first. A section whose total height is off will
  make every item below it (in that section AND in every section after it, if the delta
  is page-absolute) drift by a constant — that constant is not a local bug in each of
  those items, it is inherited. Chasing individual item deltas before the height matches
  wastes rounds correcting a symptom whose cause is one line above. Work sections in
  document order for exactly this reason.
- **When an edit changes a value with zero measured effect, do not try a different value
  next — find out why the current one didn't apply.** grep the selector for duplicates in
  the same media query (FM123) first; it is the most common cause. Check computed style
  (`getComputedStyle` on the element in a fresh iframe) before guessing a bigger number.
- **Periodically deduplicate the mobile media query block** in a long session — every
  round that appends rather than edits leaves one more selector at risk of a later
  duplicate silently winning. A last-value-wins consolidation pass (parse `@media
  (max-width: …) { … }`, merge same-selector declarations keeping the last value per
  property, rewrite) costs one script run and can unlock many "stuck" rounds at once.

**Convergence guard — do not thrash.** Track the section's failing-row count each round.
The loop must trend *down*. If a round raises the count, or the count oscillates across
three rounds without a new low (e.g. 22 → 27 → 22 → 27), **stop tuning by single-pixel
deltas — the layout is structurally wrong, not numerically off.** Per-node deltas can only
converge when the box model is right; chasing them on a fragile structure moves the error
around forever. When you detect oscillation:
  1. Revert to the round with the lowest count (keep the CSS that produced it).
  2. Stop reading per-node deltas and instead ask *why the structure allows the drift* —
     measure the **container** (its width, display, whether a flex/grid parent stretches),
     not the leaf text node. One structural fix (a real 2-column mechanism, a stretched
     container, a reordered DOM per §8) collapses a dozen deltas at once.
  3. Only resume per-pixel tuning once the structure holds — verify the container geometry
     with `iframe.contentWindow.getComputedStyle` (never the parent window's — it returns
     an empty declaration, FM117) before trusting any delta.
A round that costs a report regen + a browser probe is expensive; spending twenty of them
walking one value up and down is the failure this guard exists to catch.

The number of rounds is not a cost to be minimised. Shipping a wrong page is.

---

