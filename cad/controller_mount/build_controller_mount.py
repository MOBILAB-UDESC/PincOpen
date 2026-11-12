"""Build the Waveshare Bus Servo Adapter (A) mount for Pinc'Open.

Three parts hold the servo controller board on the outer face of Bottom_Plate:
  * Controller_Riser: a 15 deg wedge the board sits on. The connector edge
    (DC jack, screw terminal, USB-C) is raised and faces the arm, so the power
    plug leaves at an angle, away from the plate. A 3 mm pocket clears the
    through-hole pins; 4 pads with Ø2.1 pins locate the board by its Ø2.5 holes.
  * Controller_Cover: a U-shaped frame that clamps only the 4 board corners
    (0.2 mm interference). The connector edge, servo headers, UART header,
    jumpers and LED stay open.
  * Bottom_Plate_Controller: the original Bottom_Plate with 4 Ø4.0 through holes
    for 4 mm long M3 heat inserts (the floor there is 4 mm thick).
Riser and cover are clamped between the cover and the plate by 2x M3x12 (front)
and 2x M3x20 (back) socket head screws, each engaging 3 mm of insert.

Everything is in Bottom_Plate's frame (mm): the outer face is Z = -13, outward is
-Z, +X points to the jaws, the arm interface is at X = -53.5.

The parts are built with SolidCraft's command-line runner (solidcraft-cli, from
the SolidCraft AppImage). This script writes the command scripts and runs them.

Usage (from the repo root):
  python3 cad/controller_mount/build_controller_mount.py --cli /path/to/solidcraft-cli
  python3 cad/controller_mount/build_controller_mount.py --scripts-only   # write the JSON only
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = REPO / "cad/controller_mount"
PLATE_IN = REPO / "cad/step/Bottom_Plate.step"
OUT = {
    "plate": ("Bottom_Plate", "Bottom_Plate_Controller"),
    "riser": ("Riser", "Controller_Riser"),
    "cover": ("Cover", "Controller_Cover"),
}

# ---- board: Waveshare Bus Servo Adapter (A), 42 x 33 x 1.6 mm, Ø2.5 holes ----
BL, BW, BT = 33.0, 42.0, 1.6          # depth (along plate X), width (along Y), thickness
HOLES = [(2.5, 2.5), (2.5, 30.5), (39.5, 2.5), (39.5, 30.5)]   # board frame: x along BW, y along BL

# ---- layout ----
TH = 15.0                  # tilt, deg
XF = -10.0                 # board front edge (bottom face), plate X
H0 = 5.0                   # board bottom height above the plate at its front edge
Z0 = -13.0                 # plate outer face
RX0, RX1, RY = -43.0, -4.0, 28.0      # riser footprint: X from RX0 to RX1, Y +-RY
POCKET = 3.0               # clearance under the board for through-hole pins
PIN_D, PAD_R = 2.1, 2.75   # locating pins (board holes are Ø2.5) and support pads
COVER_T = 3.0
# screws: x, y, seat height of the head above the plate (M3x12 front, M3x20 back)
SCREWS = [(-7.5, 24.5, 9.0), (-7.5, -24.5, 9.0), (-38.5, 24.5, 17.0), (-38.5, -24.5, 17.0)]
INSERT_D = 4.0             # heat insert hole, through the 4 mm floor
CLEAR_D, HEAD_D, BOSS_D = 3.5, 6.2, 6.0

s, c, t = (f(math.radians(TH)) for f in (math.sin, math.cos, math.tan))
XB = XF - BL * c                                   # board back edge (connector side)
B = lambda x: H0 + (XF - x) * t                    # board bottom, height above the plate
T = lambda x: B(x) + BT / c                        # board top
EAR = lambda x: B(x) + (BT - 0.2) / c              # riser top beside the board: 0.2 below -> clamp
F = lambda x: B(x) - POCKET / c                    # pocket floor
wz = lambda h: Z0 - h                              # height above the plate -> world Z
BX, BY, BN = [0, 1, 0], [c, 0, s], [s, 0, -c]      # board x, board y, board normal (outward)
BOARD_O = [XB, -BW / 2, wz(B(XB))]                 # board corner (0, 0), bottom face
TOP_O = [BOARD_O[i] + BT * BN[i] for i in range(3)]
SIDE = {"origin": [0, 0, Z0], "x_dir": [1, 0, 0], "y_dir": [0, 0, -1]}   # sketch y = height


def on_plane(o, bx, by, h):
    return [o[i] + bx * BX[i] + by * BY[i] + h * BN[i] for i in range(3)]


def parts_script(out_dir: Path) -> list[dict]:
    cmds: list[dict] = []
    add = lambda cmd, **p: cmds.append({"command": cmd, "params": p})

    # Riser: wedge, board pocket, rounded corners, support pads, locating pins
    add("sketch.create", plane=SIDE, name="Riser_profile")
    add("sketch.line", points=[[RX1, 0], [RX1, EAR(RX1)], [RX0, EAR(RX0)], [RX0, 0]], closed=True)
    add("sketch.finish")
    add("solid.extrude", distance=2 * RY, direction="symmetric", operation="new", name="Riser_block")
    add("body.rename", body="Body1", name="Riser")
    px0, px1 = RX0 - 0.5, -9.0
    add("sketch.create", plane=SIDE, name="Pocket_profile")
    add("sketch.line", points=[[px0, F(px0)], [px1, F(px1)], [px1, 40], [px0, 40]], closed=True)
    add("sketch.finish")
    add("solid.extrude", distance=BW + 1.0, direction="symmetric", operation="cut", name="Board_pocket")
    add("solid.fillet", edges=[[RX1, RY, wz(EAR(RX1) / 2)], [RX1, -RY, wz(EAR(RX1) / 2)],
                               [RX0, RY, wz(EAR(RX0) / 2)], [RX0, -RY, wz(EAR(RX0) / 2)]],
        radius=3, name="Riser_corners")
    zin = wz((F(px1) + EAR(px1)) / 2)
    add("solid.fillet", edges=[[px1, 21.5, zin], [px1, -21.5, zin]], radius=0.8, name="Pocket_corners")
    bplane = {"origin": BOARD_O, "x_dir": BX, "y_dir": BY}
    add("sketch.create", plane=bplane, name="Pads_sketch")
    for h in HOLES:
        add("sketch.circle.center", center=list(h), radius=PAD_R)
    add("sketch.finish")
    add("solid.extrude", distance=POCKET + 0.3, direction="negative", operation="join", name="Pads")
    add("sketch.create", plane=bplane, name="Pins_sketch")
    for h in HOLES:
        add("sketch.circle.center", center=list(h), radius=PIN_D / 2)
    add("sketch.finish")
    add("solid.extrude", distance=1.3, direction="positive", operation="join", name="Pins")

    # Cover: U-shaped frame in the board-top plane, rounded outline and top rim
    by0 = (RX0 - TOP_O[0]) / c + 0.05
    by1 = (RX1 - TOP_O[0]) / c - 0.05
    bxl, bxr, il, ir = BW / 2 - RY, BW / 2 + RY, -0.3, BW + 0.3
    pts = [[bxl, by0], [4.6, by0], [4.6, 5.0], [il, 5.0], [il, 28.0], [5.0, 28.0], [5.0, 34.0],
           [37.8, 34.0], [37.8, 28.0], [ir, 28.0], [ir, 5.0], [37.4, 5.0], [37.4, by0], [bxr, by0],
           [bxr, by1], [bxl, by1]]
    radii = {0: 3, 13: 3, 14: 3, 15: 3, 1: 1.5, 2: 1.5, 5: 1.5, 8: 1.5, 11: 1.5, 12: 1.5,
             3: 2, 4: 2, 9: 2, 10: 2, 6: 1.5, 7: 1.5}   # corner k joins line k and k+1
    add("sketch.create", plane={"origin": TOP_O, "x_dir": BX, "y_dir": BY}, name="Cover_sketch")
    add("sketch.line", points=pts, closed=True)
    for k, r in sorted(radii.items()):
        add("sketch.fillet", a=f"l{k}" if k else f"l{len(pts)}", b=f"l{k + 1}", radius=r)
    add("sketch.finish")
    add("solid.extrude", distance=COVER_T, direction="positive", operation="new", name="Cover_plate")
    add("body.rename", body="Body2", name="Cover")
    add("solid.fillet", edges=[on_plane(TOP_O, bxl, 20, COVER_T)], radius=0.8, name="Cover_rim")

    # Screws: flat head seats on the cover, clearance holes through cover and riser
    for i, (x, y, seat) in enumerate(SCREWS, 1):
        add("solid.cylinder", diameter=BOSS_D, height=seat - T(x - BOSS_D / 2), base=[x, y, wz(seat)],
            operation="join", targets=["Cover"], name=f"Seat_{i}")
        add("solid.cylinder", diameter=HEAD_D, height=20, base=[x, y, wz(seat + 20)],
            operation="cut", targets=["Cover"], name=f"Counterbore_{i}")
        add("solid.cylinder", diameter=CLEAR_D, height=40, base=[x, y, wz(40)],
            operation="cut", targets=["Cover", "Riser"], name=f"M3_clearance_{i}")
    for key in ("riser", "cover"):
        body, name = OUT[key]
        add("file.export_step", path=str(out_dir / "step" / f"{name}.step"), bodies=[body])
        add("file.export_stl", path=str(out_dir / "stl" / f"{name}.stl"), bodies=[body])
    return cmds


def plate_script(out_dir: Path) -> list[dict]:
    cmds = [{"command": "solid.cylinder", "params": {
        "diameter": INSERT_D, "height": 5.0, "base": [x, y, Z0 - 0.5], "operation": "cut",
        "targets": ["Bottom_Plate"], "name": f"Heat_insert_M3_{i}"}}
        for i, (x, y, _) in enumerate(SCREWS, 1)]
    body, name = OUT["plate"]
    cmds.append({"command": "file.export_step", "params": {"path": str(out_dir / "step" / f"{name}.step"), "bodies": [body]}})
    cmds.append({"command": "file.export_stl", "params": {"path": str(out_dir / "stl" / f"{name}.stl"), "bodies": [body]}})
    return cmds


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cli", default=os.environ.get("SOLIDCRAFT_CLI") or shutil.which("solidcraft-cli"),
                    help="path to solidcraft-cli (default: $SOLIDCRAFT_CLI or PATH)")
    ap.add_argument("--scripts-only", action="store_true", help="write the SolidCraft scripts and stop")
    args = ap.parse_args()

    out_dir = REPO / "cad"
    scripts = {"parts": parts_script(out_dir), "plate": plate_script(out_dir)}
    for key, cmds in scripts.items():
        (HERE / f"{key}_script.json").write_text(json.dumps({"commands": cmds}, indent=1) + "\n")
    if args.scripts_only:
        return
    if not args.cli:
        raise SystemExit("solidcraft-cli not found: pass --cli or set SOLIDCRAFT_CLI")
    subprocess.run([args.cli, "run", str(HERE / "parts_script.json"), "--quiet",
                    "--save", str(HERE / "controller_mount.sc")], check=True)
    subprocess.run([args.cli, "run", str(HERE / "plate_script.json"), "--in", str(PLATE_IN), "--quiet"], check=True)


if __name__ == "__main__":
    main()
