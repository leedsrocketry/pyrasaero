"""Command-line interface for pyrasaero."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import click

from config import load_config, PyrasaeroConfig


def _read_flight_envelope(path: Path) -> tuple[float, float]:
    """Return (max_altitude_m, max_mach) from a reformatted flight sim CSV."""
    max_alt = 0.0
    max_mach = 0.0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            alt = float(row["altitude_m"])
            mach = float(row["mach"])
            if alt > max_alt:
                max_alt = alt
            if mach > max_mach:
                max_mach = mach
    return max_alt, max_mach


def _build_rocket(cfg: PyrasaeroConfig):
    """Construct a Rocket from a PyrasaeroConfig."""
    from automation import Rocket

    rec = cfg.recovery
    drogue_cd = rec.drogue.cd if rec.drogue else None
    drogue_dia = rec.drogue.diameter_mm if rec.drogue else None
    main_cd = rec.main.cd if rec.main else None
    main_dia = rec.main.diameter_mm if rec.main else None
    main_alt = (
        float(rec.main.threshold)
        if rec.main and isinstance(rec.main.threshold, (int, float))
        else None
    )

    return Rocket(
        surfaceFinish=cfg.rasaero_vehicle.surface_finish,
        motor=cfg.rasaero_vehicle.motor,
        loadedMass__kg=cfg.mass.wet_mass_kg,
        nozzleDiameter__mm=cfg.components.nozzle_diameter_mm,
        loadedCoM__m=cfg.mass.wet_cg_mm / 1000,
        noseconeShape=cfg.components.nosecone_shape,
        noseconeLength__mm=cfg.components.nosecone_length_mm,
        bodyDiameter__mm=cfg.components.body_diameter_mm,
        noseconeTipRadius__mm=cfg.components.nosecone_tip_radius_mm,
        bodyTubeLength__mm=cfg.components.body_tube_length_mm,
        boattailLength__mm=cfg.components.boattail_length_mm,
        boattailAftDiameter__mm=cfg.components.boattail_aft_diameter_mm,
        finRootChord__mm=cfg.components.fin_root_chord_mm,
        finAftOffset__mm=cfg.components.fin_aft_offset_mm,
        finAirfoilSection=cfg.components.fin_airfoil_section,
        finCount=cfg.components.fin_count,
        finSpan__mm=cfg.components.fin_span_mm,
        finSweepDistance__mm=cfg.components.fin_sweep_distance_mm,
        finTipChord__mm=cfg.components.fin_tip_chord_mm,
        finLeadingEdgeRadius__mm=cfg.components.fin_leading_edge_radius_mm,
        finThickness__mm=cfg.components.fin_thickness_mm,
        color=cfg.rasaero_vehicle.color,
        drogueCD=drogue_cd,
        drogueDiameter__mm=drogue_dia,
        mainCD=main_cd,
        mainDiameter__mm=main_dia,
        mainParachuteAltitude__m=main_alt,
    )


@click.group()
def main() -> None:
    """pyrasaero -- RASAero II automation for the Leeds Flight Simulator."""


@main.command()
@click.argument("simulation_yaml", type=click.Path(exists=True, path_type=Path))
@click.option("--aeroplots-convert", is_flag=True,
              help="Skip RASAero aero plots export; only convert existing CSVs. "
                   "Flight simulation export still runs.")
@click.option("--time-base", type=float, default=0.01,
              help="Flight simulation export time step in seconds (default 0.01). "
                   "Snapped down to nearest valid value: 0.01, 0.1, 0.5, or 1.0.")
def run(
    simulation_yaml: Path,
    aeroplots_convert: bool,
    time_base: float,
) -> None:
    """Run the full pyrasaero pipeline: CDX1 generation, RASAero export, conversion.

    The flight simulation is run first so that the aeroplot altitude grid
    and Mach cap can be derived from the simulated flight envelope.
    """
    cfg = load_config(simulation_yaml)

    from automation import Simulation, RASAero

    rocket = _build_rocket(cfg)

    simulation = Simulation(
        modifiedBarrowmanFlag=cfg.rasaero_sim.modified_barrowman,
        turbulenceFlag=cfg.rasaero_sim.turbulence,
        launchsiteElevation__m=cfg.rasaero_sim.elevation_m,
        launchInclination__deg=cfg.rasaero_sim.inclination_deg,
        launchRailLength__m=cfg.rasaero_sim.rail_length_m,
        launchsiteTemperature__degC=cfg.rasaero_sim.temperature_deg_c,
        windSpeed__m_s=cfg.rasaero_sim.wind_speed_m_s,
    )

    rasaero_data_dir = cfg.vehicle_yaml_dir / "rasaero-data"
    rasaero_data_dir.mkdir(exist_ok=True)

    cdx1_path = str(cfg.cdx1_path)
    aeroplots_path = str(rasaero_data_dir / "aeroplots.csv")
    flight_sim_path = str(rasaero_data_dir / "flight-simulation.csv")

    ra = RASAero(cdx1_path, flight_sim_path, flight_sim_path, aeroplots_path)
    try:
        ra.exportRocketDefinition(rocket, simulation)
        click.echo(f"CDX1 written to {cfg.cdx1_path}")

        # --- Flight simulation first (informs aeroplot export parameters) ---
        ra.exportFlightSimulation(time_base)
        click.echo(f"Flight simulation exported to {flight_sim_path}")

        if cfg.flight_sim_output_path:
            ra.reformatFlightSimulation(str(cfg.flight_sim_output_path))
            click.echo(f"Flight simulation (SI) written to {cfg.flight_sim_output_path}")

        # --- Derive aeroplot export parameters from the flight envelope ---
        max_alt, max_mach_sim = _read_flight_envelope(cfg.flight_sim_output_path)
        max_mach = float(math.ceil(max_mach_sim * 1.2))
        max_altitude = max_alt * 1.2
        # ~20 altitude steps, rounded to a clean spacing
        altitude_step = max(500.0, round(max_altitude / 20 / 500) * 500)
        max_altitude = math.ceil(max_altitude / altitude_step) * altitude_step

        click.echo(f"Flight envelope: apogee {max_alt:.0f} m, peak Mach {max_mach_sim:.2f}")
        click.echo(f"Export grid: 0–{max_altitude:.0f} m (step {altitude_step:.0f} m), "
                    f"Mach cap {max_mach:.0f}")

        if not aeroplots_convert:
            altitudes = list(range(0, int(max_altitude) + 1, int(altitude_step)))
            ra.exportAeroPlots(altitudes)
            click.echo(f"Aeroplots exported to {rasaero_data_dir}")
    except (Exception, KeyboardInterrupt):
        click.echo("\nClosing RASAero II...")
        RASAero.killAll()
        raise
    finally:
        RASAero.killAll()

    # --- Conversion ---
    from convert import convert
    convert(cfg, max_mach=max_mach)
    click.echo(f"Aero tables written to {cfg.aero_tables_dir}")


@main.command("write-cdx1")
@click.argument("simulation_yaml", type=click.Path(exists=True, path_type=Path))
def write_cdx1(simulation_yaml: Path) -> None:
    """Generate a CDX1 file from the vehicle and simulation config."""
    cfg = load_config(simulation_yaml)

    from automation import Simulation, RASAero

    rocket = _build_rocket(cfg)

    simulation = Simulation(
        modifiedBarrowmanFlag=cfg.rasaero_sim.modified_barrowman,
        turbulenceFlag=cfg.rasaero_sim.turbulence,
        launchsiteElevation__m=cfg.rasaero_sim.elevation_m,
        launchInclination__deg=cfg.rasaero_sim.inclination_deg,
        launchRailLength__m=cfg.rasaero_sim.rail_length_m,
        launchsiteTemperature__degC=cfg.rasaero_sim.temperature_deg_c,
        windSpeed__m_s=cfg.rasaero_sim.wind_speed_m_s,
    )

    rasaero_data_dir = cfg.vehicle_yaml_dir / "rasaero-data"
    rasaero_data_dir.mkdir(exist_ok=True)

    cdx1_path = str(cfg.cdx1_path)
    dummy = str(rasaero_data_dir / "dummy.csv")

    ra = RASAero(cdx1_path, dummy, dummy, dummy)
    ra.exportRocketDefinition(rocket, simulation)
    click.echo(f"CDX1 written to {cfg.cdx1_path}")
