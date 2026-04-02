# pyrasaero

Automates RASAero II to export per-altitude aeroplot data for a rocket, then converts the cumulative assembly outputs into per-component aerodynamic tables for the Leeds Flight Simulator. Windows only.

---

## Background

LFS requires aerodynamic data as per-component tables -- one CSV per component (nosecone, body tube, fin set, boattail, etc.) covering a grid of Mach number, Reynolds number, and angle of attack. RASAero II does not export this directly; it exports cumulative assembly data, where each export includes the contribution of all components from the nose down to that point.

pyrasaero bridges this gap. It reads a simulation YAML (shared with LFS), follows the vehicle YAML reference to get the vehicle geometry, generates a CDX1 file, drives RASAero II via GUI automation (pywinauto and keyboard) to export aeroplot CSVs at multiple altitudes, then converts the cumulative exports into per-component tables by successive differencing. The resulting CSVs are written to `aero-tables/` next to the vehicle YAML.

Built for the Gryphon II Block II (G2B2) campaign by the Leeds University Rocketry Association (LURA).


## Installation

**Prerequisites:** Python 3.10+, Windows, RASAero II installed.

```
pip install click pyyaml numpy pandas scipy pywinauto keyboard Pillow
```


## Usage

### Full pipeline

```
python -m pyrasaero run <simulation.yaml>
```

Reads the simulation YAML, generates a CDX1 from the vehicle config, drives RASAero II to export aeroplots at each altitude, then converts the cumulative exports into per-component LFS aero tables.

**Flags:**

| Flag | Effect |
|------|--------|
| `--convert-only` | Skip RASAero export; only convert existing CSVs in `rasaero-data/` |
| `--whole-vehicle` | Output a single whole-vehicle aero table instead of per-component |
| `--altitude-step` `FLOAT` | Altitude grid spacing in metres (default 2000) |
| `--max-altitude` `FLOAT` | Maximum altitude in metres (default 20000) |

### Write CDX1 only

```
python -m pyrasaero write-cdx1 <simulation.yaml>
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
- `rasaero` -- surface finish, colour, RASAero motor name

## Output Files

### Aero Table CSVs

One CSV per aerodynamic component, written to `aero-tables/` next to the vehicle YAML.

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


## Contact

- **Toby Thomson** -- el21tbt@leeds.ac.uk, me@tobythomson.co.uk
- **LURA Team** -- launch@leedsrocketry.co.uk
