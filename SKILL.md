---
name: figma-to-html-pixel-perfect
description: >
  Convert Figma designs, screenshots, design specifications, and design-system references
  into production-ready HTML and CSS with maximum visual fidelity. Use this skill whenever
  the user asks to recreate, implement, audit, improve, or make a website match a Figma design.
  The skill must distinguish exact design implementation from optional UX/UI enhancements,
  ask permission before making visible design changes, and verify responsiveness,
  accessibility, animations, and visual consistency.
---

# Figma → HTML/CSS, pixel-perfect

This file is the protocol. Detail lives in `references/` — **read the named reference at
each step; they are part of the protocol, not optional background.**

## THE NUMBER RULE — the one non-negotiable contract

**The node JSON is the complete design. Every px value you write into CSS must be a
number read from the node JSON, or arithmetic on such numbers, written down at the
moment you write the rule.** There is no legitimate third source of a value.

The only permitted workflow for creating OR fixing any spacing/size/position:

1. Dump the numbers: `python3 scripts/figma_spec.py figma/nodes/<section>.json`
2. Compute the CSS value from those numbers (`margin-top = child.y − (prev.y + prev.h)`).
3. Write the rule with the derivation in a comment: `margin-top: 24px; /* 404−(146+248−14lead) */`
4. Verify with the report once.

Forbidden, no exceptions, regardless of time pressure:

- **Nudge-and-remeasure.** The report prints `[design y…]` beside every delta precisely
  so the correct edit is a subtraction, not an experiment.
- **Reading only the delta.** `y +8` means: find WHICH gap in the JSON chain is wrong and
  set THAT gap to the design's number — not "subtract 8 somewhere".
- **Skipping step 1 because you are in a hurry.** Skipping it under time pressure is what
  produced the slowest sessions on record. The fast path IS the extraction path.

Tooling enforces this: `figma_report.py` auto-runs the duplicate-selector check (FM123)
every regen and prints design targets beside deltas; `figma_lint.py` fails on any CSS
value that exists nowhere in the design. If a guard fires, fixing it is the next action.

## Modes

| | A — Exact (DEFAULT) | B — Exact + advice | C — Approved changes |
|---|---|---|---|
| adds/changes anything visible | never | never (only proposes) | only what was approved |
| output | code + difference log | + prioritized audit | + what changed |

Static markup for carousels/accordions is A; wiring behaviour is C (explicit request).
Reproducing motion the design specifies is A (§ Motion below). Mode is per-request.
When unsure: A.

## Workflow — gates, in order

**0. Setup (once).** Token in `~/.figma_token`; check `design/` folder first; 403 "not
exportable" = owner must enable sharing, stop. → `references/setup.md`

**1. Discover — before any code.**
`python3 scripts/figma_discover.py <fileKey> --json figma/discovery.json`
Answers: how many design widths (= breakpoints to BUILD, not guess) · icon library? ·
hover variants? · multiple versions of the same screen? **Multiple versions: the user
picks; never pick for them.** Show the output to the user.

**2. Pull nodes, cache-first.** `python3 scripts/figma_pull.py …` — every REST endpoint
shares one quota and can 429 for hours; pull once, then work only from `figma/nodes/`.
Renders are the scarcest; a user-supplied `design/exports/page.png` replaces them.

**3. Fonts — first reply to the user.** `python3 scripts/figma_fonts.py figma/nodes/*.json`
→ request the licensed files by exact PostScript name; declare `@font-face` now so they
hot-swap in later; until then measure a substitute and disclose (never claim type fidelity).

**4. Motion check — before deciding "no animation":**
`grep -l '"interactions"' figma/nodes/*.json` — anything found is Mode A work.
→ `references/animation-guidelines.md`

**5. Per-section build loop.** For each section, in document order:
   a. `figma_spec.py` the section (NUMBER RULE step 1) — full spec table before any CSS.
   b. Build from the spec. Hard rules that prevent whole classes of offsets:
      - Top-anchor content; **never vertically centre inside a locked min-height** (FM109).
      - Text: read `styleOverrideTable` for per-character font/size changes (§ref), never
        only `style`. No invented `<br>` — lint counts them against design newlines.
      - Icons: `figma_icons.py` output only, never hand-drawn; photos: real `imageRef`
        bytes via `figma/assets-map.json`; logos never invented.
      - Fixed px column values from the frame are desktop-only truths — they need a
        breakpoint before the width where they overflow.
   c. Verify: regen report (step 6) — section is done when its row says `match`.
   → full detail: `references/build-guide.md`

**6. Report loop.**
`python3 scripts/figma_report.py --page <url> --nodes figma/nodes --selectors selectors.json --icons-dir figma/icons --assets-map figma/assets-map.json --out fidelity.html`
   - Poll `document.title === 'fidelity-READY'` — never sleep a fixed wait.
   - Bump `styles.css?v=N` after EVERY css edit or the browser measures stale CSS.
   - Read every row; **batch all sections' fixes from one read into one edit.**
   - The report waits for fonts + image decode and double-samples layout; if a count
     still changes with no edit to that section, suspect the verifier/page, not the CSS.
   - Fix section HEIGHT mismatches top-to-bottom before item spacing (deltas are
     page-absolute; upstream height errors cascade into everything below). The report
     renders a red `#heightDebt` banner whenever any section height is >6px off and a
     `#guardWarnings` banner for duplicate-selector shadowing — **every table read MUST
     return both banners' text first**; while `#heightDebt` is non-empty, per-item deltas
     are not to be acted on. A `⚠ LINEAR DRIFT` row means one repeated component's height
     is wrong — fix that unit, never the individual rows (FM128).
   - Edit had zero effect? grep for duplicate selectors (auto-warned, FM123) and check
     computed style in a fresh iframe (`contentWindow.getComputedStyle`) before retrying.
   - **After any `position:relative;left/top` or `transform:translate` shift, re-check
     `document.documentElement.scrollWidth === clientWidth` at every breakpoint before
     moving on.** A shift-only fix leaves the element the right SIZE, just partly off
     canvas — the text/box delta audit does not catch this; only an overflow sweep does,
     and the visible symptom can appear on a completely unrelated section (FM130).
   → `references/report-guide.md`

**7. Responsive = each confirmed breakpoint is a separate design.**
   - Split the frame into `figma/nodes-<width>/`, then validate: total visible TEXT count
     across split files MUST equal the frame's (a shortfall = a dropped subtree, FM119).
   - Diff per-breakpoint `imageRef`s (frames swap photos) and component default states
     (an accordion open on mobile, closed on desktop — reproduce via matchMedia, FM116).
   - If the mobile DOM order differs from desktop, author the mobile structure — do NOT
     bend desktop markup with `display:contents`+`order`+`:nth-of-type` (FM115).
   - Run the full report loop per breakpoint, plus one width wider than the design frame.
   - No mobile frame in the file → responsive behaviour is inferred: label it.

**8. Visual sweep — numeric green is necessary, never sufficient.** Twice: after the
first full build and before declaring done. Put the design render beside the settled
live build, section by section, and LOOK (a 40-line compare page; ~seconds per section).
Missing whole components hide in green reports (FM119-120).

**9. Deliver.** The fidelity report file + a difference log: every deviation, why, and
every placeholder/substitution. Do not claim a match the report does not show.
→ `references/report-guide.md`, `references/visual-review-checklist.md`,
`references/accessibility-checklist.md`

## Completion standard

- **Loop until green or every remaining row is documented, proven noise. Never ask
  "shall I continue?" while non-green rows remain.** Stop only for a real external
  blocker (quota, missing font/asset) — then report the blocker, not a fake completion.
- **Convergence guard:** the failing-row count must trend down. If it rises or
  oscillates 3 rounds without a new low, the structure is wrong, not the values —
  revert to the best round, measure the CONTAINER (width/display/stretch), fix the
  structure, only then resume value tuning.
- Speed comes from fewer rounds, never from skipping verification: extract-first
  (≤2 rounds per section), batch fixes across sections, answer node-JSON questions
  with python (never with a browser round-trip), dedupe CSS as you go.

## Clarification

Ask only when the gap genuinely blocks a reliable build (which frame is current, missing
licensed font, contradictory sources). Otherwise: build, infer conservatively, and LABEL
every inference in the difference log.

## Editing this skill

After ANY change to `scripts/` or this file: `python3 scripts/selftest.py` must pass
(exit 0). Every past failure mode with a testable guard is a fixture there — a red test
means a guard was broken or deleted, and the mistake it caught WILL recur silently.
When you add a new guard, add its fixture in the same edit.

## Failure modes — `references/failure-modes.md`

126 documented ways this work goes wrong, each with its fix. **Mandatory reading points:**
before the first build (FM1-30 layout/type), before icons/images (FM60-99), before
responsive (FM103, 109-120), when a verify result looks wrong (FM110-126), when edits
stop having effects (FM123). When you hit ANY new defect: fix the build, fix the verify
stage so it would have caught it, and add the failure mode — in design-agnostic terms.
