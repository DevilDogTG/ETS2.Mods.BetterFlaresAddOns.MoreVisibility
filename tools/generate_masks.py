#!/usr/bin/env python3
"""
Generates sharper-cutoff copies of Better Flares v4.9's low-beam masks.

Source:  <--base>/material/custom/bf_<pattern>_norm.{dds,tobj}   (Better Flares Base)
Output:  src/material/custom/ at the same names, so this add-on (loaded above
         Better Flares Base) replaces them for every Headlights.1 pattern.

Each mask is a 1024x512 BGRX texture: the lit pool under a cutoff line near the
centre row, with a soft glow above it. Two edits, in this order:

1. Left lift. Better Flares' cutoff left of the centre step sits 4-9 rows lower than
   right of it; at ~1 m lamp height and -0.55 deg aim that halves the left side's reach
   on the road. Left of the step, each column's cutoff (its 50% row) is raised to at
   most LEFT_LIFT_GAP rows below the right side's level, by at most LEFT_LIFT_CAP rows,
   by shifting the column up. The target is monotonic, so the step keeps its shape.
2. Edge gamma. Above each column's brightest row, pixels dimmer than EDGE_PROTECT of
   the column's peak are scaled by (brightness / (EDGE_PROTECT * peak)) ** (EDGE_GAMMA - 1):
   the faint glow over the cutoff fades out faster, the beam itself is untouched.

The .tobj is copied unchanged. Output is gitignored and regenerated at prePack.
Re-run after every Better Flares update.
"""
import argparse
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT_ROOT = ROOT / "src"

sys.path.insert(0, str(Path.home() / ".agent-brains/profiles/scs-mod-developer/skills/megapack/scripts"))
from megapack import reference_root, repo_game  # noqa: E402

DEFAULT_BASE = reference_root(repo_game(ROOT)) / "local" / "better-flares" / "4.9.1" / "bf_base_v4.9.1"
MASK_DIR = "material/custom"
PATTERNS = ("proj_dot1", "proj_dot2", "proj_dot3", "proj_ece1", "refl_dot1", "refl_ece1")
OWNED_DIRS = ("material",)

# --- Levers ------------------------------------------------------------------
LEFT_LIFT_GAP = 2      # rows the left cutoff stays below the right side's level (None = no lift)
LEFT_LIFT_CAP = 10     # max rows a column is raised (0.9 deg at 103 deg / aspect 2.289)
EDGE_GAMMA = 2.0       # 1.0 = upstream; 2.0 halves a glow at 25% of the peak, 10% -> 2%
EDGE_PROTECT = 0.5     # pixels at or above this fraction of the column peak are never dimmed

# The right side's level is the median 50% row over RIGHT_LEVEL_X: right of the step and of the
# ECE shoulder, in all six patterns. The lift ends at the first column from STEP_SEARCH_X whose
# cutoff already reaches the target (the step), so nothing right of it moves.
RIGHT_LEVEL_X = (580, 680)
STEP_SEARCH_X = 440

HEADER = 148           # DDS + DX10 header
W, H, FORMAT = 1024, 512, 93   # DXGI_FORMAT_B8G8R8X8_UNORM_SRGB


def read_dds(path):
    b = path.read_bytes()
    if b[:4] != b"DDS " or b[84:88] != b"DX10":
        raise SystemExit(f"{path}: not a DX10 DDS")
    h, w = int.from_bytes(b[12:16], "little"), int.from_bytes(b[16:20], "little")
    fmt = int.from_bytes(b[128:132], "little")
    if (w, h, fmt) != (W, H, FORMAT) or len(b) != HEADER + W * H * 4:
        raise SystemExit(f"{path}: expected {W}x{H} format {FORMAT} without mips, got {w}x{h} format {fmt}, "
                         f"{len(b)} bytes - Better Flares changed its masks, update this tool")
    return b[:HEADER], np.frombuffer(b[HEADER:], np.uint8).reshape(H, W, 4).astype(np.float64)


def box(a, n):
    p = np.pad(a, n // 2, mode="edge")
    return np.convolve(p, np.ones(n) / n, mode="valid")[: len(a)]


def cut_rows(px):
    """Per column: the first row from the top reaching 50% of the column's peak."""
    lum = px[:, :, :3].max(axis=2)
    peak = lum.max(axis=0)
    return np.argmax(lum >= 0.5 * peak[None, :], axis=0).astype(np.float64), peak


def lift_left(px, gap, cap):
    c, peak = cut_rows(px)
    c = box(c, 9)
    right = float(np.median(c[RIGHT_LEVEL_X[0]:RIGHT_LEVEL_X[1]]))
    target = right + gap
    reached = np.nonzero(c[STEP_SEARCH_X:] <= target)[0]
    step = STEP_SEARCH_X + (int(reached[0]) if len(reached) else W // 2)
    s = np.clip(c - target, 0, cap)
    s[step:] = 0
    s *= np.clip((peak / peak.max() - 0.05) / 0.15, 0, 1)    # fade out on the dim outer columns
    # Smooth, but never lift a column less than it needs: a smoothed-down ramp would leave a
    # notch just left of the step.
    s = np.maximum(s, box(s, 21))
    s[step:] = 0
    out = px.copy()
    rows = np.arange(H, dtype=np.float64)
    for x in np.nonzero(s > 0.01)[0]:
        src = np.clip(rows + s[x], 0, H - 1)                  # shift the column up by s rows
        for ch in range(4):
            out[:, x, ch] = np.interp(src, rows, px[:, x, ch])
    return out, right, s


def sharpen(px, gamma, protect):
    lum = px[:, :, :3].max(axis=2)
    peak_row = lum.argmax(axis=0)
    peak = lum.max(axis=0)
    t = np.divide(lum, protect * peak, out=np.zeros_like(lum), where=peak > 0)
    above = np.arange(H)[:, None] < peak_row[None, :]
    scale = np.where(above, np.power(np.minimum(t, 1.0), gamma - 1.0), 1.0)
    return px * scale[:, :, None]


def edge_height(px):
    lum = px[:, :, :3].max(axis=2)
    hs = []
    for x in (256, 400, 512, 624, 768):
        col = lum[:, x]
        hs.append(int(np.argmax(col >= 0.9 * col.max()) - np.argmax(col >= 0.1 * col.max())))
    return hs


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", type=Path, default=DEFAULT_BASE, help="extracted Better Flares v4.9 base pack")
    ap.add_argument("--out", type=Path, default=OUT_ROOT)
    ap.add_argument("--gamma", type=float, default=EDGE_GAMMA)
    args = ap.parse_args()

    outputs = {}
    for pat in PATTERNS:
        name = f"bf_{pat}_norm"
        dds, tobj = args.base / MASK_DIR / f"{name}.dds", args.base / MASK_DIR / f"{name}.tobj"
        if not dds.exists() or not tobj.exists():
            raise SystemExit(f"Missing {dds} or {tobj}")
        header, px = read_dds(dds)
        new = px
        if LEFT_LIFT_GAP is not None:
            new, right, s = lift_left(new, LEFT_LIFT_GAP, LEFT_LIFT_CAP)
            print(f"{name}: right level row {right:.0f}, left lift rows at x=200/300/400/470/500 "
                  f"{[round(float(s[x]), 1) for x in (200, 300, 400, 470, 500)]}")
        new = sharpen(new, args.gamma, EDGE_PROTECT)
        outputs[f"{MASK_DIR}/{name}.dds"] = header + np.clip(np.rint(new), 0, 255).astype(np.uint8).tobytes()
        outputs[f"{MASK_DIR}/{name}.tobj"] = tobj
        print(f"{name}: 10-90% edge px at x=256/400/512/624/768 {edge_height(px)} -> {edge_height(new)}")

    removed = 0
    for owned in OWNED_DIRS:
        for stale in sorted((args.out / owned).rglob("*")):
            if stale.is_file() and stale.relative_to(args.out).as_posix() not in outputs:
                stale.unlink()
                removed += 1
        for d in sorted((args.out / owned).rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
    for rel, data in outputs.items():
        path = args.out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, Path):
            shutil.copyfile(data, path)
        else:
            path.write_bytes(data)
    if removed:
        print(f"removed {removed} stale file(s)")
    print(f"Wrote {len(outputs)} files under {args.out / MASK_DIR} (gamma {args.gamma})")


if __name__ == "__main__":
    main()
