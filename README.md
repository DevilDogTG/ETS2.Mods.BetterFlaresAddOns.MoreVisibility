# DriveDogs: Better Flares More Visibility (DOT 7500K)

An ETS2 add-on for **Better Flares v4.8 - Headlights DOT 7500k** (by Avelium). Truck headlights reach
farther and spread wider for more comfortable night driving, and the road stays readable in bad
daytime conditions, while keeping Better Flares' realistic mood.

**Status: `1.0.0`.** Better Flares v4.8 only; DOT 7500k only.

## Load order
Top = highest priority in Mod Manager:
1. DriveDogs: Better Flares More Visibility (DOT 7500K)
2. Better Flares v4.8 - Headlights DOT 7500k
3. Better Flares v4.8 - Base

## How it works
ETS2 replaces whole files, so this mod ships complete copies of Better Flares' truck `head_light`
definitions (and, when tuned, the headlight flare units) with only the tuned values changed.
Those files are **generated, not hand-edited**. See `docs/adr/ADR-0001-generate-from-upstream-v48.md`.

`tools/generate_headlights.py` reads the extracted upstream pack and applies the tuning levers at the
top of the script:

| Lever (per beam stage: low / hi / front / roof / front_roof) | Field(s) |
|---|---|
| `color_mult` | `*_color`, `*_color_specular`, `*_color_ambient` |
| `range_mult` | `*_range` |
| `bias_add` | `*_bias` |
| `angle_add` | `*_angle` (aspect stays upstream, so vertical FOV scales too) |
| `refr_fraction_mult` | `*_refracted_color_fraction` |
| `refr_range_mult` | `*_refracted_range` |

| Lever (flare units `vehicle_headl`, `vehicle_high_beam`) | Field |
|---|---|
| `default_scale_mult` | `default_scale` |
| `scale_factor_mult` | `scale_factor` |
| `inner_angle_add` / `outer_angle_add` | `flare_inner_angle` / `flare_outer_angle` |

Released values, per-round (Tx) history and how to run a new tuning round: see
[`docs/tuning.md`](docs/tuning.md).

Aim (`*_rot`), `aspect` and masks are never touched. Only files a lever actually changes are
written, and the run fails if any written file references a mask the base pack doesn't ship.

```
python tools/generate_headlights.py            # regenerate src/def + src/unit
python tools/generate_headlights.py --all --out <dir>   # identity round-trip check vs upstream
```
Defaults expect the extracted references at
`D:\Repositories\ETS2\Mods\Extracted\local\better-flares\4.8\` (`--source` / `--base` override).

## Building
Requires `scs_packer` (and `scs_extractor`, for verification) on `PATH`, and Python 3 with Pillow.
Packing runs `pack.config.json`'s `prePack` (`python tools/generate_cover.py`), which regenerates
`src/cover.jpg` with the `manifest.sii` version badge. Commit the regenerated cover with a version bump.

- **Local**: the `scs-mod-developer` profile's `pack-mod` skill → versioned `.scs` in `output/local/`.
- **Workshop**: `pack-mod` stages `output/workshop/` for the SCS Workshop Uploader.

## Updating for a new Better Flares release
1. Extract the new base + DOT 7500k packs into the extracted-reference root.
2. Point `--source`/`--base` (or the defaults) at them and regenerate.
3. Review `git diff src/`, playtest, bump the version.
