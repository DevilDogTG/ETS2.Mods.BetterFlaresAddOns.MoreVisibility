# ADR-0002: Override Better Flares v4.9's shared color.sui instead of per-truck defs

- Status: accepted
- Date: 2026-10-28
- Supersedes: [ADR-0001](ADR-0001-generate-from-upstream-v48.md) (its file set and v4.8-only scope; its
  generate-from-upstream approach stands)

## Context
Better Flares v4.9 replaced the v4.8 headlight options (one pack per standard and colour, e.g. DOT 7500k) with two
packs the player combines:
- **Headlights.1** (beam pattern: `proj_dot1/2/3`, `proj_ece1`, `refl_dot1`, `refl_ece1`): 280 truck defs that set
  only the five beam masks and `@include "/def/vehicle/_common/color.sui"`.
- **Headlights.2** (colour: `2000K_led` ... `9500K_xen`): ships that `color.sui` with every beam value (aim, colour,
  range, angle, aspect, bias, refracted) for every truck, plus the headlight flare units.

v4.9.1 also deleted every `bf_trucklight_mask_*` texture. MoreVisibility 1.0.0 ships 261 whole truck defs naming six of
them, so on v4.9 it breaks the masks and overrides the player's Headlights.1 and Headlights.2 choice with v4.8 values.

v4.9.1 Headlights.2 7500K LED alone already exceeds 1.0.0 in brightness (~1.94x v4.8 vs 1.0.0's 1.35x), low-beam
reach (140 vs 130), roof reach (400 vs 360) and near-field spill (refracted range 60 vs 5.2). It is narrower
(90 deg vs 103) and its high beam is shorter (240 vs 280).

## Decision
- Ship three files, generated from Headlights.2 7500K LED by `tools/generate_headlights.py`:
  `def/vehicle/_common/color.sui`, `unit/hookup/vehicle/flare/vehicle_headl.sii`, `vehicle_high_beam.sii`.
  No truck defs. The mod works with any Headlights.1 pattern.
- Keep Better Flares' brightness, low-beam and roof reach, near-field spill, bias, aim and aspect (user,
  2026-10-28). Keep two 1.0.0 values as absolutes: angle 103 deg on every stage, and range 280 for `hi_beam` and
  `front_beam`. Keep 1.0.0's lamp glow (T5) on Headlights.2's flare units.
- 7500K LED only.
- The generator checks every Headlights.1 def it can find: each must include `/def/vehicle/_common/color.sui` and
  name only masks the base pack ships.
- Major version 2.0.0: requires Better Flares v4.9, different file set.

## Consequences
- Load order: this mod above Better Flares Headlights.2 7500K LED (both ship the same three paths). Headlights.1
  and Headlights.2 are both required; base, Traffic Addon and City Lights are unaffected.
- With another Headlights.2 colour loaded below, this mod still applies 7500K values (it replaces `color.sui`).
- If Better Flares renames `color.sui` or moves beam values back into Headlights.1, the generator's h1 check fails
  and the mod must be redesigned.
- Wider angle at aspect 2 also raises the vertical spread. If that lights signs or trees too high, an aspect lever is
  the next step (2.29 keeps v4.9's vertical spread at 103 deg).
