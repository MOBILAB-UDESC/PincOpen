# PincOpen as a Dex1 gripper on a Unitree G1

How to run the PincOpen on a G1 so that Unitree's Dex1 software, in particular
[xr_teleoperate](https://github.com/MOBILAB-UDESC/xr_teleoperate) with `--ee dex1`, drives it over the
robot's own DDS. Written from the first setup on `g1-al39` (November 2026); every step can be re-run on
another robot.

```
PICO controller ──Wi-Fi──► xr_teleoperate (robot PC2, --ee dex1 --input-mode controller)
                               │ rt/dex1/right/cmd    (unitree_go MotorCmds_, q 0..5.4 rad)
                               ▼ DDS, domain 0, eth0
                          pincopen_dex1_server.py (robot PC2, conda env tv)
                               │ USB serial /dev/ttyACM0, 1 Mbit/s
                               ▼
                          Feetech/Waveshare bus adapter ── STS3215 (12 V) ── PincOpen
                               ▲ 12 V XT30 from the G1 side panel
```

Mechanics and wiring: [g1_wrist_interface.md](g1_wrist_interface.md). Bridge details:
[../dex1_bridge/README.md](../dex1_bridge/README.md).

## What you need

- **Laptop**: MOBILAB's `mobilab-g1-teleop` checked out (not published yet), with its `xr_teleoperate`
  submodule (MOBILAB's fork), and `brew install gum`. This repo, with `.venv-dex1` set up as in the
  [README](../README.md#use-it-as-a-unitree-dex1-gripper).
- **Robot**: a G1 with its development computer (PC2, Jetson, Ubuntu 20.04) on the lab Wi-Fi, and the
  robot password once.
- **Gripper**: calibrated (`dex1_bridge/calibration.json`), its bus adapter connected by USB to PC2 and
  powered from the 12 V XT30. Check the servo label: a 7.4 V STS3215 needs a buck converter.

All `scripts/...` commands below run from the `mobilab-g1-teleop` checkout on the laptop.

## 1. Reach the robot

Cable the laptop to the robot (USB-C Ethernet adapter, laptop at `192.168.123.222`), then:

```bash
scripts/config-robot-ssh.sh --ip 192.168.123.164 --ssh-alias g1-al39   # password once
scripts/config-robot-sudo.sh --host g1-al39                            # sudo without password
scripts/config-robot-wifi.sh --host g1-al39                            # teleop + lab Wi-Fi
```

Check that Wi-Fi works: `ping` the robot's Wi-Fi address and `ssh g1-al39` with the cable unplugged.

Two things found on `g1-al39` that you may also find on other G1s:

- **Same SSH host key as another G1** (`g1-gort`): both were flashed from one image. The scripts identify a
  robot by its host key, so they can't tell those two apart. Harmless while only one is on the network;
  fix with new host keys on one robot (`sudo rm /etc/ssh/ssh_host_* && sudo dpkg-reconfigure openssh-server`)
  and register it again.
- **No internet on the robot even on Wi-Fi**: its default route goes out `eth0` to `192.168.123.1`, which
  doesn't exist, and wins over the Wi-Fi route. `config-robot-teleoperation.sh` works around it by sharing
  the laptop's internet through SSH. For single packages, download them on the laptop and copy them (see
  step 3). Not changed on the robot: the lab scripts never touch the robot's `eth0` profile.

## 2. Install xr_teleoperate

The gripper speaks the regular Dex1 DDS protocol; only teleop needs changes, all in
[MOBILAB-UDESC/xr_teleoperate#1](https://github.com/MOBILAB-UDESC/xr_teleoperate/pull/1), branch
`dex1-one-gripper`:

- **one gripper**: upstream waits forever for both grippers;
- **controllers**: index trigger closes, middle-finger grip opens (upstream: trigger only, narrow window);
- **start from the headset**: A on the right controller starts tracking, like `r` on the computer.

Check out that branch, or `independent-dex3` once it's merged, in the submodule, then install:

```bash
(cd xr_teleoperate && git fetch && git checkout dex1-one-gripper)
scripts/config-robot-teleoperation.sh --host g1-al39 --yes
```

This installs conda env `tv` (Python 3.10), xr_teleoperate in `~/teleoperation` (linked as
`~/xr_teleoperate`), `unitree_sdk2_python`, tmux and a certificate. On a Jetson, the `nlopt` pip build
fails and the script falls back to conda's `nlopt`; that's expected.

To update only xr_teleoperate on a robot that already has it (no internet needed), push the commit over
SSH into the robot's checkout:

```bash
cd xr_teleoperate
git push ssh://g1-al39/home/unitree/teleoperation/xr_teleoperate dex1-one-gripper:refs/heads/dex1-one-gripper
ssh g1-al39 'cd ~/xr_teleoperate && git checkout dex1-one-gripper && git log --oneline -1'
```

Not while teleop runs. Once the robot has `dex1-one-gripper` checked out, git refuses to push into it;
push to a side branch and fast-forward on the robot:

```bash
git push ssh://g1-al39/home/unitree/teleoperation/xr_teleoperate dex1-one-gripper:refs/heads/dex1-one-gripper-next
ssh g1-al39 'cd ~/xr_teleoperate && git merge --ff-only dex1-one-gripper-next && git branch -d dex1-one-gripper-next'
```

Optional, checks both changes on the robot without touching real grippers (DDS domain 9, `lo`):

```bash
ssh g1-al39
conda activate tv && cd ~/xr_teleoperate
python -m unittest -v teleop.utils.test_button_release teleop.robot_control.test_dex1_gripper_controller   # 19 tests, ~50 s
```

## 3. Install the bridge on the robot

```bash
# serial port access for the robot user (log in again afterwards)
ssh g1-al39 'sudo usermod -aG dialout unitree'

# pyserial into tv, copied from the laptop because the robot has no internet (step 1)
python3 -m pip download --no-deps --only-binary=:all: -d /tmp/wheels pyserial==3.5
scp /tmp/wheels/pyserial-3.5-py2.py3-none-any.whl g1-al39:/tmp/
ssh g1-al39 'source ~/miniconda3/etc/profile.d/conda.sh && conda activate tv && pip install --no-index /tmp/pyserial-3.5-py2.py3-none-any.whl'

# the bridge, with this gripper's calibration
scp -r dex1_bridge g1-al39:~/pincopen_dex1_bridge     # from this repo's root
```

Find the adapter: `ssh g1-al39 'ls -l /dev/serial/by-id'`. On `g1-al39` it is `/dev/ttyACM0`
(`usb-1a86_USB_Single_Serial_58CD177307-if00`, motor id 7).

## 4. Smoke test: robot bridge, laptop client

Gripper free to move, fingers out of the jaws. On the robot:

```bash
ssh -t g1-al39
source ~/miniconda3/etc/profile.d/conda.sh && conda activate tv
cd ~/pincopen_dex1_bridge
python pincopen_dex1_server.py --port /dev/ttyACM0 --side right -n wlan0
```

Expect `motor 7 on /dev/ttyACM0 ...` and `PincOpen Dex1 server started`. On the laptop:

```bash
source .venv-dex1/bin/activate && cd dex1_bridge
python test_dex1_sweep.py --watch -n en0     # state: q ~ 0 closed, ~ 5.4 open when moved by hand
python test_dex1_sweep.py --q 2.7 -n en0     # torque on, holds half open
python test_dex1_sweep.py -n en0             # sine sweep
```

This runs DDS over the lab Wi-Fi (`wlan0` on the robot, `en0` on the laptop), which worked on MobiLink.
Over the cable instead, use `-n eth0` on the robot and the laptop's USB Ethernet interface (the one with
`192.168.123.222`, e.g. `en15`) on the laptop. CycloneDDS fails with `does not match an available
interface` when that interface is gone, e.g. the cable came loose.

Result on `g1-al39` (2026-11-04): state, hold and sweep all worked over Wi-Fi.

## 5. Teleoperate with the PICO controller

Check the robot first (from the laptop): `scripts/run-robot-state.sh --host g1-al39 --state status`.
On `g1-al39` after a fresh boot (2026-11-05) the motion mode was `ai` but the locomotion service didn't
answer (`GetFsmId` → 3102, nobody listening on `rt/api/sport/request`). Hanging teleop still works:
xr_teleoperate releases the motion mode itself and drives the arms directly. Standing teleop doesn't,
and `run-robot-state.sh --state damping` can't stop the robot then: the remote's L2 + B is the stop.

Bridge on the robot, on `eth0` this time (same machine and interface as xr_teleoperate):

```bash
python pincopen_dex1_server.py --port /dev/ttyACM0 --side right -n eth0
```

Then teleop, robot hanging on the gantry for the first run, someone holding the remote for damping
(L2 + B):

```bash
scripts/run-robot-teleoperation.sh --host g1-al39 --arm G1_29 --ee dex1 --input-mode controller --hanging
```

`--input-mode controller` with `--ee dex1` needs mobilab-g1-teleop's ADR-027 change to this script; before
it, the script refused controllers with any hand. About 10 s after start, xr_teleoperate logs `No state
from the left gripper; controlling the right gripper only.`

Right controller:

| Input | Effect |
|---|---|
| A (press and release) | starts tracking, like `r` in the teleop terminal |
| index trigger held | closes; deeper pull = faster (full pull ≈ 1.5 s for the whole stroke) |
| middle-finger grip held | opens, same speeds |
| neither | stays where it is, and keeps holding a grasped object |

Common mistake: the bridge still running with `-n wlan0` from the smoke test. Teleop listens on `eth0`,
never sees the gripper and stops after 10 s with `No state on rt/dex1/left/state or rt/dex1/right/state`.

Result on `g1-al39` (2026-11-05): hanging teleop with the PICO controller worked, gripper driven by the
upstream trigger mapping. The trigger/grip mapping (911063d) passes its tests on the robot; not yet tried
on hardware, nor the A button (74f303c).

## Not done yet

- Starting the bridge automatically with teleop (`run-robot-teleoperation.sh --ee dex1`), a udev name for
  the adapter, and a `config-robot-pincopen.sh` install script in mobilab-g1-teleop.
- Trigger/grip mapping and A to start, on hardware (step 5).
