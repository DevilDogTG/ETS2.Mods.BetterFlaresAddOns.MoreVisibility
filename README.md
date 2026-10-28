# DriveDogs: Better Flares More Visibility (7500K LED)

An ETS2 add-on for **Better Flares v4.9 - Headlights.2 7500K LED** (by Avelium). Truck headlights spread
wider and the high beam reaches farther for more comfortable night driving, and the headlamp glow stays
readable in bad daytime conditions, while keeping Better Flares' realistic mood.

**Status: `2.0.0`.** Better Flares v4.9 only; 7500K LED only; any Headlights.1 pattern. `1.0.0` was for
Better Flares v4.8 and breaks on v4.9 (removed beam masks).

## Load order
Top = highest priority in Mod Manager:
1. DriveDogs: Better Flares More Visibility (7500K LED)
2. Better Flares - Headlights.2 7500K LED
3. Better Flares - Headlights.1 (any one)
4. Better Flares - City Lights Addon (optional)
5. Better Flares - Traffic Addon (optional)
6. Better Flares - Base

Headlights.1 and Headlights.2 are both required: every Headlights.1 truck def includes the
`def/vehicle/_common/color.sui` that only Headlights.2 ships.

## How it works
Better Flares v4.9 keeps every beam value for every truck in one file, Headlights.2's
`def/vehicle/_common/color.sui`; Headlights.1 truck defs only set masks and include it. ETS2 replaces whole files,
so this mod ships a complete copy of that file (and of the two headlight flare units) with only the tuned values
changed. Those files are **generated, not hand-edited**. See `docs/adr/ADR-0002-generate-from-v49-color.md`
(supersedes ADR-0001's v4.8 per-truck design).

`tools/generate_headlights.py` reads the extracted upstream pack and applies the tuning levers at the
top of the script:

| Lever (per beam stage: low / hi / front / roof / front_roof) | Field(s) |
|---|---|
| `color_mult` | `*_color`, `*_color_specular`, `*_color_ambient` |
| `range_mult` / `range_set` | `*_range` (relative / absolute) |
| `bias_add` | `*_bias` |
| `angle_add` / `angle_set` | `*_angle` (relative / absolute; aspect stays upstream, so vertical FOV scales too) |
| `refr_fraction_mult` | `*_refracted_color_fraction` |
| `refr_range_mult` | `*_refracted_range` |

| Lever (flare units `vehicle_headl`, `vehicle_high_beam`) | Field |
|---|---|
| `default_scale_mult` | `default_scale` |
| `scale_factor_mult` | `scale_factor` |
| `inner_angle_add` / `outer_angle_add` | `flare_inner_angle` / `flare_outer_angle` |

Released values, per-round (Tx) history and how to run a new tuning round: see
[`docs/tuning.md`](docs/tuning.md).

Aim (`*_rot`) and `aspect` are never touched. Only files a lever actually changes are written. The run fails if any
Headlights.1 def next to the base pack doesn't include `/def/vehicle/_common/color.sui` or names a mask the base
pack doesn't ship.

```
python tools/generate_headlights.py            # regenerate src/def + src/unit
python tools/generate_headlights.py --all --out <dir>   # identity round-trip check vs upstream
```
Defaults read `local/better-flares/4.9.1/bf_h2_7500K_led_v4.9.1` and `bf_base_v4.9.1` (with the `bf_h1_*` packs
next to it) under this host's extracted-reference root (`scs-mod-developer` host config); `--source` / `--base`
override.

## Building
Requires `scs_packer` (and `scs_extractor`, for verification) on `PATH`, and Python 3 with Pillow.
Packing runs `pack.config.json`'s `prePack` (`python tools/generate_cover.py`), which regenerates
`src/cover.jpg` with the `manifest.sii` version badge. Commit the regenerated cover with a version bump.

- **Local**: the `scs-mod-developer` profile's `pack-mod` skill → versioned `.scs` in `output/local/`.
- **Workshop**: `pack-mod` stages `output/workshop/` for the SCS Workshop Uploader.

## Updating for a new Better Flares release
1. Extract the new base, every Headlights.1 and the Headlights.2 7500K LED pack into the extracted-reference root.
2. Point the defaults (or `--source`/`--base`) at them and regenerate. A failed h1 check means Better Flares changed
   its design again.
3. Review `git diff src/`, playtest, bump the version.
