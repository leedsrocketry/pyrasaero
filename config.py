"""Configuration loading for pyrasaero.

Reads a simulation YAML (shared with LFS), follows the vehicle YAML
reference, and builds a unified config for pyrasaero operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VehicleComponents:
    """Component geometry from the shared vehicle YAML."""

    body_diameter_mm: float
    nozzle_diameter_mm: float
    nosecone_shape: str
    nosecone_length_mm: float
    nosecone_tip_radius_mm: float
    body_tube_length_mm: float
    boattail_length_mm: float
    boattail_aft_diameter_mm: float
    fin_count: int
    fin_span_mm: float
    fin_root_chord_mm: float
    fin_tip_chord_mm: float
    fin_sweep_distance_mm: float
    fin_aft_offset_mm: float
    fin_airfoil_section: str
    fin_thickness_mm: float
    fin_leading_edge_radius_mm: float

    @property
    def length_mm(self) -> float:
        """Total vehicle length [mm] — sum of component lengths."""
        return self.nosecone_length_mm + self.body_tube_length_mm + self.boattail_length_mm


@dataclass(frozen=True)
class VehicleMass:
    """Mass fields from the shared vehicle YAML."""

    wet_mass_kg: float
    wet_cg_mm: float


@dataclass(frozen=True)
class RasaeroVehicle:
    """RASAero vehicle properties from the vehicle YAML."""

    surface_finish: str
    color: str
    motor: str  # RASAero motor name


@dataclass(frozen=True)
class RasaeroSimulation:
    """RASAero simulation settings — rasaero-only flags + existing LFS fields."""

    modified_barrowman: bool
    turbulence: bool
    elevation_m: float
    inclination_deg: float
    rail_length_m: float
    temperature_deg_c: float
    wind_speed_m_s: float


@dataclass(frozen=True)
class PyrasaeroConfig:
    """Top-level config combining vehicle YAML and simulation YAML."""

    components: VehicleComponents
    mass: VehicleMass
    rasaero_vehicle: RasaeroVehicle
    rasaero_sim: RasaeroSimulation
    vehicle_yaml_dir: Path
    aero_tables_dir: Path
    cdx1_path: Path


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(simulation_yaml_path: Path) -> PyrasaeroConfig:
    """Parse a simulation YAML, follow the vehicle reference, and build config.

    Parameters
    ----------
    simulation_yaml_path
        Path to the simulation YAML (e.g. cape-wrath.yaml).

    Returns
    -------
    PyrasaeroConfig
    """
    sim_path = Path(simulation_yaml_path).resolve()
    sim_dir = sim_path.parent

    with sim_path.open("r", encoding="utf-8") as fh:
        sim_raw = yaml.safe_load(fh)

    # --- Resolve and read vehicle YAML ---
    vehicle_rel = sim_raw["vehicle"]
    vehicle_path = (sim_dir / vehicle_rel).resolve()
    vehicle_dir = vehicle_path.parent

    with vehicle_path.open("r", encoding="utf-8") as fh:
        veh_raw = yaml.safe_load(fh)

    # --- Components ---
    comp = veh_raw["components"]
    nc = comp["nosecone"]
    bt = comp["body_tube"]
    tail = comp["boattail"]
    fins = comp["fins"]

    components = VehicleComponents(
        body_diameter_mm=float(veh_raw["body_diameter_mm"]),
        nozzle_diameter_mm=float(veh_raw["nozzle_diameter_mm"]),
        nosecone_shape=str(nc["shape"]),
        nosecone_length_mm=float(nc["length_mm"]),
        nosecone_tip_radius_mm=float(nc["tip_radius_mm"]),
        body_tube_length_mm=float(bt["length_mm"]),
        boattail_length_mm=float(tail["length_mm"]),
        boattail_aft_diameter_mm=float(tail["aft_diameter_mm"]),
        fin_count=int(fins["count"]),
        fin_span_mm=float(fins["span_mm"]),
        fin_root_chord_mm=float(fins["root_chord_mm"]),
        fin_tip_chord_mm=float(fins["tip_chord_mm"]),
        fin_sweep_distance_mm=float(fins["sweep_distance_mm"]),
        fin_aft_offset_mm=float(fins["aft_offset_mm"]),
        fin_airfoil_section=str(fins["airfoil_section"]),
        fin_thickness_mm=float(fins["thickness_mm"]),
        fin_leading_edge_radius_mm=float(fins["leading_edge_radius_mm"]),
    )

    # --- Mass ---
    mass_raw = veh_raw["mass"]
    mass = VehicleMass(
        wet_mass_kg=float(mass_raw["wet_mass_kg"]),
        wet_cg_mm=float(mass_raw["wet_cg_mm"]),
    )

    # --- RASAero vehicle properties ---
    ra_veh = veh_raw["rasaero"]
    rasaero_vehicle = RasaeroVehicle(
        surface_finish=str(ra_veh["surface_finish"]),
        color=str(ra_veh["color"]),
        motor=str(ra_veh["motor"]),
    )

    # --- RASAero simulation settings ---
    ra_sim = sim_raw.get("rasaero", {})
    site = sim_raw.get("site", {})
    launch = sim_raw.get("launch", {})
    rail = launch.get("rail", {})
    surface_wind = launch.get("surface_wind", {})

    inclination_raw = rail.get("inclination", 90)
    inclination = 90.0 if inclination_raw == "auto" else float(inclination_raw)

    rasaero_sim = RasaeroSimulation(
        modified_barrowman=bool(ra_sim.get("modified_barrowman", True)),
        turbulence=bool(ra_sim.get("turbulence", False)),
        elevation_m=float(site.get("elevation", 0)),
        inclination_deg=inclination,
        rail_length_m=float(rail["length"]),
        temperature_deg_c=float(site.get("temperature", 15)),
        wind_speed_m_s=float(surface_wind.get("speed_ms", 0)),
    )

    # --- Output paths ---
    aero_tables_dir = vehicle_dir / "aero-tables"
    cdx1_path = vehicle_dir / f"{vehicle_path.stem}.CDX1"

    return PyrasaeroConfig(
        components=components,
        mass=mass,
        rasaero_vehicle=rasaero_vehicle,
        rasaero_sim=rasaero_sim,
        vehicle_yaml_dir=vehicle_dir,
        aero_tables_dir=aero_tables_dir,
        cdx1_path=cdx1_path,
    )
