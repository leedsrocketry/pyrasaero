# pyrasaero

Automates RASAero II to export per-altitude aeroplot data and flight simulation results for a rocket, then converts the cumulative assembly outputs into per-component aerodynamic tables and a reformatted SI-unit flight simulation CSV for the Leeds Flight Simulator. Windows only.

---

## Background

LFS requires aerodynamic data as per-component tables -- one CSV per component (nosecone, body tube, fin set, boattail, etc.) covering a grid of Mach number, Reynolds number, and angle of attack. RASAero II does not export this directly; it exports cumulative assembly data, where each export includes the contribution of all components from the nose down to that point.

pyrasaero bridges this gap. It reads a simulation YAML (shared with LFS), follows the vehicle YAML reference to get the vehicle geometry, generates a CDX1 file, and drives RASAero II via GUI automation (pywinauto and keyboard) to:

1. Export aeroplot CSVs at multiple altitudes, then convert the cumulative exports into per-component tables by successive differencing. The resulting CSVs are written to `aero-tables/` next to the vehicle YAML.
2. Run a flight simulation, export the results to CSV, and reformat with SI units and lowercase snake_case headers. The reformatted CSV is written to the `verification.reference_trajectory` path from the simulation config.

Built for the Gryphon II Block II (G2B2) campaign by the Leeds University Rocketry Association (LURA).


## GUI Timing

Because pyrasaero drives RASAero II via GUI automation, it relies on fixed delays (`time.sleep`) to wait for windows, menus, and dialogs to appear. These delays are defined as class attributes on `RASAero` in `automation.py`:

| Attribute | Default | Used for |
|-----------|---------|----------|
| `guiShortDelay__s` | 0.5 | Menu navigation, dialog interactions |
| `guiLongDelay__s` | 1.0 | Window launches, file operations |
| `simulationDelay__s` | 2.0 | Waiting for the flight simulation to complete |
| `simulationDataDelay__s` | 3.0 | Waiting for the simulation data viewer to open |

If automation fails because a window hasn't appeared in time (especially on slower machines), increase the relevant delay. You can override them before calling any export method:

```python
RASAero.guiLongDelay__s = 4.0        # slower machine — give windows more time
RASAero.simulationDelay__s = 5.0     # long-burning motor — simulation takes longer
```


## Installation

**Prerequisites:** Python 3.10+, Windows, RASAero II installed.

```
pip install click pyyaml numpy pandas scipy pywinauto keyboard Pillow rich
```


## Usage

### Full pipeline

```
python . run <simulation.yaml>
```

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


## Input Files

### Simulation YAML

The same simulation YAML that drives LFS (e.g. `cape-wrath.yaml`). Must contain:

- `vehicle` -- path to the vehicle YAML (relative to this file)
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


## Contact

- **Toby Thomson** -- el21tbt@leeds.ac.uk, me@tobythomson.co.uk
- **LURA Team** -- launch@leedsrocketry.co.uk
