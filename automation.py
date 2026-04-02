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
                 mainCD=None,
                 mainArea__m2=None,
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
        self.mainCD = mainCD
        self.mainArea__m2 = mainArea__m2
        self.mainParachuteAltitude__m = mainParachuteAltitude__m
        self.color = color

        if self.finThickness__mm is None:
            self.finThickness__mm = (self.finRootThickness__mm + self.finTipThickness__mm) / 2.0

        if self.finLeadingEdgeLength__mm is None:
            self.finLeadingEdgeLength__mm = (self.finRootChord__mm + self.finTipChord__mm) / 4.0
        
        # Adjusted to 5 values to match your 5 components in aftComponentOrder
        self.runningLength__mm = (
        self.noseconeLength__mm,
        self.noseconeLength__mm + bodyTubeLength__mm,
        self.noseconeLength__mm + bodyTubeLength__mm + boattailLength__mm,
        self.noseconeLength__mm + bodyTubeLength__mm + boattailLength__mm + 10.0, # Placeholder for FinCan
        self.noseconeLength__mm + bodyTubeLength__mm + boattailLength__mm + 10.0  # Total length
)
        
class RASAero():
    window = None
    rocket = None
    simulation = None
    #aftComponentOrder = ("Fin", "BoatTail", "BodyTube", "NoseCone")
    aftComponentOrder = ("BoatTail", "Fin", "FinCan", "BodyTube", "NoseCone")
    guiShortDelay__s = 0.5
    guiLongDelay__s = 2.0

    def __init__(self, rocketDefinitionPath, rocketIllustrationFullPath, flightSimulationFullPath, aeroPlotsFullPath):
        self.rocketDefinitionPath = rocketDefinitionPath
        self.rocketIllustrationFullPath = rocketIllustrationFullPath
        self.flightSimulationFullPath = flightSimulationFullPath
        self.aeroPlotsFullPath = aeroPlotsFullPath
    
    def mm2in(self, mm): return mm / 25.4
    def m2ft(self, m): return m * 3.28084
    def kg2lbs(self, kg): return kg * 2.20462
    def ms2mph(self, ms): return ms * 2.23694
    def degC2degF(self, degC): return (degC * (9 / 5)) + 32
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
                
                #sleep(self.guiLongDelay__s)
    
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
            
            # Don"t save changes
            keyboard.send("tab")
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
        sleep(self.guiLongDelay__s)
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
    
    # TODO: Implement properly
    def exportFlightSimulation(self):
        return None
    
    def exportAeroPlots(self, altitudes):
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
                keyboard.write(f"{base}-{component}-{altitude:.0f}{extension}")
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
        
        # Document Setup
        root = ET.Element("RASAeroDocument")
        design = ET.SubElement(root, "RocketDesign")
        simulations = ET.SubElement(root, "SimulationList")
        simulation = ET.SubElement(simulations, "Simulation")
        launchsite = ET.SubElement(root, "LaunchSite")

        # Simulation Setup
        self.addElement(design, "ModifiedBarrowman", self.simulation.rASAeroModifiedBarrowmanFlag)
        self.addElement(design, "Turbulence", self.simulation.rASAeroTurbulenceFlag)
        self.addElement(launchsite, "Altitude", self.m2ft(self.simulation.launchsiteElevation__m))
        self.addElement(launchsite, "RodAngle", (90 - self.simulation.launchInclination__deg))
        self.addElement(launchsite, "RodLength", self.m2ft(self.simulation.launchRailLength__m))
        self.addElement(launchsite, "Temperature", self.degC2degF(self.simulation.launchsiteTemperature__degC))
        self.addElement(launchsite, "WindSpeed", self.ms2mph(self.simulation.windSpeed__m_s))
        
        # Rocket
        self.addElement(design, "Surface", self.rocket.surfaceFinish)
        self.addElement(simulation, "SustainerEngine", self.rocket.motor)
        self.addElement(simulation, "SustainerLaunchWt", self.kg2lbs(self.rocket.loadedMass__kg))
        self.addElement(simulation, "SustainerNozzleDiameter", self.mm2in(self.rocket.nozzleDiameter__mm))
        self.addElement(simulation, "SustainerCG", self.mm2in(self.rocket.loadedCoM__m * 1000))

        # Nosecone
        nosecone = ET.SubElement(design, "NoseCone")
        self.addElement(nosecone, "PartType", "NoseCone")
        self.addElement(nosecone, "Location", self.mm2in(rocket.runningLength__mm[0]))
        self.addElement(nosecone, "Color", self.rocket.color)
        self.addElement(nosecone, "Shape", self.rocket.noseconeShape)
        self.addElement(nosecone, "Length", self.mm2in(self.rocket.noseconeLength__mm))
        self.addElement(nosecone, "Diameter", self.mm2in(self.rocket.bodyDiameter__mm))
        self.addElement(nosecone, "BluntRadius", self.mm2in(self.rocket.noseconeTipRadius__mm))
        
        # Body Tube
        bodyTube = ET.SubElement(design, "BodyTube")
        self.addElement(bodyTube, "PartType", "BodyTube")
        self.addElement(bodyTube, "Location", self.mm2in(rocket.runningLength__mm[1]))
        self.addElement(bodyTube, "Color", rocket.color)
        self.addElement(bodyTube, "Length", self.mm2in(self.rocket.bodyTubeLength__mm))
        self.addElement(bodyTube, "Diameter", self.mm2in(self.rocket.bodyDiameter__mm))
        
        # Boattail
        boattail = ET.SubElement(design, "BoatTail")
        self.addElement(boattail, "PartType", "BoatTail")
        self.addElement(boattail, "Location", self.mm2in(rocket.runningLength__mm[2]))
        self.addElement(boattail, "Color", self.rocket.color)
        self.addElement(boattail, "Length", self.mm2in(self.rocket.boattailLength__mm))
        self.addElement(boattail, "Diameter", self.mm2in(self.rocket.bodyDiameter__mm))
        self.addElement(boattail, "RearDiameter", self.mm2in(self.rocket.boattailAftDiameter__mm))
        
        # Fins
        fins = ET.SubElement(boattail, "Fin")
        self.addElement(fins, "Location", self.mm2in(self.rocket.finRootChord__mm + self.rocket.finAftOffset__mm))
        self.addElement(fins, "Color", self.rocket.color)
        self.addElement(fins, "AirfoilSection", self.rocket.finAirfoilSection)
        self.addElement(fins, "Count", self.rocket.finCount)
        self.addElement(fins, "Chord", self.mm2in(self.rocket.finRootChord__mm))
        self.addElement(fins, "Span", self.mm2in(self.rocket.finSpan__mm))
        self.addElement(fins, "SweepDistance", self.mm2in(self.rocket.finSweepDistance__mm))
        self.addElement(fins, "TipChord", self.mm2in(self.rocket.finTipChord__mm))
        self.addElement(fins, "Thickness", self.mm2in(self.rocket.finThickness__mm))
        self.addElement(fins, "LERadius", self.mm2in(self.rocket.finLeadingEdgeRadius__mm))
        self.addElement(fins, "FX1", self.mm2in(self.rocket.finLeadingEdgeLength__mm))
        
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
