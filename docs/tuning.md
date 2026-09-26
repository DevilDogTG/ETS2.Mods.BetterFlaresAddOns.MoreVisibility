# Tuning reference

The tuning levers live at the top of `tools/generate_headlights.py` (`STAGE_LEVERS`, `FLARE_LEVERS`).
This page records what each round (Tx) controls, the released values, and how they were reached, so
a future round (new Better Flares release, or a retune) starts from known ground.

**Tuning intent:** comfortable night driving first; in bad daytime conditions (rain, fog, overcast)
the road stays readable; keep Better Flares' realistic mood (no arcade glare). The engine limits how
visible a lamp can be in daylight; that ceiling is accepted.

## Rounds

Values are Better Flares v4.8 DOT 7500k stock → released `1.0.0`. Head_light values are identical
across all 261 truck files, so one row covers every truck.

| Round | Lever group | Fields | Stock v4.8 | Lever | Released 1.0.0 | Check in-game |
|---|---|---|---|---|---|---|
| **T1** | Intensity | `*_color`, `*_color_specular`, `*_color_ambient` | low `(2.142, 2.413, 3.2)` | `color_mult` 1.35 (all stages) | low `(2.8917, 3.25755, 4.32)` | Road brightness at night; readability in bad daylight |
| **T2** | Reach | `*_range` | low 100 / hi, front 200 / roof, front_roof 240 | `range_mult` 1.3 / 1.4 / 1.5 | 130 / 280 / 360 | How far the lit pool carries before fading |
| | | `*_bias` | 0.0 | `bias_add` +0.15 / +0.15 / +0.2 | 0.15 / 0.15 / 0.2 | Semantics undocumented; watch for washed-out road or a changed cut-off |
| **T3** | Width | `*_angle` | 95° (aspect 3.0 untouched) | `angle_add` +8 (all stages) | 103° | Shoulder coverage, curves; glare on signs and oncoming traffic (vertical FOV grows too) |
| **T4** | Near-field | `*_refracted_color_fraction` | 0.01 | `refr_fraction_mult` 1.5 | 0.015 | Light just ahead of the bumper; smooth blend into the main beam |
| | | `*_refracted_range` | 4.0 | `refr_range_mult` 1.3 | 5.2 | |
| **T5** | Lamp glow | `vehicle_headl`: `default_scale` / `scale_factor` | 1.6 / 3.5 | `default_scale_mult` 1.15, `scale_factor_mult` 1.1 | 1.84 / 3.85 | Lamp readable in poor daylight without blooming into a blob |
| | | `vehicle_headl`: `flare_inner_angle` / `flare_outer_angle` | 80° / 100° | `inner_angle_add` / `outer_angle_add` +10 | 90° / 110° | Glow still visible from off-axis |
| | | `vehicle_high_beam`: `default_scale` / `scale_factor` | 1.8 / 4.0 | same levers | 2.07 / 4.4 | |
| | | `vehicle_high_beam`: `flare_inner_angle` / `flare_outer_angle` | 70° / 100° | same levers | 80° / 110° | |
| **T6** | Aim (not used) | `*_rot` pitch, or the `_norm_dot_w` mask | −6.2° / −6.3°, `_norm_dot_c` | *no lever yet* | stock | Only if reach still feels short; needs a new generator lever (keep the missing-mask check) |

Stages: `low_beam`, `hi_beam`, `front_beam`, `roof_beam`, `front_roof_beam`. Slash-separated lever
values read low / hi, front / roof, front_roof.

The T5 flare units are shared by every vehicle using Better Flares' headlight glow, most likely
AI traffic too.

## History

| Build | Changed | Verdict |
|---|---|---|
| 1.0.0-dev.1 | T1 intensity ×1.35 | Fine, kept |
| 1.0.0-dev.2 | + T2 range ×1.3–1.5, bias +0.15/+0.2 (the predecessor v0.1.0's values) | OK, kept |
| 1.0.0-dev.3 | + T3 angle +5°, T4 refracted fraction ×1.5 / range ×1.3 | T4 kept; T3 "a little wider" |
| 1.0.0-dev.4 | T3 → +8°, + T5 flare glow | All OK → released as 1.0.0 |

## Running a new round

1. Change **one lever group** in `tools/generate_headlights.py` (two at once only when you can tell
   their effects apart in-game) and add a `# Tn (<version>): ...` note above the levers.
2. Regenerate: `python tools/generate_headlights.py`. Check the printed key counts, and diff
   one file against upstream.
3. Bump `package_version` in `src/manifest.sii` to the next `-dev.N`, run
   `python tools/generate_cover.py`, and commit source and cover together.
4. Pack locally (`pack-mod`), playtest night + bad-weather day, and add a row to **History** above.
5. When a round is kept, update the **Rounds** table's lever and released columns.

Out of scope so far: side/clearance marker flares (Better Flares **base** `vehicle_orange*`,
`vehicle_redl*`, `vehicle_whitel*`, ...). Changing them would override base-pack files for all
vehicles and isn't DOT-specific.
