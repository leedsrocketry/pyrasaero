import sys
import pandas as pd
import xml.etree.ElementTree as ET
import keyboard
import shutil
from PIL import Image
from time import sleep
from pywinauto.application import Application
from pywinauto import Desktop
import numpy as np
import os

RASAeroPath = "C:\\Program Files (x86)\\RASAero II\\RASAero II.exe"

class Simulation():
    def __init__(self,
                 modifiedBarrowmanFlag, turbulenceFlag, 
                 launchsiteElevation__m,
                 launchInclination__deg, 
                 launchRailLength__m,
                 launchsiteTemperature__degC,
                 windSpeed__m_s):
        self.rASAeroModifiedBarrowmanFlag = modifiedBarrowmanFlag
        self.rASAeroTurbulenceFlag = turbulenceFlag
        self.launchsiteElevation__m = launchsiteElevation__m
        self.launchInclination__deg = launchInclination__deg
        self.launchRailLength__m = launchRailLength__m
        self.launchsiteTemperature__degC = launchsiteTemperature__degC
        self.windSpeed__m_s = windSpeed__m_s

class Rocket():
    def __init__(self,
                 surfaceFinish,
                 motor,
                 loadedMass__kg,
                 nozzleDiameter__mm,
                 loadedCoM__m,
                 noseconeShape,
                 noseconeLength__mm,
                 bodyDiameter__mm,
                 noseconeTipRadius__mm,
                 bodyTubeLength__mm,
                 boattailLength__mm,
                 boattailAftDiameter__mm,
                 finRootChord__mm,
                 finAftOffset__mm,
                 finAirfoilSection,
                 finCount,
                 finSpan__mm,
                 finSweepDistance__mm,
                 finTipChord__mm,
                 finLeadingEdgeRadius__mm,
                 finThickness__mm=None,
                 finRootThickness__mm=None,
                 finTipThickness__mm=None,
                 finLeadingEdgeLength__mm=None,
                 loadedMoI__kgm2=None,
                 drogueCD=None,
                 drogueArea__m2=None,
                 drogueDiameter__mm=None,
                 mainCD=None,
                 mainArea__m2=None,
                 mainDiameter__mm=None,
                 mainParachuteAltitude__m=None,
                 color="Black"
    ):
        self.surfaceFinish = surfaceFinish
        self.motor = motor
        self.loadedMass__kg = loadedMass__kg
        self.nozzleDiameter__mm = nozzleDiameter__mm
        self.loadedCoM__m = loadedCoM__m
        self.noseconeShape = noseconeShape
        self.noseconeLength__mm = noseconeLength__mm
        self.bodyDiameter__mm = bodyDiameter__mm
        self.noseconeTipRadius__mm = noseconeTipRadius__mm
        self.bodyTubeLength__mm = bodyTubeLength__mm
        self.boattailLength__mm = boattailLength__mm
        self.boattailAftDiameter__mm = boattailAftDiameter__mm
        self.finRootChord__mm = finRootChord__mm
        self.finAftOffset__mm = finAftOffset__mm
        self.finAirfoilSection = finAirfoilSection
        self.finCount = finCount
        self.finSpan__mm = finSpan__mm
        self.finSweepDistance__mm = finSweepDistance__mm
        self.finTipChord__mm = finTipChord__mm
        self.finLeadingEdgeRadius__mm = finLeadingEdgeRadius__mm
        self.finThickness__mm = finThickness__mm
        self.finRootThickness__mm = finRootThickness__mm
        self.finTipThickness__mm = finTipThickness__mm
        self.finLeadingEdgeLength__mm = finLeadingEdgeLength__mm
        self.loadedMoI__kgm2 = loadedMoI__kgm2
        self.drogueCD = drogueCD
        self.drogueArea__m2 = drogueArea__m2
        self.drogueDiameter__mm = drogueDiameter__mm
        self.mainCD = mainCD
        self.mainArea__m2 = mainArea__m2
        self.mainDiameter__mm = mainDiameter__mm
        self.mainParachuteAltitude__m = mainParachuteAltitude__m
        self.color = color

        if self.finThickness__mm is None:
            self.finThickness__mm = (self.finRootThickness__mm + self.finTipThickness__mm) / 2.0

        if self.finLeadingEdgeLength__mm is None:
            self.finLeadingEdgeLength__mm = (self.finRootChord__mm + self.finTipChord__mm) / 4.0
        
        # Component start positions from nose tip [mm].
        # Index 0 = body tube start, 1 = boattail start, 2 = vehicle aft end.
        self.runningLength__mm = (
            self.noseconeLength__mm,
            self.noseconeLength__mm + bodyTubeLength__mm,
            self.noseconeLength__mm + bodyTubeLength__mm + boattailLength__mm,
        )
        
class RASAero():
    window = None
    rocket = None
    simulation = None
    # Aft-to-fore: each entry is exported (as a cumulative assembly), then
    # stripped from the working CDX1 before the next.  The aftmost component
    # in each assembly gives its name to the exported CSV.
    aftComponentOrder = ("Fin", "BoatTail", "BodyTube", "NoseCone")
    guiShortDelay__s = 0.5
    guiLongDelay__s = 1.0
    simulationDelay__s = 2.0
    simulationDataDelay__s = 3.0

    @staticmethod
    def killAll():
        """Kill all running RASAero II processes."""
        import subprocess
        subprocess.run(
            ["taskkill", "/F", "/IM", "RASAero II.exe"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def __init__(self, rocketDefinitionPath, rocketIllustrationFullPath, flightSimulationFullPath, aeroPlotsFullPath):
        self.rocketDefinitionPath = rocketDefinitionPath
        self.rocketIllustrationFullPath = rocketIllustrationFullPath
        self.flightSimulationFullPath = flightSimulationFullPath
        self.aeroPlotsFullPath = aeroPlotsFullPath
    
    @staticmethod
    def _rnd(value: float, ndigits: int = 5) -> float:
        """Round to *ndigits* significant figures."""
        if value == 0:
            return 0
        from math import log10, floor
        magnitude = floor(log10(abs(value)))
        return round(value, ndigits - 1 - magnitude)

    def mm2in(self, mm): return self._rnd(mm / 25.4)
    def m2ft(self, m): return self._rnd(m * 3.28084)
    def kg2lbs(self, kg): return self._rnd(kg * 2.20462)
    def ms2mph(self, ms): return self._rnd(ms * 2.23694)
    def degC2degF(self, degC): return self._rnd((degC * (9 / 5)) + 32)
    def ft2m(self, value): return float(value) * 0.3048 
    def degF2degC(self, value): return (float(value) - 32) * 5/9 
    def mph2ms(self, value): return float(value) * 0.44704 
    def lbs2kg(self, value): return float(value) * 0.453592 
    def in2mm(self, value): return float(value) * 25.4 
    def in2m(self, value): return float(value) * 0.0254

    # TODO: Use this a bit more?
    def retry(self, function, attempts=3):
        for attempt in range(attempts):
            sleep(self.guiLongDelay__s)
            try:
                return function()

            except Exception as e:
                if attempt == attempts - 1:
                    print("MAXIMUM RASAERO ATTEMPTS REACHED. EXITING.")
                    sys.exit(1)
    
    def getElementText(self, parent, tag):
        element = parent.find(tag)
        return element.text if element is not None else None
    
    def addElement(self, parent, tag, text):
        element = ET.SubElement(parent, tag)
        element.text = str(text)
        return element
    
    def writeCDX1File(self, root, fullPath):
        tree = ET.ElementTree(root)
        ET.indent(tree, space=" ")
        tree.write(fullPath, encoding="unicode", xml_declaration=False)
    
    def removeCDX1Element(self, fullPath, element):
        tree = ET.parse(fullPath)
        root = tree.getroot()

        for parent in root.iter():
            children_to_remove = [child for child in parent if child.tag == element]

            for child in children_to_remove:
                parent.remove(child)
        
        self.writeCDX1File(root, fullPath)
    
    def openWindow(self):
        # If window is not already open
        if not self.window:
            rasaero = Application(backend="uia").start(RASAeroPath).connect(title="RASAero II ", timeout=10)
            self.window = rasaero.top_window()

            # Give window some time to load
            sleep(self.guiLongDelay__s)
    
    def closeWindow(self):
        # Only if window is already open
        if self.window:
            # Close main window
            keyboard.send("alt + f4")
            sleep(self.guiShortDelay__s)

            # Don't save changes
            keyboard.send("tab")
            sleep(self.guiShortDelay__s)
            keyboard.send("enter")

            self.window = None
    
    def openFile(self, fullPath):
        # Open dialog
        self.openWindow()
        self.window.set_focus()
        self.window.type_keys("^o")

        # Wait for the dialog to appear
        dlg = self.retry(lambda: Desktop(backend="uia").window(title_re="RASAero II"))

        # Edit box
        file_name_box = dlg.child_window(auto_id="1148", control_type="Edit")
        file_name_box.set_edit_text(fullPath)

        # Open button
        open_btn = dlg.child_window(auto_id="1", control_type="Button")
        open_btn.click_input()

        # Give window some time to load
        sleep(self.guiShortDelay__s)
        self.open = True

    def exportFigure(self):
        # Open file, if not already open
        self.openFile(self.rocketDefinitionPath)

        # Screenshot the window
        self.window.capture_as_image().save(self.rocketIllustrationFullPath)
        
        screenshot = Image.open(self.rocketIllustrationFullPath)
        width, height = screenshot.size
        
        left = width * 0.02
        right = width - left
        top = height * 0.4
        bottom = height - (height / 7)
        
        figure = screenshot.crop((left, top, right, bottom))
        figure.save(self.rocketIllustrationFullPath)
    
    def exportFlightSimulation(self, timeBase: float = 0.01):
        """Automate RASAero II to run a flight simulation and export data to CSV.

        Parameters
        ----------
        timeBase
            Desired export time step in seconds.  Snapped down to the nearest
            valid RASAero option: 0.01, 0.1, 0.5, or 1.0.
        """
        # --- Snap time base to nearest valid value ---
        validBases = [0.01, 0.1, 0.5, 1.0]
        snapped = validBases[0]
        for v in validBases:
            if v <= timeBase:
                snapped = v
        if snapped != timeBase:
            print(f"Time base {timeBase} snapped to {snapped}")

        downPresses = {0.01: 0, 0.1: 1, 0.5: 2, 1.0: 3}[snapped]

        # Delete any existing flight simulation CSV to avoid overwrite pop-ups
        if os.path.isfile(self.flightSimulationFullPath):
            os.remove(self.flightSimulationFullPath)

        # 1. Open the CDX1 file
        self.openFile(self.rocketDefinitionPath)

        # 2. Click "Flight Simulation" button
        dlg = self.retry(lambda: Desktop(backend="uia").window(title_re="RASAero II"))
        btn = dlg.child_window(title_re="Flight Sim", control_type="Button")
        btn.click_input()
        sleep(self.guiLongDelay__s)

        # 3. Run simulation: Alt → right → down → down → enter
        keyboard.send("alt")
        sleep(self.guiShortDelay__s)
        keyboard.send("right")
        sleep(self.guiShortDelay__s)
        keyboard.send("down")
        sleep(self.guiShortDelay__s)
        keyboard.send("down")
        sleep(self.guiShortDelay__s)
        keyboard.send("enter")

        # 4–5. Navigate to "View Data" button while simulation runs.
        #       The simulation completes before we finish navigating.
        for _ in range(7):
            keyboard.send("right")
            sleep(self.guiShortDelay__s)

        # 6. Click "View Data"
        # The button is embedded in a DataGridView; pywinauto cannot
        # reliably locate it, but space activates the focused cell.
        keyboard.send("space")

        # 7. Wait for simulation data window (slower to open than other windows)
        sleep(self.simulationDataDelay__s)

        # 8. Export to CSV: alt+f → right → enter
        keyboard.send("alt+f")
        sleep(self.guiShortDelay__s)
        keyboard.send("right")
        sleep(self.guiShortDelay__s)
        keyboard.send("enter")
        sleep(self.guiShortDelay__s)

        # 9. Select time base
        for _ in range(downPresses):
            keyboard.send("down")
            sleep(self.guiShortDelay__s)

        # 10. Confirm time base: tab → enter
        keyboard.send("tab")
        sleep(self.guiShortDelay__s)
        keyboard.send("enter")
        sleep(self.guiLongDelay__s)

        # 11. Enter file path in save dialog and save
        keyboard.write(self.flightSimulationFullPath)
        keyboard.send("enter")
        sleep(self.guiLongDelay__s)

        # 12. Close data window, then flight sim window
        keyboard.send("alt+f4")
        sleep(self.guiShortDelay__s)
        keyboard.send("alt+f4")
        sleep(self.guiShortDelay__s)
        # Flight sim window asks to save changes — don't save
        keyboard.send("tab")
        sleep(self.guiShortDelay__s)
        keyboard.send("enter")

        self.window = None

    def reformatFlightSimulation(self, outputPath: str):
        """Read the raw RASAero flight simulation CSV, convert to SI units with
        lowercase snake_case headers, and write to *outputPath*.

        The raw RASAero export uses entirely imperial units.  This method
        converts every column to SI and renames headers to match the LFS
        convention (lowercase snake_case with units).
        """
        df = pd.read_csv(self.flightSimulationFullPath)

        # Unit conversions (imperial → SI)
        lbf_to_n = 4.44822
        lb_to_kg = 0.453592
        in_to_m = 0.0254
        ft_to_m = 0.3048

        conversions: dict[str, tuple[str, float]] = {
            "Time (sec)":            ("time_s",                        1.0),
            "Stage":                 ("stage",                         1.0),
            "Stage Time (sec)":      ("stage_time_s",                  1.0),
            "Mach Number":           ("mach",                          1.0),
            "Angle of Attack (deg)": ("aoa_deg",                       1.0),
            "CD":                    ("cd",                            1.0),
            "Thrust (lb)":           ("thrust_n",                      lbf_to_n),
            "Weight (lb)":           ("mass_kg",                       lb_to_kg),
            "Drag (lb)":             ("drag_n",                        lbf_to_n),
            "Lift (lb)":             ("lift_n",                        lbf_to_n),
            "CG (in)":              ("cg_m",                          in_to_m),
            "CP (in)":              ("cp_m",                          in_to_m),
            "Stability Margin (cal)": ("stability_margin_cal",        1.0),
            "Accel (ft/sec^2)":      ("acceleration_ms2",             ft_to_m),
            "Accel-V (ft/sec^2)":    ("acceleration_vertical_ms2",    ft_to_m),
            "Accel-H (ft/sec^2)":    ("acceleration_horizontal_ms2",  ft_to_m),
            "Velocity (ft/sec)":     ("velocity_ms",                  ft_to_m),
            "Vel-V (ft/sec)":        ("velocity_vertical_ms",         ft_to_m),
            "Vel-H (ft/sec)":        ("velocity_horizontal_ms",       ft_to_m),
            "Pitch Attitude (deg)":  ("pitch_attitude_deg",           1.0),
            "Flight Path Angle (deg)": ("flight_path_angle_deg",      1.0),
            "Altitude (ft)":         ("altitude_m",                   ft_to_m),
            "Distance (ft)":         ("distance_m",                   ft_to_m),
        }

        out = pd.DataFrame()
        for raw_col, (new_col, factor) in conversions.items():
            if raw_col in df.columns:
                if factor == 1.0:
                    out[new_col] = df[raw_col]
                else:
                    out[new_col] = df[raw_col] * factor

        out.to_csv(outputPath, index=False)
    
    def exportAeroPlots(self, altitudes):
        # Delete any existing aeroplot CSVs to avoid overwrite pop-ups
        aero_dir = os.path.dirname(self.aeroPlotsFullPath)
        if os.path.isdir(aero_dir):
            for f in os.listdir(aero_dir):
                if f.lower().startswith("aeroplots") and f.lower().endswith(".csv"):
                    os.remove(os.path.join(aero_dir, f))

        # Make a working copy of the rocket definition
        base, extension = os.path.splitext(self.rocketDefinitionPath)
        workingPath = f"{base}-working{extension}"
        shutil.copy(self.rocketDefinitionPath, workingPath)
        
        def addMachAlt(fullPath, altitude__m):
            tree = ET.parse(workingPath)
            root = tree.getroot()

            machalt = ET.SubElement(root, "MachAlt")
            [self.addElement(machalt, "Item", f"{x}, {self.m2ft(altitude__m)}") for x in (0, 25)]

            self.writeCDX1File(root, fullPath)

        # NOTE: Order of components here *must* run aft-forward since
        #       RASAero can simualte just a nosecone but not just a fin
        for component in self.aftComponentOrder:
            for altitude in altitudes:
                # This is critical! RASAero must fully close to flush previous Mach-Alt settings!
                self.closeWindow()

                # Replace any exisiting Mach-Alt table
                self.removeCDX1Element(workingPath, "MachAlt")
                addMachAlt(workingPath, altitude)

                # Open file
                self.openFile(workingPath)

                # Open the "Aero Plots" window
                dlg = self.retry(lambda: Desktop(backend="uia").window(title_re="RASAero II"))
                open_btn = dlg.child_window(title_re="Aero Plots", control_type="Button")
                open_btn.click_input()

                # Give the "Aero Plots" window time to open before we look for buttons
                sleep(self.guiLongDelay__s)
                
                # Navigate File → Export → To CSV File via keyboard
                # (avoids resolution-dependent image matching)
                keyboard.send("alt+f")
                sleep(self.guiShortDelay__s)
                keyboard.send("e")
                sleep(self.guiShortDelay__s)
                keyboard.send("t")
                
                # Export the "Aero Plots" data
                base, extension = os.path.splitext(self.aeroPlotsFullPath)
                keyboard.write(f"{base}-{component.lower()}-{altitude:.0f}{extension}")
                keyboard.send("enter")
                
                # Close "Aero Plots" window
                keyboard.send("alt + f4")
                
                # Give the program some time to save the file
                sleep(self.guiLongDelay__s)
            
            # Remove component
            self.removeCDX1Element(workingPath, component)
        
        # Working CDX1 file has served its purpose. Delete.
        os.remove(workingPath)

    def exportRocketDefinition(self, rocket, simulation):
        self.rocket = rocket
        self.simulation = simulation

        # --- Document structure (order matches RASAero's own output) ---
        root = ET.Element("RASAeroDocument")
        self.addElement(root, "FileVersion", 2)

        design = ET.SubElement(root, "RocketDesign")

        # --- Components ---
        # NoseCone
        nosecone = ET.SubElement(design, "NoseCone")
        self.addElement(nosecone, "PartType", "NoseCone")
        self.addElement(nosecone, "Length", self.mm2in(rocket.noseconeLength__mm))
        self.addElement(nosecone, "Diameter", self.mm2in(rocket.bodyDiameter__mm))
        self.addElement(nosecone, "Shape", rocket.noseconeShape)
        self.addElement(nosecone, "BluntRadius", self.mm2in(rocket.noseconeTipRadius__mm))
        self.addElement(nosecone, "Location", 0)
        self.addElement(nosecone, "Color", rocket.color)

        # BodyTube
        body_tube = ET.SubElement(design, "BodyTube")
        self.addElement(body_tube, "PartType", "BodyTube")
        self.addElement(body_tube, "Length", self.mm2in(rocket.bodyTubeLength__mm))
        self.addElement(body_tube, "Diameter", self.mm2in(rocket.bodyDiameter__mm))
        self.addElement(body_tube, "Location", self.mm2in(rocket.runningLength__mm[0]))
        self.addElement(body_tube, "Color", rocket.color)

        # BoatTail
        boattail = ET.SubElement(design, "BoatTail")
        self.addElement(boattail, "PartType", "BoatTail")
        self.addElement(boattail, "Length", self.mm2in(rocket.boattailLength__mm))
        self.addElement(boattail, "Diameter", self.mm2in(rocket.bodyDiameter__mm))
        self.addElement(boattail, "RearDiameter", self.mm2in(rocket.boattailAftDiameter__mm))
        self.addElement(boattail, "Location", self.mm2in(rocket.runningLength__mm[1]))
        self.addElement(boattail, "Color", rocket.color)

        # Fin (nested inside BoatTail)
        fins = ET.SubElement(boattail, "Fin")
        self.addElement(fins, "Count", rocket.finCount)
        self.addElement(fins, "Chord", self.mm2in(rocket.finRootChord__mm))
        self.addElement(fins, "Span", self.mm2in(rocket.finSpan__mm))
        self.addElement(fins, "SweepDistance", self.mm2in(rocket.finSweepDistance__mm))
        self.addElement(fins, "TipChord", self.mm2in(rocket.finTipChord__mm))
        self.addElement(fins, "Thickness", self.mm2in(rocket.finThickness__mm))
        self.addElement(fins, "LERadius", self.mm2in(rocket.finLeadingEdgeRadius__mm))
        self.addElement(fins, "Location", self.mm2in(rocket.finRootChord__mm + rocket.finAftOffset__mm))
        self.addElement(fins, "AirfoilSection", rocket.finAirfoilSection)
        self.addElement(fins, "FX1", self.mm2in(rocket.finLeadingEdgeLength__mm))
        self.addElement(fins, "FX3", 0)

        # Design-level fields
        self.addElement(design, "Surface", rocket.surfaceFinish)
        self.addElement(design, "ModifiedBarrowman", self.simulation.rASAeroModifiedBarrowmanFlag)
        self.addElement(design, "Turbulence", self.simulation.rASAeroTurbulenceFlag)

        # --- LaunchSite ---
        launchsite = ET.SubElement(root, "LaunchSite")
        self.addElement(launchsite, "Altitude", self.m2ft(self.simulation.launchsiteElevation__m))
        self.addElement(launchsite, "Pressure", 29.53)
        self.addElement(launchsite, "RodAngle", self._rnd(90 - self.simulation.launchInclination__deg))
        self.addElement(launchsite, "RodLength", self.m2ft(self.simulation.launchRailLength__m))
        self.addElement(launchsite, "Temperature", self.degC2degF(self.simulation.launchsiteTemperature__degC))
        self.addElement(launchsite, "WindSpeed", self.ms2mph(self.simulation.windSpeed__m_s))

        # --- Recovery ---
        if rocket.drogueCD is not None or rocket.mainCD is not None:
            recovery = ET.SubElement(root, "Recovery")
            has_drogue = rocket.drogueCD is not None
            has_main = rocket.mainCD is not None

            # Drogue (device 1)
            self.addElement(recovery, "Altitude1", 1000)
            self.addElement(recovery, "DeviceType1", "Parachute")
            self.addElement(recovery, "Event1", has_drogue)
            self.addElement(recovery, "Size1",
                            self.mm2in(rocket.drogueDiameter__mm) if has_drogue else 0)
            self.addElement(recovery, "EventType1", "Apogee")
            self.addElement(recovery, "CD1", rocket.drogueCD if has_drogue else 0)

            # Main (device 2)
            main_alt_ft = self._rnd(self.m2ft(rocket.mainParachuteAltitude__m)) if has_main else 1000
            self.addElement(recovery, "Altitude2", main_alt_ft)
            self.addElement(recovery, "DeviceType2", "Parachute")
            self.addElement(recovery, "Event2", has_main)
            self.addElement(recovery, "Size2",
                            self.mm2in(rocket.mainDiameter__mm) if has_main else 0)
            self.addElement(recovery, "EventType2", "Altitude")
            self.addElement(recovery, "CD2", rocket.mainCD if has_main else 0)

        # --- Simulation ---
        sim_list = ET.SubElement(root, "SimulationList")
        sim_el = ET.SubElement(sim_list, "Simulation")
        self.addElement(sim_el, "SustainerEngine", rocket.motor)
        self.addElement(sim_el, "SustainerLaunchWt", self.kg2lbs(rocket.loadedMass__kg))
        self.addElement(sim_el, "SustainerNozzleDiameter", self.mm2in(rocket.nozzleDiameter__mm))
        self.addElement(sim_el, "SustainerCG", self.mm2in(rocket.loadedCoM__m * 1000))

        self.writeCDX1File(root, self.rocketDefinitionPath)
    
    def parseFlightSimulation(self):
        # Parse the rocket definition to create the simulation object, unless already loaded
        if self.simulation is None:
            self.parseRocketDefinition()
        
        dataframe = pd.read_csv(self.flightSimulationFullPath)

        # Unit conversion
        dataframe["Velocity (m/s)"] = dataframe["Velocity (ft/sec)"] * 0.3048 # ft/s to m
        dataframe["Altitude (m)"] = dataframe["Altitude (ft)"] * 0.3048     # ft to m
        dataframe["CM (m)"] = dataframe["CG (in)"].values * 0.0254          # in to m

        # Renaming columns
        dataframe = dataframe.rename(columns={"Time (sec)": "Time (s)", "Mach Number": "Mach"})

        self.simulation.dataframe = dataframe
        self.simulation.apogee__m = dataframe["Altitude (m)"].max()

        return self.simulation
    
    # parseAeroParameters and parseRocketDefinition removed —
    # YAML is now the source of truth; conversion is handled by convert.py.
