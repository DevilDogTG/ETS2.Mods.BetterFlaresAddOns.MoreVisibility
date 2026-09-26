# ADR-0001: Generate the add-on from upstream Better Flares v4.8, v4.8 only

- Status: accepted
- Date: 2026-09-26

## Context
The add-on retunes Better Flares' (Avelium) DOT 7500k truck headlights. ETS2 mods replace whole
files, never single fields, so every shipped `head_light/*.sii` carries a full copy of upstream's
values and wins over Better Flares when loaded above it.

The previous build (v0.1.0, predecessor repo `ETS2Mods.BetterFlaresHeadlightVisibilityAddOns`) was
generated from Better Flares v4.7.2. On v4.8 it broke:
- it referenced masks v4.8's base pack no longer ships (`bf_trucklight_mask_norm_dot.tobj`,
  `bf_trucklight_mask_high_dot.tobj`; v4.8 has `_norm_dot_c`, `_norm_dot_w`, `_high`);
- it forced v4.7's aim (-2 deg pitch vs v4.8's -6), aspect (2 vs 3) and refracted setup back on;
- its brightness multipliers were relative to v4.7's baseline, roughly 2x brighter than v4.8's.

Across all 261 v4.8 DOT 7500k head_light files, every per-light value is identical; only
`reflectors_*` and metadata vary per truck.

## Decision
- Target Better Flares **v4.8 only**, DOT 7500k only. v4.7 is not maintained.
- `src/def/` and `src/unit/` are **generated** by `tools/generate_headlights.py` from the extracted
  upstream pack, never hand-edited. The script edits only lever-targeted value tokens; aim, aspect,
  masks, comments and line endings stay byte-for-byte upstream.
- The script emits only files the levers actually change, so upstream is never overridden without
  a reason (the lamp-glow flare units ship only once their levers move).
- The script fails the build if any emitted file references a mask the v4.8 base pack doesn't
  ship: the exact failure that broke v0.1.0.
- Generated files are committed (reviewable diffs, `pack-mod` packs `src/` as-is) and pinned
  `-text` in `.gitattributes` so line endings round-trip exactly.

## Consequences
- Any Better Flares update means: re-extract, regenerate, diff, playtest. A mask rename is caught
  by the generator instead of in-game.
- The add-on must load above Better Flares v4.8 base and DOT 7500k in Mod Manager.
- It conflicts with any other mod shipping the same truck `head_light` files; there is no partial merge.
- Tuning is expressed as a few multipliers/offsets per beam stage rather than per-truck values,
  which matches upstream's own uniformity.
