# pyrasaero

Automates RASAero II to export per-altitude aeroplot data for a rocket, then converts the cumulative assembly outputs into per-component aerodynamic tables for the Leeds Flight Simulator. Windows only.

---

## Table of Contents

- [Background](#background)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Input Files](#input-files)
- [Output Files](#output-files)
- [Contact](#contact)
- [Licence](#licence)

---

## Background

LFS requires aerodynamic data as per-component tables — one CSV per component (nosecone, body tube, fin set, boattail, etc.) covering a grid of Mach number, Reynolds number, and angle of attack. RASAero II does not export this directly; it exports cumulative assembly data, where each export includes the contribution of all components from the nose down to that point.

pyrasaero bridges this gap. It drives RASAero II via GUI automation (pywinauto and keyboard) to export aeroplot CSVs at multiple altitudes, then converts the cumulative exports into per-component tables by successive differencing. The resulting CSVs are written directly to the LFS simulation's `aero_tables/` directory.

Built for the Gryphon II Block II (G2B2) campaign by the Leeds University Rocketry Association (LURA).


## Installation

**Prerequisites:** Python 3.10+, Windows, RASAero II installed.

```
git clone git@github.com:leedsrocketry/pyrasaero.git
cd pyrasaero
pip install -e .
```

Or install dependencies directly:

```
pip install numpy pandas scipy pywinauto keyboard opencv-python Pillow matplotlib
```


## Quick Start

**Step 1 — Export aeroplots from RASAero II:**

```
pyrasaero
```

Opens RASAero II, loads the CDX1 file, and exports aeroplot CSVs for each component at each configured altitude. CSVs are saved to `rasaero-data/`.

**Step 2 — Convert to LFS aero tables:**

```
pyrasaero-convert
```

Reads the exported CSVs, differences cumulative assemblies to isolate per-component contributions, and writes one CSV per component to the LFS `aero_tables/` directory.


## Usage

### Exporting Aeroplots

```
pyrasaero
```

Requires RASAero II to be installed and the CDX1 file to be present at the configured path. The script drives the RASAero II GUI — do not interact with the machine while it runs.

Motor and altitude configuration is defined in `pyrasaero/cli.py`. Edit the motor definitions and altitude list there before running.

### Converting to LFS Tables

```
pyrasaero-convert
```

Reads from `rasaero-data/` (relative to the pyrasaero repo root) and writes to `../leeds-flight-simulator/simulations/g2b2-safety-case/aero_tables/`. Both paths are configured at the top of `pyrasaero/convert.py`.

Prints a verification summary on completion — the sum of per-component CA and CN values at representative conditions should match the full-vehicle values from RASAero.


## Input Files

### CDX1 File (`.CDX1`)

RASAero II's native project file. Contains vehicle geometry, motor selection, and simulation configuration. Used by both the automation script (to configure each run) and the converter (to read vehicle length for CP unit conversion).

Path is configured in `pyrasaero/cli.py` and `pyrasaero/convert.py`.

### Aeroplot CSVs

Raw exports from RASAero II's aeroplot function. One CSV per component per altitude, named `aeroplots-{Component}-{altitude_ft}.csv`. Stored in `rasaero-data/` after running `pyrasaero`.

Each file is a 15-column RASAero II aeroplot export. The converter reads Mach, Reynolds, AoA, CA (power-off), CA (power-on), CN, CN_alpha, and CP.

### GUI Reference Screenshots

`pyrasaero/gui-pics/` contains reference screenshots used by the OpenCV-based GUI automation to locate UI elements in RASAero II. These must match the installed version of RASAero II. If automation fails, compare the screenshots against the actual RASAero II UI and recapture if necessary.


## Output Files

### Aero Table CSVs

One CSV per aerodynamic component, written to the LFS `aero_tables/` directory.

**Column layout:**

| Column | Description |
|--------|-------------|
| `Mach` | Mach number |
| `Reynolds` | Reynolds number |
| `AoA_deg` | Angle of attack (degrees) |
| `CA_off` | Axial force coefficient, motor off |
| `CA_on` | Axial force coefficient, motor on |
| `CN` | Normal force coefficient |
| `CP_m` | Centre of pressure, metres from nose tip |
| `CN_alpha_per_rad` | Normal force slope (1/rad), averaged over the linear AoA regime (≤ 5°) |

These files are consumed directly by LFS. After running `pyrasaero-convert`, copy or link the `aero_tables/` directory to the relevant LFS simulation directory and update the `aero_tables` path in `vehicle.yaml`.


## Contact

- **Toby Thomson** — el21tbt@leeds.ac.uk, me@tobythomson.co.uk
- **LURA Team** — launch@leedsrocketry.co.uk


## Licence

<!-- TODO: Add licence information -->
