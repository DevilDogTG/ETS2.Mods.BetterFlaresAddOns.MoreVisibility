#!/usr/bin/env python3
"""
Generates the add-on's head_light and flare-unit files from the upstream
Better Flares v4.8 DOT 7500k pack by applying the tuning levers below.

Source:  <--source>/def/vehicle/truck/*/head_light/*.sii
         <--source>/unit/hookup/vehicle/flare/{vehicle_headl,vehicle_high_beam}.sii
Output:  src/ at the same relative paths

ETS2 replaces whole files, so an output file carries every upstream value;
only lever-targeted values change. Lines are edited in place (value token
only), so aim, aspect, masks, comments and line endings stay byte-for-byte
upstream. A file the levers leave unchanged is not emitted at all, so the
add-on never overrides upstream without a reason. Re-run after every Better
Flares update.
"""
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_ROOT = ROOT / "src"

EXTRACTED = Path(r"D:\Repositories\ETS2\Mods\Extracted\local\better-flares\4.8")
DEFAULT_SOURCE = EXTRACTED / "better_flares_v4.8_dot_7500"
DEFAULT_BASE = EXTRACTED / "better_flares_v4.8_base"

HEAD_LIGHT_GLOB = "def/vehicle/truck/*/head_light/*.sii"
FLARE_DIR = "unit/hookup/vehicle/flare"
FLARE_FILES = ("vehicle_headl.sii", "vehicle_high_beam.sii")
# Directories this script owns in src/ - stale files in them are removed.
OWNED_DIRS = ("def/vehicle/truck", FLARE_DIR)

# --- Tuning levers ---------------------------------------------------------
# Identity values (mult 1.0, add 0.0) leave upstream untouched. Tune one
# lever group at a time; log every build in the plan's tuning log.
#   color_mult          color, color_specular, color_ambient (light intensity)
#   range_mult          range (reach)
#   bias_add            bias (undocumented; tuned empirically)
#   angle_add           angle in degrees (width; aspect stays 3.0, so the
#                       vertical FOV widens by the same ratio)
#   refr_fraction_mult  refracted_color_fraction (near-field spill)
#   refr_range_mult     refracted_range
IDENTITY_STAGE = dict(color_mult=1.0, range_mult=1.0, bias_add=0.0, angle_add=0.0,
                      refr_fraction_mult=1.0, refr_range_mult=1.0)

STAGE_LEVERS = {
    "low_beam": dict(IDENTITY_STAGE),
    "hi_beam": dict(IDENTITY_STAGE),
    "front_beam": dict(IDENTITY_STAGE),
    "roof_beam": dict(IDENTITY_STAGE),
    "front_roof_beam": dict(IDENTITY_STAGE),
}

#   default_scale_mult  flare sprite size up close
#   scale_factor_mult   flare sprite growth with distance
#   inner_angle_add     flare_inner_angle, full-visibility cone (degrees)
#   outer_angle_add     flare_outer_angle, fade-out cone (degrees)
IDENTITY_FLARE = dict(default_scale_mult=1.0, scale_factor_mult=1.0,
                      inner_angle_add=0.0, outer_angle_add=0.0)

FLARE_LEVERS = {
    "vehicle_headl.sii": dict(IDENTITY_FLARE),
    "vehicle_high_beam.sii": dict(IDENTITY_FLARE),
}
# ---------------------------------------------------------------------------

# Longest stage first so "front_roof_beam_x" never parses as "front_beam".
STAGE_KEY_RE = re.compile(r"^(front_roof_beam|front_beam|roof_beam|low_beam|hi_beam)_(\w+)$")
LINE_RE = re.compile(r"^(\s*)(\w+)(\s*:\s*)([^#\r\n]*?)(\s*(?:#[^\r\n]*)?\r?\n?)$")
NUM_RE = re.compile(r"[-+]?\d*\.?\d+")
MASK_RE = re.compile(r'^\s*\w+_mask\s*:\s*"([^"]+)"', re.MULTILINE)


def fmt(value, template):
    """Format like the upstream token: keep at least its decimal places,
    add more only when the new value needs them (max 6)."""
    decimals = len(template.split(".")[1]) if "." in template else 0
    text = f"{round(value, 6):.6f}".rstrip("0").rstrip(".")
    have = len(text.split(".")[1]) if "." in text else 0
    if have < decimals:
        text = f"{value:.{decimals}f}"
    return text


def apply(value_text, op, amount):
    """Apply mult/add to every number in a scalar or '(r, g, b)' value."""
    def repl(m):
        v = float(m.group(0))
        return fmt(v * amount if op == "mult" else v + amount, m.group(0))
    return NUM_RE.sub(repl, value_text)


def head_light_rule(key):
    m = STAGE_KEY_RE.match(key)
    if not m:
        return None
    lv = STAGE_LEVERS[m.group(1)]
    return {
        "color": ("mult", lv["color_mult"]),
        "color_specular": ("mult", lv["color_mult"]),
        "color_ambient": ("mult", lv["color_mult"]),
        "range": ("mult", lv["range_mult"]),
        "bias": ("add", lv["bias_add"]),
        "angle": ("add", lv["angle_add"]),
        "refracted_color_fraction": ("mult", lv["refr_fraction_mult"]),
        "refracted_range": ("mult", lv["refr_range_mult"]),
    }.get(m.group(2))


def flare_rule_for(filename):
    lv = FLARE_LEVERS[filename]
    rules = {
        "default_scale": ("mult", lv["default_scale_mult"]),
        "scale_factor": ("mult", lv["scale_factor_mult"]),
        "flare_inner_angle": ("add", lv["inner_angle_add"]),
        "flare_outer_angle": ("add", lv["outer_angle_add"]),
    }
    return rules.get


def transform(text, rule_for, changed_keys):
    out = []
    for line in text.splitlines(keepends=True):
        m = LINE_RE.match(line)
        rule = rule_for(m.group(2)) if m else None
        if rule and rule not in (("mult", 1.0), ("add", 0.0)):
            new_value = apply(m.group(4), *rule)
            if new_value != m.group(4):
                changed_keys[m.group(2)] += 1
                line = m.group(1) + m.group(2) + m.group(3) + new_value + m.group(5)
        out.append(line)
    return "".join(out)


def check_masks(outputs, base):
    """Guard against v0.1.0's failure: a mask path the base pack doesn't ship."""
    if not base.exists():
        print(f"warning: base pack not found, mask check skipped: {base}", file=sys.stderr)
        return
    missing = Counter()
    for text in outputs.values():
        for path in MASK_RE.findall(text):
            if not (base / path.lstrip("/")).exists():
                missing[path] += 1
    if missing:
        for path, n in missing.items():
            print(f"error: {n} file(s) reference missing mask {path}", file=sys.stderr)
        raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                    help="extracted Better Flares v4.8 dot_7500 pack")
    ap.add_argument("--base", type=Path, default=DEFAULT_BASE,
                    help="extracted Better Flares v4.8 base pack (mask check)")
    ap.add_argument("--out", type=Path, default=OUT_ROOT)
    ap.add_argument("--all", action="store_true",
                    help="emit unchanged files too (identity round-trip check)")
    args = ap.parse_args()

    head_lights = sorted(args.source.glob(HEAD_LIGHT_GLOB))
    if not head_lights:
        raise SystemExit(f"No head_light files under {args.source}")
    jobs = [(f, head_light_rule) for f in head_lights]
    for name in FLARE_FILES:
        f = args.source / FLARE_DIR / name
        if not f.exists():
            raise SystemExit(f"Missing flare unit {f}")
        jobs.append((f, flare_rule_for(name)))

    changed_keys = Counter()
    outputs = {}
    for f, rule_for in jobs:
        # newline="" keeps upstream CRLF/LF exactly.
        text = f.read_text(encoding="utf-8", newline="")
        new = transform(text, rule_for, changed_keys)
        if new != text or args.all:
            outputs[f.relative_to(args.source).as_posix()] = new

    check_masks(outputs, args.base)

    for owned in OWNED_DIRS:
        for stale in sorted((args.out / owned).rglob("*")):
            if stale.is_file() and stale.relative_to(args.out).as_posix() not in outputs:
                stale.unlink()
                print(f"removed stale {stale.relative_to(args.out).as_posix()}")
        # Deepest first, so emptied parents go too; keeps empty dirs out of the pack.
        for d in sorted((args.out / owned).rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
    for rel, text in outputs.items():
        path = args.out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="")

    print(f"Wrote {len(outputs)} of {len(jobs)} files under {args.out}")
    for key, n in sorted(changed_keys.items()):
        print(f"  {key}: {n}")


if __name__ == "__main__":
    main()
