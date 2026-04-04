"""Convert cumulative RASAero II aeroplots into per-component LFS tables.

The aeroplots CSVs in ``rasaero-data/`` are *cumulative* RASAero
configurations (vehicle built up to and including that component).
This script differences successive assemblies to extract individual
component contributions.

Processing:
  - For each altitude file, load all 5 assemblies and difference positionally
  - Use vehicle-level Re (from BoatTail / full vehicle assembly) for all
  - Quantise Re per altitude (median across Mach values)
  - Decimate Mach to 0.1 spacing
  - Convert CP from inches to metres
  - CP moment balance uses CNAlpha to avoid division by zero at AoA=0

Output: one 8-column CSV per component in ``aero-tables/``, plus a
whole-vehicle 8-column CSV (``vehicle-aero-table.csv``) alongside it.
"""

from __future__ import annotations

import csv
import math
import re
import statistics
from pathlib import Path

INCHES_TO_M = 0.0254
MACH_TOL = 0.005
MACH_STEP = 0.1
CNALPHA_EPS = 1.0e-6

# RASAero CSV column indices (15-column aeroplot format)
COL_MACH = 0
COL_ALPHA = 1
COL_CA_OFF = 5
COL_CA_ON = 6
COL_CN = 8
COL_CNALPHA = 11
COL_CP = 12
COL_RE = 14

# Aft-to-fore component order.  Each entry names the aftmost component
# present in that cumulative assembly.
# Iteration is reversed for differencing: NoseCone -> BodyTube -> BoatTail -> Fin.
AFT_COMPONENT_ORDER = ("Fin", "BoatTail", "BodyTube", "NoseCone")

# Row layout used internally (8 columns).
I_MACH, I_RE, I_AOA = 0, 1, 2
I_CA_OFF, I_CA_ON, I_CN, I_CNA, I_CP = 3, 4, 5, 6, 7


def _is_mach_on_grid(mach: float) -> bool:
    """True if *mach* is within tolerance of a 0.1-spaced grid point."""
    remainder = mach / MACH_STEP
    return abs(remainder - round(remainder)) < MACH_TOL / MACH_STEP


def _load_altitude_file(path: Path) -> list[list[float]]:
    """Load one aeroplots CSV, extract 8 columns.

    Returns rows as [Mach, Re, AoA, CA_off, CA_on, CN, CNAlpha, CP_inches].
    CP is kept in inches here; conversion to metres happens later.
    """
    rows: list[list[float]] = []
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        if len(header) < 15:
            return rows
        for line in reader:
            if len(line) < 15:
                continue
            rows.append([
                float(line[COL_MACH]),
                float(line[COL_RE]),
                float(line[COL_ALPHA]),
                float(line[COL_CA_OFF]),
                float(line[COL_CA_ON]),
                float(line[COL_CN]),
                float(line[COL_CNALPHA]),
                float(line[COL_CP]),
            ])
    return rows


def _find_altitude_files(src_dir: Path, component: str) -> list[tuple[int, Path]]:
    """Return sorted (altitude_ft, path) pairs for one component."""
    pattern = re.compile(
        rf"^aeroplots-{re.escape(component)}-(\d+)\.csv$", re.IGNORECASE,
    )
    hits: list[tuple[int, Path]] = []
    for p in src_dir.iterdir():
        m = pattern.match(p.name)
        if m:
            hits.append((int(m.group(1)), p))
    return sorted(hits)


def convert(cfg: object) -> None:
    """Run the conversion pipeline.

    Parameters
    ----------
    cfg
        A ``PyrasaeroConfig`` instance (from ``config.load_config``).
    """
    src_dir = cfg.vehicle_yaml_dir / "rasaero-data"
    dst_dir = cfg.aero_tables_dir
    vehicle_len_mm = cfg.components.length_mm

    if not src_dir.is_dir():
        raise SystemExit(f"Source directory not found: {src_dir}")

    # Remove stale aero table CSVs from previous runs
    if dst_dir.is_dir():
        for f in dst_dir.iterdir():
            if f.suffix.lower() == ".csv":
                f.unlink()

    print(f"Vehicle length: {vehicle_len_mm:.1f} mm")

    # Discover altitude files — use BoatTail (full vehicle) as reference
    alt_files_ref = _find_altitude_files(src_dir, "BoatTail")
    altitudes = [alt for alt, _ in alt_files_ref]
    print(f"Altitudes: {len(altitudes)} ({altitudes[0]}..{altitudes[-1]} ft)")

    # Check all components have the same altitudes
    fore_to_aft = list(reversed(AFT_COMPONENT_ORDER))
    comp_alt_files: dict[str, dict[int, Path]] = {}
    for comp in fore_to_aft:
        af = _find_altitude_files(src_dir, comp)
        comp_alt_files[comp] = {alt: path for alt, path in af}
        missing = set(altitudes) - set(comp_alt_files[comp])
        if missing:
            print(f"  WARNING: {comp} missing altitudes: {sorted(missing)}")

    dst_dir.mkdir(parents=True, exist_ok=True)

    # Accumulate per-component rows across all altitudes
    comp_output: dict[str, list[list[float]]] = {c: [] for c in fore_to_aft}

    for alt_ft in altitudes:
        # Load all assemblies at this altitude
        asm_data: dict[str, list[list[float]]] = {}
        for comp in fore_to_aft:
            path = comp_alt_files[comp].get(alt_ft)
            if path is None:
                raise SystemExit(
                    f"{comp} missing altitude {alt_ft} — cannot proceed")
            asm_data[comp] = _load_altitude_file(path)

        # Verify all assemblies have the same number of rows
        n = len(asm_data[fore_to_aft[0]])
        for comp in fore_to_aft[1:]:
            if len(asm_data[comp]) != n:
                raise SystemExit(
                    f"Row count mismatch at alt={alt_ft}: "
                    f"{fore_to_aft[0]} has {n}, {comp} has {len(asm_data[comp])}"
                )

        # Vehicle-level Re: from BoatTail (full vehicle), quantised to median
        vehicle_re_values = [r[I_RE] for r in asm_data["BoatTail"]]
        vehicle_re = statistics.median(vehicle_re_values)

        # Difference fore to aft
        vehicle_len_in = vehicle_len_mm / 25.4
        prev_rows: list[list[float]] | None = None
        for comp in fore_to_aft:
            asm = asm_data[comp]

            if prev_rows is not None:
                for j in range(n):
                    a = asm[j]
                    p = prev_rows[j]

                    ca_off = a[I_CA_OFF] - p[I_CA_OFF]
                    ca_on = a[I_CA_ON] - p[I_CA_ON]
                    cn = a[I_CN] - p[I_CN]
                    cna = a[I_CNA] - p[I_CNA]

                    if abs(cna) > CNALPHA_EPS:
                        # When both cumulative CN values are zero (AoA=0),
                        # RASAero's cumulative CP is undefined and the
                        # moment balance produces garbage.  Mark as NaN
                        # and backfill from the nearest valid AoA below.
                        if abs(a[I_CN]) < 1e-12 and abs(p[I_CN]) < 1e-12:
                            cp = float("nan")
                        else:
                            cp = (a[I_CP] * a[I_CNA] - p[I_CP] * p[I_CNA]) / cna
                        # Clamp destabilising components (negative CNα)
                        # to the vehicle length.  Their virtual CP can
                        # be far aft, which is correct for static moment
                        # balance but causes numerical instability in
                        # per-component local-AoA lever arm calculations.
                        if cna < 0 and not math.isnan(cp):
                            cp = max(0.0, min(cp, vehicle_len_in))
                    else:
                        cp = a[I_CP]

                    if _is_mach_on_grid(a[I_MACH]):
                        comp_output[comp].append([
                            a[I_MACH], vehicle_re, a[I_AOA],
                            ca_off, ca_on, cn, cna,
                            cp * INCHES_TO_M,
                        ])
            else:
                # First assembly (NoseCone): contribution = cumulative
                for j in range(n):
                    a = asm[j]
                    if _is_mach_on_grid(a[I_MACH]):
                        comp_output[comp].append([
                            a[I_MACH], vehicle_re, a[I_AOA],
                            a[I_CA_OFF], a[I_CA_ON], a[I_CN], a[I_CNA],
                            a[I_CP] * INCHES_TO_M,
                        ])

            # Save raw cumulative rows (NOT component rows) for next iteration
            prev_rows = [list(r) for r in asm]

    # Fill missing grid cells and write output
    for comp in fore_to_aft:
        rows = comp_output[comp]

        # Fill missing (Mach, Re, AoA) cells
        grid: dict[tuple[float, float], dict[float, list[float]]] = {}
        for r in rows:
            key = (r[I_MACH], r[I_RE])
            grid.setdefault(key, {})[r[I_AOA]] = r

        all_aoa = sorted({r[I_AOA] for r in rows})
        filled = 0
        for key, aoa_map in grid.items():
            for aoa in all_aoa:
                if aoa not in aoa_map:
                    nearest = min(aoa_map, key=lambda a: abs(a - aoa))
                    new_row = list(aoa_map[nearest])
                    new_row[I_AOA] = aoa
                    rows.append(new_row)
                    filled += 1

        # Backfill NaN CPs.  At AoA=0 (CN=0 for both assemblies) the
        # cumulative CP from RASAero is undefined, so the moment-balance
        # was marked NaN above.  Replace with the nearest valid AoA's CP.
        for key, aoa_map in grid.items():
            for aoa, row in aoa_map.items():
                if math.isnan(row[I_CP]):
                    nearest = min(
                        (a for a in aoa_map if not math.isnan(aoa_map[a][I_CP])),
                        key=lambda a: abs(a - aoa),
                        default=None,
                    )
                    if nearest is not None:
                        row[I_CP] = aoa_map[nearest][I_CP]

        rows.sort(key=lambda r: (r[I_MACH], r[I_RE], r[I_AOA]))

        # Write CSV — 8 columns, CN_alpha_per_rad appended after CP_m
        dst_path = dst_dir / f"{comp.lower()}.csv"
        with open(dst_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Mach", "Reynolds", "AoA_deg",
                             "CA_off", "CA_on", "CN", "CP_m", "CN_alpha_per_rad"])
            for r in rows:
                writer.writerow([r[0], r[1], r[2], r[3], r[4], r[5], r[7], r[6]])

        extra = f" (filled {filled})" if filled else ""
        print(f"  {comp:>10}: {len(rows)} rows{extra} -> {dst_path}")

    # --- Whole-vehicle CSV (from full-vehicle assembly = aftmost component) ---
    full_vehicle_comp = AFT_COMPONENT_ORDER[0]  # aftmost = full vehicle
    wv_rows: list[list[float]] = []
    for alt_ft in altitudes:
        path = comp_alt_files[full_vehicle_comp].get(alt_ft)
        if path is None:
            continue
        raw = _load_altitude_file(path)
        vehicle_re = statistics.median(r[I_RE] for r in raw)
        for r in raw:
            if _is_mach_on_grid(r[I_MACH]):
                wv_rows.append([
                    r[I_MACH], vehicle_re, r[I_AOA],
                    r[I_CA_OFF], r[I_CA_ON], r[I_CN],
                    r[I_CP] * INCHES_TO_M, r[I_CNA],
                ])

    wv_rows.sort(key=lambda r: (r[0], r[1], r[2]))
    wv_path = dst_dir.parent / "vehicle-aero-table.csv"
    with open(wv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Mach", "Reynolds", "AoA_deg",
                         "CA_off", "CA_on", "CN", "CP_m", "CN_alpha_per_rad"])
        for r in wv_rows:
            writer.writerow([r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]])
    print(f"\n  Whole-vehicle: {len(wv_rows)} rows -> {wv_path}")

    # --- Verification ---
    print("\n--- Verification (CA_off sum at M=0.5, AoA=0) ---")
    ca_sum = 0.0
    cn_sum = 0.0
    for comp in fore_to_aft:
        p = dst_dir / f"{comp.lower()}.csv"
        with open(p, newline="") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if abs(float(row[0]) - 0.5) < 0.01 and float(row[2]) == 0:
                    ca = float(row[3])
                    print(f"  {comp:>10}: CA_off = {ca:+.6f}")
                    ca_sum += ca
                    break
    print(f"  {'SUM':>10}: CA_off = {ca_sum:.6f}")

    print("\n--- Verification (CN sum at M=0.5, AoA=2) ---")
    for comp in fore_to_aft:
        p = dst_dir / f"{comp.lower()}.csv"
        with open(p, newline="") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if abs(float(row[0]) - 0.5) < 0.01 and float(row[2]) == 2:
                    cn = float(row[5])
                    print(f"  {comp:>10}: CN = {cn:+.6f}")
                    cn_sum += cn
                    break
    print(f"  {'SUM':>10}: CN = {cn_sum:.6f}")

    # Check CA_on == CA_off for all components except NoseCone
    print("\n--- Verification (CA_on vs CA_off at M=0.5, AoA=0) ---")
    for comp in fore_to_aft:
        p = dst_dir / f"{comp.lower()}.csv"
        with open(p, newline="") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if abs(float(row[0]) - 0.5) < 0.01 and float(row[2]) == 0:
                    ca_off = float(row[3])
                    ca_on = float(row[4])
                    diff = ca_on - ca_off
                    status = "  (no delta)" if abs(diff) < 1e-9 else f"  (delta = {diff:+.6f})"
                    print(f"  {comp:>10}: CA_off={ca_off:+.6f}  CA_on={ca_on:+.6f}{status}")
                    break

    print("\nDone.")
