"""Convert an existing RASAero II CDX1 file into pyrasaero input YAMLs.

This is the inverse of ``RASAero.exportRocketDefinition``: it reads the
imperial values in a CDX1 and writes

  * a vehicle YAML (geometry, mass, recovery, RASAero properties), and
  * a simulation YAML (launch site, rail, RASAero flags) that points to it.

pyrasaero models a fixed layout (nosecone, body tube, boattail with fins
on it, single stage).  Anything else in the CDX1 is simplified, and each
simplification is reported with a warning.
"""

from __future__ import annotations

import warnings
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

IN_TO_MM = 25.4
FT_TO_M = 0.3048
LB_TO_KG = 0.453592


def _num(parent: ET.Element | None, tag: str, default: float | None = None) -> float | None:
    if parent is None:
        return default
    el = parent.find(tag)
    if el is None or el.text is None or el.text.strip() == "":
        return default
    return float(el.text)


def _text(parent: ET.Element | None, tag: str, default: str | None = None) -> str | None:
    if parent is None:
        return default
    el = parent.find(tag)
    if el is None or el.text is None:
        return default
    return el.text.strip()


def _bool(parent: ET.Element | None, tag: str, default: bool = False) -> bool:
    value = _text(parent, tag)
    if value is None:
        return default
    return value.lower() == "true"


def _mm(inches: float) -> float:
    return round(inches * IN_TO_MM, 3)


def _m(feet: float) -> float:
    return round(feet * FT_TO_M, 3)


def cdx1_to_yaml(cdx1_path: Path, out_dir: Path) -> tuple[Path, Path]:
    """Read *cdx1_path* and write vehicle and simulation YAMLs into *out_dir*.

    Returns ``(vehicle_yaml_path, simulation_yaml_path)``.
    """
    cdx1_path = Path(cdx1_path).resolve()
    root = ET.parse(cdx1_path).getroot()
    design = root.find("RocketDesign")
    if design is None:
        raise ValueError(f"{cdx1_path.name} has no <RocketDesign> section")

    # --- Components ---------------------------------------------------------
    nose = design.find("NoseCone")
    if nose is None:
        raise ValueError("CDX1 has no NoseCone")

    body_tubes = design.findall("BodyTube")
    if not body_tubes:
        raise ValueError("CDX1 has no BodyTube")
    if len(body_tubes) > 1:
        warnings.warn(
            f"{len(body_tubes)} body tubes found; pyrasaero models one, "
            "so their lengths have been summed"
        )
    body_len_in = sum(_num(bt, "Length", 0.0) for bt in body_tubes)
    last_tube = body_tubes[-1]

    if design.find("Booster") is not None:
        warnings.warn(
            "Booster stage(s) ignored; pyrasaero only models the sustainer"
        )

    body_dia_in = _num(nose, "Diameter")

    boattail = design.find("BoatTail")
    if boattail is not None:
        bt_len_in = _num(boattail, "Length", 0.0)
        bt_aft_in = _num(boattail, "RearDiameter", body_dia_in)
    else:
        # RASAero also stores the boattail on the last body tube
        bt_len_in = _num(last_tube, "BoattailLength", 0.0)
        bt_aft_in = _num(last_tube, "BoattailRearDiameter", 0.0) or body_dia_in
    if bt_len_in <= 0:
        warnings.warn(
            "No boattail in the CDX1. pyrasaero needs one: set "
            "components.boattail.length_mm to a small non-zero value (and "
            "aft_diameter_mm = body diameter) in the vehicle YAML"
        )

    # Fins: prefer ones on the boattail, else on the last body tube
    fin = boattail.find("Fin") if boattail is not None else None
    fin_on_body_tube = False
    if fin is None:
        for bt in reversed(body_tubes):
            fin = bt.find("Fin")
            if fin is not None:
                fin_on_body_tube = True
                break
    if fin is None:
        raise ValueError("CDX1 has no fins on the sustainer")

    chord_in = _num(fin, "Chord")
    # RASAero fin Location = distance from parent's aft end to fin root LE.
    # pyrasaero puts fins on the boattail with aft_offset measured from the
    # boattail's aft end to the fin trailing edge.
    aft_offset_in = _num(fin, "Location") - chord_in
    if fin_on_body_tube:
        aft_offset_in += bt_len_in
        if bt_len_in > 0:
            warnings.warn(
                "Fins are on the body tube in the CDX1; pyrasaero puts them "
                "on the boattail. Their position has been kept, but check the "
                "generated CDX1 looks right in RASAero"
            )

    # --- Mass / motor -------------------------------------------------------
    sim = root.find("SimulationList/Simulation")
    if sim is None:
        raise ValueError("CDX1 has no simulation (motor, launch weight, CG)")
    motor = _text(sim, "SustainerEngine")
    if not motor:
        raise ValueError("CDX1 simulation has no sustainer motor selected")
    nozzle_in = _num(sim, "SustainerNozzleDiameter") or _num(design, "SustainerNozzle", 0.0)

    # --- Recovery -----------------------------------------------------------
    rec = root.find("Recovery")
    recovery: dict = {}
    if rec is not None and _bool(rec, "Event1"):
        recovery["drogue"] = {
            "cd": _num(rec, "CD1"),
            "diameter_mm": _mm(_num(rec, "Size1")),
            "threshold": "apogee",
        }
        if (_text(rec, "EventType1") or "").lower() != "apogee":
            warnings.warn("Drogue event is not 'Apogee'; pyrasaero always deploys it at apogee")
    if rec is not None and _bool(rec, "Event2"):
        recovery["main"] = {
            "cd": _num(rec, "CD2"),
            "diameter_mm": _mm(_num(rec, "Size2")),
            "threshold": _m(_num(rec, "Altitude2")),
        }

    vehicle = {
        "body_diameter_mm": _mm(body_dia_in),
        "nozzle_diameter_mm": _mm(nozzle_in),
        "components": {
            "nosecone": {
                "shape": _text(nose, "Shape"),
                "length_mm": _mm(_num(nose, "Length")),
                "tip_radius_mm": _mm(_num(nose, "BluntRadius", 0.0)),
            },
            "body_tube": {"length_mm": _mm(body_len_in)},
            "boattail": {
                "length_mm": _mm(bt_len_in),
                "aft_diameter_mm": _mm(bt_aft_in),
            },
            "fins": {
                "count": int(_num(fin, "Count")),
                "span_mm": _mm(_num(fin, "Span")),
                "root_chord_mm": _mm(chord_in),
                "tip_chord_mm": _mm(_num(fin, "TipChord")),
                "sweep_distance_mm": _mm(_num(fin, "SweepDistance")),
                "aft_offset_mm": _mm(aft_offset_in),
                "airfoil_section": _text(fin, "AirfoilSection"),
                "thickness_mm": _mm(_num(fin, "Thickness")),
                "leading_edge_radius_mm": _mm(_num(fin, "LERadius", 0.0)),
            },
        },
        "mass": {
            "wet_mass_kg": round(_num(sim, "SustainerLaunchWt") * LB_TO_KG, 4),
            "wet_cg_mm": _mm(_num(sim, "SustainerCG")),
        },
        "rasaero": {
            "surface_finish": _text(design, "Surface"),
            "color": _text(nose, "Color", "Black"),
            "motor": motor,
        },
    }
    if recovery:
        vehicle["recovery"] = recovery

    # --- Simulation ---------------------------------------------------------
    site = root.find("LaunchSite")
    temp_f = _num(site, "Temperature")
    vehicle_name = f"{cdx1_path.stem}-vehicle"
    simulation = {
        "vehicle": f"{vehicle_name}.yaml",
        "site": {
            "elevation": _m(_num(site, "Altitude", 0.0)),
            "temperature": round((temp_f - 32) * 5 / 9, 2) if temp_f else 15,
        },
        "launch": {
            "rail": {
                "length": _m(_num(site, "RodLength", 0.0)),
                "inclination": round(90 - _num(site, "RodAngle", 0.0), 3),
            },
        },
        "verification": {"reference_trajectory": "rasaero-trajectory.csv"},
        "rasaero": {
            "modified_barrowman": _bool(design, "ModifiedBarrowman", True),
            "turbulence": _bool(design, "Turbulence", False),
        },
    }
    if simulation["launch"]["rail"]["length"] <= 0:
        warnings.warn("Launch rail length is 0 in the CDX1; set launch.rail.length in the simulation YAML")

    # --- Write --------------------------------------------------------------
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    vehicle_path = out_dir / f"{vehicle_name}.yaml"
    sim_path = out_dir / f"{cdx1_path.stem}-sim.yaml"

    # pyrasaero writes <vehicle stem>.CDX1 next to the vehicle YAML; make
    # sure that can never overwrite the source file.
    if (out_dir / f"{vehicle_name}.CDX1").resolve() == cdx1_path:
        raise ValueError("Output location would overwrite the source CDX1")

    header = f"# Generated by pyrasaero import-cdx1 from {cdx1_path.name}\n"
    for path, data in ((vehicle_path, vehicle), (sim_path, simulation)):
        with path.open("w", encoding="utf-8") as fh:
            fh.write(header)
            yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)

    return vehicle_path, sim_path
