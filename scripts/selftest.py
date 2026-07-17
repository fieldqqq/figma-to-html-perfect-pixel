#!/usr/bin/env python3
"""Regression suite for the skill's own guards.

Every past failure mode with a testable guard gets a fixture here that the guard MUST
catch (and a negative fixture it must NOT false-positive on). Run after ANY edit to
scripts/ or SKILL.md:

    python3 scripts/selftest.py        # exit 0 = all guards alive, exit 1 = a guard broke

This is the answer to "how do you know the same mistake cannot come back": the mistake
is encoded as a test. If a future edit deletes or breaks a guard, this fails loudly
BEFORE the guard silently misses the next real defect.
"""
import json, os, re, sys, tempfile, pathlib

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

PASS, FAIL = 0, 0
def check(name, ok, detail=""):
    global PASS, FAIL
    if ok: PASS += 1; print(f"  ok   {name}")
    else:  FAIL += 1; print(f"  FAIL {name}  {detail}")


# ---------------------------------------------------------------- FM123: duplicate selectors
from figma_lint import duplicate_selectors

print("FM123 duplicate-selector guard")
css_dup = "@media (max-width: 640px) { .a { margin-top: 10px; } .b { color: red; } .a { margin-top: 20px; } }"
hits = duplicate_selectors(css_dup)
check("same-selector same-property in one media block IS flagged",
      any(s == ".a" and "margin-top" in props for _, s, props in hits), str(hits))

css_ok = ".a { margin-top: 10px; } .a { transition: color .2s; }"
hits = duplicate_selectors(css_ok)  # disjoint properties: normal pattern (base + transitions group)
check("same-selector DISJOINT properties is NOT flagged (no wolf-crying)",
      not any(s == ".a" for _, s, _ in hits), str(hits))

css_split = "@media (max-width: 640px) { .a { gap: 4px; } } @media (min-width: 1280px) { .a { gap: 9px; } }"
hits = duplicate_selectors(css_split)  # different media blocks: legitimate per-breakpoint values
check("same selector across DIFFERENT media blocks is NOT flagged",
      not hits, str(hits))


# ---------------------------------------------------------------- invented-value lint (FM97 class)
from figma_lint import css_numbers, custom_props

print("FM97 invented-value guard (via css_numbers + design vocabulary)")
css = ":root { --s: 24px; } .x { gap: var(--s); padding: 17px; }"
props = custom_props(css)
gaps = set(css_numbers(css, "gap", props))
pads = set(css_numbers(css, "padding", props))
check("resolves var() so hidden values are still audited", gaps == {24}, str(gaps))
design_spacing = {24, 32}
invented = sorted(v for v in pads if v not in design_spacing)
check("17px absent from design vocabulary is caught as invented", invented == [17], str(invented))


# ---------------------------------------------------------------- FM119: split completeness
print("FM119 split-completeness rule (text counts must sum to frame total)")
def count_texts(node):
    if node.get("visible") is False: return 0
    n = 1 if node.get("type") == "TEXT" else 0
    return n + sum(count_texts(c) for c in node.get("children") or [])
frame = {"type": "FRAME", "children": [
    {"type": "TEXT", "characters": "a"},
    {"type": "GROUP", "children": [{"type": "TEXT", "characters": "b"},
                                   {"type": "TEXT", "characters": "c", "visible": False}]}]}
splits = [{"type": "FRAME", "children": [{"type": "TEXT", "characters": "a"}]}]  # 'b' dropped
check("dropped subtree is detected (frame 2 visible texts vs split 1)",
      count_texts(frame) == 2 and sum(count_texts(s) for s in splits) == 1)


# ---------------------------------------------------------------- report guards present & wired
print("report guards present in the generated page (deletion smoke test)")
src = (HERE / "figma_report.py").read_text()
for name, needle in [
    ("FM110 scrollbar auto-widen",        "DESIGN_W - d.documentElement.clientWidth"),
    ("FM118 WAAPI settle",                "a.finish()"),
    ("FM122 fonts.ready wait",            "d.fonts.ready"),
    ("FM122 capped img decode",           "im.decode"),
    ("FM122 double-sample stability",     "sample()==="),
    ("FM131 matchMedia swing",            "DESIGN_W + 700"),
    ("heightDebt banner",                 "id=\"heightDebt\""),
    ("guardWarnings banner",              "id=\"guardWarnings\""),
    ("FM128 linear-drift detector",       "LINEAR DRIFT"),
    ("READY completion signal",           "fidelity-READY"),
    ("design target beside every delta",  "[design y${t.y}]"),
    ("dup warnings injected into HTML",   "__DUP_WARNINGS__"),
]:
    check(name, needle in src, f"needle missing: {needle!r}")

# the swing must run AFTER the settle sampler (FM131 ordering bug was real)
i_settle, i_swing = src.find("sample()==="), src.find("DESIGN_W + 700")
check("FM131 swing ordered AFTER settle sampler", 0 < i_settle < i_swing,
      f"settle@{i_settle} swing@{i_swing}")


# ---------------------------------------------------------------- SKILL.md contract intact
print("SKILL.md contract intact")
skill = (HERE.parent / "SKILL.md").read_text()
for name, needle in [
    ("NUMBER RULE present",         "THE NUMBER RULE"),
    ("nudge-and-remeasure banned",  "Nudge-and-remeasure"),
    ("heights-first rule",          "HEIGHT mismatches top-to-bottom"),
    ("banner read contract",        "#guardWarnings"),
    ("split completeness rule",     "MUST equal the frame"),
    ("convergence guard",           "Convergence guard"),
    ("visual sweep mandatory",      "never sufficient"),
]:
    check(name, needle in skill, f"needle missing: {needle!r}")

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
