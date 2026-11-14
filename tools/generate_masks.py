#!/usr/bin/env python3
"""
Generates sharper-cutoff copies of Better Flares v4.9's low-beam masks.

Source:  <--base>/material/custom/bf_<pattern>_norm.{dds,tobj}   (Better Flares Base)
Output:  src/material/custom/ at the same names, so this add-on (loaded above
         Better Flares Base) replaces them for every Headlights.1 pattern.

Each mask is a 1024x512 BGRX texture: the lit pool under a cutoff line near the
centre row, with a soft glow above it. Per column, every pixel above the column's
brightest row is scaled by (its brightness / the column's peak) ** (EDGE_GAMMA - 1):
the faint glow over the cutoff fades out faster, while pixels near the peak barely
change. Nothing moves, so the cutoff line and Better Flares' step and kink shapes
stay exactly where they are; the transition into the dark just gets shorter.

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
EDGE_GAMMA = 2.0       # 1.0 = upstream; 2.0 turns a 50% glow into 25%, 10% into 1%

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


def sharpen(px, gamma):
    lum = px[:, :, :3].max(axis=2)
    peak_row = lum.argmax(axis=0)
    peak = lum.max(axis=0)
    t = np.divide(lum, peak, out=np.zeros_like(lum), where=peak > 0)
    above = np.arange(H)[:, None] < peak_row[None, :]
    scale = np.where(above, np.power(t, gamma - 1.0), 1.0)
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
        new = sharpen(px, args.gamma)
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
