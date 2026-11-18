# pyrasaero

Automates RASAero II to export per-altitude aeroplot data and flight simulation results for a rocket, then converts the cumulative assembly outputs into per-component aerodynamic tables and a reformatted SI-unit flight simulation CSV for the Leeds Flight Simulator. Windows only.

---

## Background

LFS requires aerodynamic data as per-component tables -- one CSV per component (nosecone, body tube, fin set, boattail, etc.) covering a grid of Mach number, Reynolds number, and angle of attack. RASAero II does not export this directly; it exports cumulative assembly data, where each export includes the contribution of all components from the nose down to that point.

pyrasaero bridges this gap. It reads a simulation YAML (shared with LFS), follows the vehicle YAML reference to get the vehicle geometry, generates a CDX1 file, and drives RASAero II via GUI automation (pywinauto; see [How the GUI automation works](#how-the-gui-automation-works)) to:

1. Export aeroplot CSVs at multiple altitudes, then convert the cumulative exports into per-component tables by successive differencing. The resulting CSVs are written to `aero-tables/` next to the vehicle YAML.
2. Run a flight simulation, export the results to CSV, and reformat with SI units and lowercase snake_case headers. The reformatted CSV is written to the `verification.reference_trajectory` path from the simulation config.

Built for the Gryphon II Block II (G2B2) campaign by the Leeds University Rocketry Association (LURA).


## How the GUI automation works

pyrasaero drives RASAero II through Windows UI Automation (pywinauto):

- **It clicks only checked controls.** Buttons and menu items are clicked at the position UI Automation reports, and only after checking the control is visible inside its window. Text is typed only into a dialog that has been confirmed open. No keystrokes are sent to "whatever window has focus".
- **Every step waits for its result.** For example, it waits for the Flight window to appear, the simulation result to show in the grid, and the Save As dialog to open. Each wait has a timeout and fails with a clear error.
- **Exported CSVs are checked.** A file must stop growing for 4 s and pass a content check before RASAero is closed. The flight CSV must run to landing, and an aero plot CSV must reach Mach 25.
- **Pop-ups are reported, not hidden.** RASAero warnings such as "Marginal Stability" are closed automatically, and their message is shown in the WARNINGS panel.
- **RASAero is closed by ending its process.** It's restarted for every export, which also clears the previous Mach-Alt table. The CDX1 on disk is the source of truth, so nothing is lost.

The wait limits are class attributes on `RASAero` in `automation.py`. Increase them on a slow machine:

| Attribute | Default | Limit for |
|-----------|---------|-----------|
| `windowTimeout__s` | 20 | A window or dialog to appear |
| `simulationTimeout__s` | 60 | The flight simulation to finish, and the flight data window to open |
| `fileTimeout__s` | 180 | An exported CSV to be fully written |
| `settleDelay__s` | 0.3 | Pause after each click |

```python
RASAero.windowTimeout__s = 40.0      # slower machine
```

Timing for a typical run: the flight simulation export takes about 40 s. Each aero plot export takes about 25 s, and there are 4 builds × about 20 altitudes, so the full aero plot export takes about 35 minutes.


## Installation

**Prerequisites:** Python 3.10+, Windows, RASAero II installed.

Install the dependencies into a virtual environment in the repo folder:

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install click pyyaml numpy pandas scipy pywinauto rich
```

Use `.venv\Scripts\python.exe` for every command below. Your system Python won't have `pywinauto`.

### RASAero motor file

RASAero II only looks for motors in the **one** motor file selected under *File → Select Motor File*, and it remembers that choice between sessions. If that file is missing, or doesn't contain your motor, RASAero shows a "The motor ... was not found in the currently selected engine file" pop-up partway through the automation.

Before you start, select a file that contains your motor. The bundled database, `Documents\RASAero II\rasp.eng`, has around 880 motors. `run` checks this before launching RASAero and stops with a clear error if the motor can't be found.

The motor name in the vehicle YAML must match RASAero's list exactly, including spacing. For example, `O3400-IM-P  (CTI)` has **two** spaces before the bracket.


## Quick start

Starting from a rocket you have already built in RASAero II:

1. **Create the YAMLs from your CDX1:**
   ```
   .venv\Scripts\python.exe <pyrasaero> import-cdx1 <rocket.CDX1> -o <output folder>
   ```
2. **Check the generated YAMLs.** Values are converted from imperial, so check things like the rail length; 13.12 ft comes out as 3.999 m.
3. **Optionally, regenerate the CDX1 and open it in RASAero** to check the geometry:
   ```
   .venv\Scripts\python.exe <pyrasaero> write-cdx1 <output folder>\<name>-sim.yaml
   ```
4. **Run the full pipeline:**
   ```
   .venv\Scripts\python.exe <pyrasaero> run <output folder>\<name>-sim.yaml
   ```

`<pyrasaero>` is the path to this repo folder. Run the folder as a script; `python -m pyrasaero` does not work because the modules use plain top-level imports.

pyrasaero writes all its outputs next to the vehicle YAML. If your design files are in a synced folder (OneDrive/SharePoint), use `-o` to put the YAMLs in a local folder, so that run outputs aren't uploaded for everyone.


## Usage

### Full pipeline

```
python . run <simulation.yaml>
```

**While it runs, keep the PC unlocked and don't use the mouse.** pyrasaero clicks RASAero's controls with the real mouse pointer and brings RASAero's windows to the front. GUI automation doesn't work while the screen is locked. Close RASAero before starting: pyrasaero refuses to run if it's already open, because it closes RASAero by ending its process. Press Ctrl+C to abort; this also closes RASAero.

Reads the simulation YAML, generates a CDX1 from the vehicle config, drives RASAero II to run a flight simulation first, then uses the simulated flight envelope (apogee and peak Mach) to determine the aeroplot export altitude grid and Mach cap. The cumulative aeroplot exports are converted into per-component LFS aero tables with a properly resolved Reynolds number axis (see [Aerodynamic Table Format](#aerodynamic-table-format)). The flight simulation CSV is reformatted to SI units.

**Flags:**

| Flag | Effect |
|------|--------|
| `--aeroplots-convert` | Skip the slow aero plots RASAero export; only convert existing CSVs in `rasaero-data/`. Flight simulation export still runs. |
| `--time-base` `FLOAT` | Flight simulation export time step in seconds (default 0.01). Snapped down to nearest valid value: 0.01, 0.1, 0.5, or 1.0. |

### Write CDX1 only

```
python . write-cdx1 <simulation.yaml>
```

Generates a CDX1 file from the vehicle and simulation config without running RASAero. Useful for manual inspection or development.

### Import an existing CDX1

```
python . import-cdx1 <rocket.CDX1> [-o <output folder>]
```

Converts a rocket designed in RASAero II into a vehicle YAML (`<name>-vehicle.yaml`) and a simulation YAML (`<name>-sim.yaml`). By default they go in `<name>-pyrasaero/` next to the CDX1. The simulation YAML's `verification.reference_trajectory` is set to `rasaero-trajectory.csv`.

pyrasaero models a fixed layout: one nose cone, one body tube, and a boattail with the fins on it, single stage. If the CDX1 differs, the importer simplifies it and prints a warning for each change:

- multiple body tubes are merged into one, with their lengths summed
- boosters are ignored
- fins on the body tube are moved onto the boattail, keeping their position
- a missing boattail needs to be added by hand

Some values are not carried across exactly; see [Known limitations](#known-limitations).


## Input Files

### Simulation YAML

The same simulation YAML that drives LFS (e.g. `cape-wrath.yaml`). Must contain:

- `vehicle` -- path to the vehicle YAML (relative to this file)
- `verification.reference_trajectory` -- where the SI flight simulation CSV is written. Required by `run`, because the aero plot grid is derived from this trajectory.
- `site.elevation`, `launch.rail.length`, etc. -- pyrasaero reads existing LFS fields
- `rasaero.modified_barrowman`, `rasaero.turbulence` -- RASAero-specific simulation flags

### Vehicle YAML

The shared vehicle YAML (e.g. `g2b2-o3400.yaml`). pyrasaero reads:

- `body_diameter_mm`, `nozzle_diameter_mm` -- top-level vehicle dimensions
- `components` -- nested component geometry (nosecone, body_tube, boattail, fins), ordered forward-to-aft
- `mass` -- wet mass and CG
- `recovery` -- drogue and main parachute CD, diameter, and deploy threshold (used for CDX1 Recovery section)
- `rasaero` -- surface finish, colour, RASAero motor name

## Output Files

### Aerodynamic Table Format

Both per-component and whole-vehicle tables share the same 8-column CSV format and the same 3D grid structure: (Mach, Reynolds, AoA). The tables are designed for trilinear interpolation by LFS.

| Column | Description |
|--------|-------------|
| `Mach` | Mach number |
| `Reynolds` | Reynolds number |
| `AoA_deg` | Angle of attack (degrees) |
| `CA_off` | Axial force coefficient, motor off |
| `CA_on` | Axial force coefficient, motor on |
| `CN` | Normal force coefficient |
| `CP_m` | Centre of pressure, metres from nose tip |
| `CN_alpha_per_rad` | Normal force slope (1/rad) |

**Mach axis:** retains the full resolution from the RASAero aeroplot export, capped at the nearest whole number 20% above the peak Mach from the RASAero flight simulation. This keeps the table compact by excluding Mach values that are never encountered in flight, reducing memory usage in LFS.

**Reynolds axis:** a regular log-spaced grid covering the full range of Reynolds numbers present in the aeroplot data. Each altitude file from RASAero provides aerodynamic coefficients at actual flight Reynolds numbers (Re = rho * V * L / mu, which varies with both altitude and Mach). For each (Mach, AoA) combination, the values from all altitude files are interpolated onto this common Re grid, so LFS can look up coefficients at any flight Reynolds number and receive data corresponding to the correct aerodynamic environment.

**AoA axis:** retains the values from the RASAero aeroplot export (typically 0, 2, and 4 degrees).

### Per-Component Aero Table CSVs

One CSV per aerodynamic component, written to `aero-tables/` next to the vehicle YAML. Per-component contributions are extracted by differencing successive cumulative assemblies exported from RASAero.

### Whole-Vehicle Aero Table CSV

A single `vehicle-aero-table.csv` written next to the `aero-tables/` directory. This contains the whole-vehicle (full cumulative assembly) aerodynamic data without per-component differencing.


### Flight Simulation CSV

A single reformatted CSV written to the `verification.reference_trajectory` path from the simulation config. All columns are converted from imperial to SI units with lowercase snake_case headers.

| Column | Description |
|--------|-------------|
| `time_s` | Time (seconds) |
| `stage` | Stage identifier |
| `stage_time_s` | Stage time (seconds) |
| `mach` | Mach number |
| `aoa_deg` | Angle of attack (degrees) |
| `cd` | Drag coefficient |
| `thrust_n` | Thrust (Newtons) |
| `mass_kg` | Vehicle mass (kilograms) |
| `drag_n` | Drag force (Newtons) |
| `lift_n` | Lift force (Newtons) |
| `cg_m` | Centre of gravity from nose (metres) |
| `cp_m` | Centre of pressure from nose (metres) |
| `stability_margin_cal` | Stability margin (calibres) |
| `acceleration_ms2` | Total acceleration (m/s²) |
| `acceleration_vertical_ms2` | Vertical acceleration (m/s²) |
| `acceleration_horizontal_ms2` | Horizontal acceleration (m/s²) |
| `velocity_ms` | Total velocity (m/s) |
| `velocity_vertical_ms` | Vertical velocity (m/s) |
| `velocity_horizontal_ms` | Horizontal velocity (m/s) |
| `pitch_attitude_deg` | Pitch attitude (degrees) |
| `flight_path_angle_deg` | Flight path angle (degrees) |
| `altitude_m` | Altitude (metres) |
| `distance_m` | Distance (metres) |


## Troubleshooting

| Symptom | Cause and fix |
|---------|---------------|
| "The motor ... was not found in the currently selected engine file", or a pre-run error saying the motor or motor file wasn't found | RASAero's selected motor file is missing or doesn't contain the motor. In RASAero use *File → Select Motor File* and pick `Documents\RASAero II\rasp.eng` (or another file containing the motor). Check the motor name's spacing. See [RASAero motor file](#rasaero-motor-file). |
| "RASAero II is already running" | Save your work in RASAero and close it, then rerun. If no RASAero window is visible, end it with `taskkill /F /IM "RASAero II.exe"`. |
| "RASAero's Open dialog did not appear" or "Timed out waiting for ..." | RASAero didn't respond in time: the screen was locked, another window covered it, or RASAero showed an unexpected pop-up. The error lists any pop-up text RASAero showed. Unlock the PC and retry; on a slow machine, increase the [timeouts](#how-the-gui-automation-works). |
| "RASAero export ... is incomplete" | RASAero didn't finish writing the CSV within `fileTimeout__s`; increase it. |
| "RASAero control ... is not visible; refusing to click blind" | Another window was covering RASAero, or RASAero's layout differs from what pyrasaero expects. Don't use the PC during the run and retry. |
| `ModuleNotFoundError: No module named 'pywinauto'` | You're using a Python without the dependencies. Run with `.venv\Scripts\python.exe`. |
| `run` stops saying `verification.reference_trajectory` must be set | Add it to the simulation YAML; see [Simulation YAML](#simulation-yaml). |


## Known limitations

- **Fin wedge dimensions (FX1/FX3).** The CDX1 writer always uses `FX1 = (root chord + tip chord) / 4` and `FX3 = 0`, whatever the original design had. For Double Wedge and Hexagonal airfoils this changes the fin cross-section, and so the supersonic fin drag.
- **Wind and pressure.** The generated CDX1 always uses 0 wind speed (aero plots must be generated in still air) and 29.53 inHg launch site pressure, so the flight simulation is a still-air reference.
- **Recovery.** The drogue always deploys at apogee. The main parachute's `threshold` must be a number (altitude in metres), not `apogee`.
- **Fields left out.** The generated CDX1 leaves out fields RASAero writes itself but pyrasaero doesn't use (booster flags, launch lugs, rail guides, etc.). RASAero opens it without complaint.


## Contact

- **Toby Thomson** -- el21tbt@leeds.ac.uk, me@tobythomson.co.uk
- **LURA Team** -- launch@leedsrocketry.co.uk
