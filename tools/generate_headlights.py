#!/usr/bin/env python3
"""
Generates the add-on's beam and flare-unit files from the upstream
Better Flares v4.9 Headlights.2 7500K LED pack by applying the tuning levers below.

Source:  <--source>/def/vehicle/_common/color.sui
         <--source>/unit/hookup/vehicle/flare/{vehicle_headl,vehicle_high_beam}.sii
Output:  src/ at the same relative paths

Better Flares v4.9 splits headlights in two packs: every Headlights.1 truck def
(beam pattern) sets only its masks and includes /def/vehicle/_common/color.sui,
which Headlights.2 (colour) ships with every beam value for every truck. So this
add-on overrides that one file and works with any Headlights.1 pattern.

ETS2 replaces whole files, so an output file carries every upstream value;
only lever-targeted values change. Lines are edited in place (value token
only), so aim, aspect, comments and line endings stay byte-for-byte
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

# This host's extracted-reference root for this repo's game, from the scs-mod-developer host config.
sys.path.insert(0, str(Path.home() / ".agent-brains/profiles/scs-mod-developer/skills/megapack/scripts"))
from megapack import reference_root, repo_game  # noqa: E402

EXTRACTED = reference_root(repo_game(ROOT)) / "local" / "better-flares" / "4.9.1"
DEFAULT_SOURCE = EXTRACTED / "bf_h2_7500K_led_v4.9.1"
DEFAULT_BASE = EXTRACTED / "bf_base_v4.9.1"
H1_GLOB = "bf_h1_*"   # Headlights.1 packs, next to the base pack

COLOR_FILE = "def/vehicle/_common/color.sui"
H1_DEF_GLOB = "def/vehicle/*/*/head_light/*.sii"
FLARE_DIR = "unit/hookup/vehicle/flare"
FLARE_FILES = ("vehicle_headl.sii", "vehicle_high_beam.sii")
# Directories this script owns in src/ - stale files in them are removed
# (def/vehicle also clears the 1.x per-truck defs).
OWNED_DIRS = ("def/vehicle", FLARE_DIR)

# --- Tuning levers ---------------------------------------------------------
# Identity values (mult 1.0, add 0.0, set None) leave upstream untouched. Tune
# one lever group at a time; log every build in docs/tuning.md.
#   color_mult          color, color_specular, color_ambient (light intensity)
#   range_mult          range (reach)
#   range_set           range, absolute (used instead of range_mult)
#   bias_add            bias (undocumented; tuned empirically)
#   angle_add           angle in degrees (width; aspect is left alone, so the
#                       vertical FOV widens by the same ratio)
#   angle_set           angle, absolute (used instead of angle_add)
#   refr_fraction_mult  refracted_color_fraction (near-field spill)
#   refr_range_mult     refracted_range
IDENTITY_STAGE = dict(color_mult=1.0, range_mult=1.0, range_set=None, bias_add=0.0,
                      angle_add=0.0, angle_set=None, refr_fraction_mult=1.0, refr_range_mult=1.0)

# 2.0.0 on Better Flares v4.9 (user, 2026-10-28): brightness, low-beam and roof reach,
# near-field spill, bias, aim and aspect stay Better Flares'. Kept from 1.0.0 as
# absolutes: the wider beam (103 deg on every stage; v4.9 is 90) and the longer high
# beam and front aux lamps (280; v4.9 is 240 / 260). The 1.x levers were relative to
# v4.8, whose baseline v4.9 already exceeds (rounds in docs/tuning.md).
STAGE_LEVERS = {
    "low_beam": dict(IDENTITY_STAGE, angle_set=103.0),
    "hi_beam": dict(IDENTITY_STAGE, angle_set=103.0, range_set=280.0),
    "front_beam": dict(IDENTITY_STAGE, angle_set=103.0, range_set=280.0),
    "roof_beam": dict(IDENTITY_STAGE, angle_set=103.0),
    "front_roof_beam": dict(IDENTITY_STAGE, angle_set=103.0),
}

#   default_scale_mult  flare sprite size up close
#   scale_factor_mult   flare sprite growth with distance
#   inner_angle_add     flare_inner_angle, full-visibility cone (degrees)
#   outer_angle_add     flare_outer_angle, fade-out cone (degrees)
IDENTITY_FLARE = dict(default_scale_mult=1.0, scale_factor_mult=1.0,
                      inner_angle_add=0.0, outer_angle_add=0.0)

# T5 (1.0.0-dev.4): lamp glow - moderate sprite growth, cones +10 deg. Kept for
# 2.0.0, now on top of Headlights.2 7500K's own flare units.
FLARE_LEVERS = {
    "vehicle_headl.sii": dict(IDENTITY_FLARE, default_scale_mult=1.15, scale_factor_mult=1.1,
                  inner_angle_add=10.0, outer_angle_add=10.0),
    "vehicle_high_beam.sii": dict(IDENTITY_FLARE, default_scale_mult=1.15, scale_factor_mult=1.1,
                  inner_angle_add=10.0, outer_angle_add=10.0),
}
# ---------------------------------------------------------------------------

# Longest stage first so "front_roof_beam_x" never parses as "front_beam".
STAGE_KEY_RE = re.compile(r"^(front_roof_beam|front_beam|roof_beam|low_beam|hi_beam)_(\w+)$")
LINE_RE = re.compile(r"^(\s*)(\w+)(\s*:\s*)([^#\r\n]*?)(\s*(?:#[^\r\n]*)?\r?\n?)$")
NUM_RE = re.compile(r"[-+]?\d*\.?\d+")
MASK_RE = re.compile(r'^\s*\w+_mask\s*:\s*"([^"]+)"', re.MULTILINE)
INCLUDE_RE = re.compile(r'^\s*@include\s+"([^"]+)"', re.MULTILINE)
IDENTITY_RULES = (("mult", 1.0), ("add", 0.0), ("set", None))


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
    """Apply mult/add/set to every number in a scalar or '(r, g, b)' value."""
    def repl(m):
        v = float(m.group(0))
        new = {"mult": v * amount, "add": v + amount, "set": amount}[op]
        return fmt(new, m.group(0))
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
        "range": ("set", lv["range_set"]) if lv["range_set"] is not None else ("mult", lv["range_mult"]),
        "bias": ("add", lv["bias_add"]),
        "angle": ("set", lv["angle_set"]) if lv["angle_set"] is not None else ("add", lv["angle_add"]),
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
        if rule and rule not in IDENTITY_RULES:
            new_value = apply(m.group(4), *rule)
            if new_value != m.group(4):
                changed_keys[m.group(2)] += 1
                line = m.group(1) + m.group(2) + m.group(3) + new_value + m.group(5)
        out.append(line)
    return "".join(out)


def check_h1(base):
    """Guard the half this add-on doesn't ship: every Headlights.1 def must include
    the file we override (else our values never reach it) and name only masks the
    base pack ships (v0.1.0 and 1.0.0 broke on masks a Better Flares update removed)."""
    packs = sorted(p for p in base.parent.glob(H1_GLOB) if p.is_dir())
    if not base.exists() or not packs:
        print(f"warning: base or Headlights.1 packs not found next to {base}, h1 check skipped",
              file=sys.stderr)
        return
    errors = Counter()
    defs = 0
    for pack in packs:
        for f in pack.glob(H1_DEF_GLOB):
            defs += 1
            text = f.read_text(encoding="utf-8", errors="replace")
            if "/" + COLOR_FILE not in INCLUDE_RE.findall(text):
                errors[f"{pack.name}: def without @include /{COLOR_FILE}"] += 1
            for path in MASK_RE.findall(text):
                if not (base / path.lstrip("/")).exists():
                    errors[f"{pack.name}: missing mask {path}"] += 1
    for what, n in errors.items():
        print(f"error: {n} file(s): {what}", file=sys.stderr)
    if errors:
        raise SystemExit(1)
    print(f"h1 check OK: {defs} defs in {len(packs)} Headlights.1 packs")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                    help="extracted Better Flares v4.9 Headlights.2 7500K LED pack")
    ap.add_argument("--base", type=Path, default=DEFAULT_BASE,
                    help="extracted Better Flares v4.9 base pack; Headlights.1 packs are "
                         "found next to it (include/mask check)")
    ap.add_argument("--out", type=Path, default=OUT_ROOT)
    ap.add_argument("--all", action="store_true",
                    help="emit unchanged files too (identity round-trip check)")
    args = ap.parse_args()

    color = args.source / COLOR_FILE
    if not color.exists():
        raise SystemExit(f"Missing {color}")
    jobs = [(color, head_light_rule)]
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

    check_h1(args.base)

    removed = 0
    for owned in OWNED_DIRS:
        for stale in sorted((args.out / owned).rglob("*")):
            if stale.is_file() and stale.relative_to(args.out).as_posix() not in outputs:
                stale.unlink()
                removed += 1
        # Deepest first, so emptied parents go too; keeps empty dirs out of the pack.
        for d in sorted((args.out / owned).rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
    for rel, text in outputs.items():
        path = args.out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="")

    if removed:
        print(f"removed {removed} stale file(s)")
    print(f"Wrote {len(outputs)} of {len(jobs)} files under {args.out}")
    for key, n in sorted(changed_keys.items()):
        print(f"  {key}: {n}")


if __name__ == "__main__":
    main()
