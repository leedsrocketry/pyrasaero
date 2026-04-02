from colored import Fore, Back, Style
from pyrasaero.automation import Simulation, Rocket, RASAero
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np
import os
import argparse
import rocketpy
import glob
from rocketpy.mathutils import Function
from texttable import Texttable
from ambiance import Atmosphere
import pandas as pd

# TODO: Check these values
# Copy and paste this to replace the Motors dictionary in main.py

Motors = {
    "O3400-IM-P  (CTI)": rocketpy.SolidMotor(
                            thrust_source="o3400.eng",
                            dry_mass=5.5,
                            dry_inertia=((2246272.78024 * 1e-6), (2246272.78024 * 1e-6), (23099.21813 * 1e-6)),
                            nozzle_radius=0.07,
                            grain_number=6,
                            grain_separation=0.00079,
                            grain_density=(1.50350 / 0.00091),
                            grain_outer_radius=0.0425,
                            grain_initial_inner_radius=0.01745,
                            grain_initial_height=0.19,
                            grains_center_of_mass_position= 0.60487,
                            center_of_dry_mass_position=0.64437,
                            coordinate_system_orientation="nozzle_to_combustion_chamber",
                            nozzle_position=0
                        ),

    "N5800-CS  (CTI)": rocketpy.SolidMotor(
                            thrust_source="n5800.eng",
                            dry_mass=5.805,                   # Total Case (14.8kg) - Propellant (9.0kg)
                            dry_inertia=(0.12, 0.12, 0.01),   # Estimated for 98mm 6GXL hardware
                            nozzle_radius=0.038,              # ~76mm nozzle exit radius
                            grain_number=6,
                            grain_separation=0.001,           # Standard CTI grain spacer
                            grain_density=1815,               # C-Star propellant density
                            grain_outer_radius=0.044,         # Radius for 98mm motor
                            grain_initial_inner_radius=0.02,  # Initial core radius
                            grain_initial_height=0.18,        # Total propellant length divided by 6
                            grains_center_of_mass_position=0.62,
                            center_of_dry_mass_position=0.62,
                            coordinate_system_orientation="nozzle_to_combustion_chamber",
                            nozzle_position=0
                        )
}

# TODO: Review these values
"""
G2B2 = Rocket(
    surfaceFinish="Smooth Paint",
    motor="O3400-IM-P  (CTI)",
    loadedMass__kg=25,
    nozzleDiameter__mm=50,
    loadedCoM__m=1.300,
    noseconeShape="Von Karman Ogive",
    noseconeLength__mm=790,
    bodyDiameter__mm=130,
    noseconeTipRadius__mm=1,
    bodyTubeLength__mm=1500,
    boattailLength__mm=280,
    boattailAftDiameter__mm=104,
    finRootChord__mm=120,
    finAftOffset__mm=50,
    finAirfoilSection="Double Wedge",
    finCount=4,
    finSpan__mm=120,
    finSweepDistance__mm=90,
    finRootThickness__mm = 12,
    finTipThickness__mm = 6,
    finTipChord__mm=40,
    finLeadingEdgeRadius__mm=1,
    color="Orange",
    loadedMoI__kgm2 = 12,
    drogueCD = 0.97,
    drogueArea__m2 = np.pi * (0.9144 * 0.5 * 0.5)**2,
    mainCD = 2.2,
    mainArea__m2 = np.pi * (1.8288 * 0.5)**2,
    mainParachuteAltitude__m = 300
)
"""
# Simulation Parameters
SimulationCount = 1
CoefficientAltitudeStepover__m = 2000
LaunchDate = datetime.now()
LaunchSiteLatitude = 54
LaunchSiteLongitude = 43
LaunchHeading__deg = 0
MotorImpulseUncertainty__pct = 0.08
MotorBurnTimeUncertainty__pct = 0.08
InclinationUncertainty__deg = 2
HeadingUncertainty__deg = 2

HighAltitudeSimulation = Simulation(
    modifiedBarrowmanFlag=True,
    turbulenceFlag=False,
    launchsiteElevation__m=0,
    launchInclination__deg=85,
    launchRailLength__m=4,
    launchsiteTemperature__degC=5,
    windSpeed__m_s=10
)

# Misc
RocketDefinitionFilename = "rasaero-data\\Breaking all illusions.CDX1"
FlightSimulationFilename = "rasaero-data\\flight-simulation.csv"
AeroPlotsFilename = "rasaero-data\\aeroplots.csv"
RocketpyOutputFilename = "output.txt"
"""
def simulate(components, CDOn, CDOff):
    surfaces = []
    locations = []
    referenceArea__m2 = ((np.pi * G2B2.bodyDiameter__mm**2) / 4) * 1e-6

    # Generate a collection of "Generic Surfaces" using the RASAero coefficients
    for component in components:
        # TODO: Implement this properly
        def cm(mach, alpha, reynolds):
            return 0

        surface = rocketpy.GenericSurface(
            reference_area=referenceArea__m2,
            reference_length=1,
            coefficients={
                "cD": lambda alpha, beta, mach, reynolds, pitchRate, yawRate, rollRate: 0,
                "cL": lambda alpha, beta, mach, reynolds, pitchRate, yawRate, rollRate: component.CL(mach, alpha, reynolds),
                "cQ": lambda alpha, beta, mach, reynolds, pitchRate, yawRate, rollRate: component.CL(mach, beta, reynolds),
                "cm": lambda alpha, beta, mach, reynolds, pitchRate, yawRate, rollRate: cm(mach, alpha, reynolds),
                "cn": lambda alpha, beta, mach, reynolds, pitchRate, yawRate, rollRate: cm(mach, beta, reynolds),
                "cl": lambda alpha, beta, mach, reynolds, pitchRate, yawRate, rollRate: 0
            },
            name="Generic Surface"
        )

        # Placing the surfaces at the CP location at Mach 0.5, 0 AoA and sea-level Reynolds
        locations.append(component.CP(0.5, 0, 598715.4))
        surfaces.append(surface)

    # TODO:
    # 1. Make this more parametric
    # 2. Nice way to remove all the details somehow?
    motor = rocketpy.SolidMotor(
        thrust_source=MotorFile,
        dry_mass=5.5,
        dry_inertia=(11223280.45/1000000,
                            821090442.73/1000000,
                            821090442.73/1000000),
        nozzle_radius=0.07,
        grain_number=6,
        grain_separation=0.00079,
        grain_density=(1.50350 / 0.00091),
        grain_outer_radius=0.0425,
        grain_initial_inner_radius=0.01745,
        grain_initial_height=0.19,
        grains_center_of_mass_position= 0.60487,
        center_of_dry_mass_position=0.64437,
        coordinate_system_orientation="nozzle_to_combustion_chamber",
        nozzle_position=0
    )
    stochasticMotor = rocketpy.StochasticSolidMotor(
        solid_motor=motor,
        total_impulse=(motor.total_impulse * MotorImpulseUncertainty__pct),
        burn_out_time=(motor.burn_out_time * MotorBurnTimeUncertainty__pct)
    )

    rocket = rocketpy.Rocket(
        radius=((BodyDiameter__mm / 2) * 1e-3),
        mass=LoadedMass__kg,
        inertia=UnloadedInertia__kgm2,
        center_of_mass_without_motor=(CoMTipDistance__mm * 1e-3),
        coordinate_system_orientation="nose_to_tail",
        power_on_drag=Function(CDOn),
        power_off_drag=Function(CDOff)
    )
    rocket.add_parachute(
        name="Drogue",
        cd_s=(DrogueCD * DrogueArea__m2),
        trigger="apogee",
        sampling_rate=100
    )
    rocket.add_parachute(
        name="Main",
        cd_s=(MainCD * MainArea__m2),
        trigger=MainParachuteAltitude__m,
        sampling_rate=100
    )
    rocket.add_motor(motor, 0)
    rocket.add_surfaces(surfaces, locations)
    stochasticRocket = rocketpy.StochasticRocket(rocket=rocket)
    stochasticRocket.add_motor(stochasticMotor)

    # TODO: Add our wind model
    environment = rocketpy.Environment()
    environment.set_date(LaunchDate)
    environment.set_atmospheric_model(type="standard_atmosphere")
    stochasticEnvironment = rocketpy.StochasticEnvironment(environment=environment)

    flight = rocketpy.Flight(
        rocket = rocket,
        environment  = environment,
        rail_length = LaunchRailLength__m,
        inclination = LaunchInclination__deg,
        heading = LaunchHeading__deg,
    )
    stochasticFlight = rocketpy.StochasticFlight(
        flight=flight,
        inclination=InclinationUncertainty__deg,
        heading=HeadingUncertainty__deg
    )

    monteCarlo = rocketpy.MonteCarlo(
        filename=RocketpyOutputFilename,
        rocket=stochasticRocket,
        environment=stochasticEnvironment,
        flight=stochasticFlight,
    )

    monteCarlo.simulate(number_of_simulations=SimulationCount, append=False)

def plotAltitudeProfile(time, altitudeProfile):
    return None

def plotFlightProfile(time, flightProfile):
    return None

def plotLandingProfile(landingProfile):
    return None
"""
def calculateMaximumCPMovement(components, maxMach):
    table = Texttable()
    table.set_cols_align(["c", "c", "c", "c", "c"])
    table.set_cols_valign(["m", "m", "m", "m", "m"])
    table.add_row(["Component", "Max \u0394CP (mm)", "Max \u0394CP (%)", "@ Mach", "@ Alpha (deg)"])

    for component in components:
        # df is the dataframe already loaded
        df = component.dataframe.sort_values("Mach")

        # First non-zero, non-NaN CP
        first_idx = df.index[(df["CP"].notna()) & (df["CP"] != 0)][0]
        first_cp = df.loc[first_idx, "CP"]

        # Subset to Mach <= maxMach with valid CP
        df_sub = df.loc[(df["Mach"] <= maxMach) & (df["CP"].notna())].copy()

        # Signed displacement from first CP
        df_sub["dCP"] = first_cp - df_sub["CP"]

        # Row with maximum absolute displacement
        idx_max = df_sub["dCP"].abs().idxmax()

        max_delta_cp = df_sub.loc[idx_max, "dCP"] * 1e3
        pct_at_max = (df_sub.loc[idx_max, "dCP"] / first_cp) * 100
        mach_at_max = df_sub.loc[idx_max, "Mach"]
        alpha_at_max = df_sub.loc[idx_max, "Alpha"] / 0.0174533

        table.add_row([component.name, max_delta_cp, pct_at_max, mach_at_max, alpha_at_max])

    print(table.draw())

def plotCD(rocket, maxMach):
    fig, ax = plt.subplots()
    fig.suptitle("Full Rocket CD")
    ax.set_xlabel("Mach")
    ax.set_ylabel("CD")
    ax.set_ylim((0, 0.5))
    ax.grid()

    mach = np.linspace(0.01, maxMach, 100)
    ax.plot(mach, rocket.component.CDOn(mach, 0), label="Power-On")
    ax.plot(mach, rocket.component.CDOff(mach, 0), label="Power-Off")

    ax.legend()

# TODO: Make the user provide the reynolds number?
def compareInterpolation(components, alpha__deg, mach):
    alpha__rad = alpha__deg * 0.0174533

    for component in components:
        # Table setup
        table = Texttable()
        table.set_cols_align(["c", "c", "c", "c"])
        table.set_cols_valign(["m", "m", "m", "m"])
        table.add_row(["Source", "CP", "CL", "CNAlpha"])

        lut = component.dataframe[(component.dataframe["Alpha"] == alpha__rad) & (component.dataframe["Mach"] == mach)]
        reynolds = lut["Reynolds Number"]
        interpolation = {
            "CP": component.CP(mach, alpha__rad, reynolds),
            "CL": component.CL(mach, alpha__rad, reynolds),
            "CNAlpha": component.CNAlpha(mach, reynolds)
        }

        table.add_row(["LUT", lut["CP"], lut["CL"], lut["CNAlpha"]])
        table.add_row(["Interpolation", interpolation["CP"], interpolation["CL"], interpolation["CNAlpha"]])

        # Print!
        print(component.name)
        print(table.draw())
        print()

def calculateUnloadedMassProperties(loadedMass__kg, loadedCoM__m, loadedMoI__kgm2, rocketLength__m, solidMotor):
    # Extract motor properties
    motorCasingMass__kg = solidMotor.dry_mass
    propellantMass__kg = solidMotor.propellant_initial_mass
    motorTotalMass__kg = motorCasingMass__kg + propellantMass__kg

    motorCoM__m = rocketLength__m - solidMotor.center_of_dry_mass_position
    propellantCoM__m = rocketLength__m - solidMotor.grains_center_of_mass_position

    motorMoI__kgm2 = solidMotor.dry_I_11
    propellantMoI__kgm2 = solidMotor.propellant_I_11(0)

    # Calculate combined motor properties at liftoff
    motorCombinedCoM__m = (motorCasingMass__kg * motorCoM__m +
                           propellantMass__kg * propellantCoM__m) / motorTotalMass__kg
    motorCombinedMoI__kgm2 = (motorMoI__kgm2 + motorCasingMass__kg * (motorCoM__m - motorCombinedCoM__m)**2 +
                              propellantMoI__kgm2 + propellantMass__kg * (propellantCoM__m - motorCombinedCoM__m)**2)

    # Reverse calculate unloaded properties using parallel axis theorem
    unloadedMass__kg = loadedMass__kg - motorTotalMass__kg
    unloadedCoM__m = (loadedMass__kg * loadedCoM__m - motorTotalMass__kg * motorCombinedCoM__m) / unloadedMass__kg
    unloadedMoI__kgm2 = (loadedMoI__kgm2 - motorCombinedMoI__kgm2 -
                         motorTotalMass__kg * (motorCombinedCoM__m - loadedCoM__m)**2 -
                         unloadedMass__kg * (unloadedCoM__m - loadedCoM__m)**2)

    return unloadedMass__kg, unloadedCoM__m, unloadedMoI__kgm2

def calculateFlightMassProperties(time__s, unloadedMass__kg, unloadedCoM__m, unloadedMoI__kgm2, rocketLength__m, solidMotor):
    # Extract motor properties
    motorCasingMass__kg = solidMotor.dry_mass
    propellantMass__kg = np.array(solidMotor.propellant_mass(time__s))

    motorCoM__m = rocketLength__m - solidMotor.center_of_dry_mass_position
    propellantCoM__m = rocketLength__m - solidMotor.grains_center_of_mass_position

    motorMoI__kgm2 = solidMotor.dry_I_11
    propellantMoI__kgm2 = np.array(solidMotor.propellant_I_11(time__s))

    # Calculate total mass and CoM throughout flight
    currentTotalMass__kg = unloadedMass__kg + motorCasingMass__kg + propellantMass__kg
    flightCoM__m = (unloadedMass__kg * unloadedCoM__m +
                    motorCasingMass__kg * motorCoM__m +
                    propellantMass__kg * propellantCoM__m) / currentTotalMass__kg

    # Calculate MoI using parallel axis theorem (vectorized)
    flightMoI__kgm2 = (
        unloadedMoI__kgm2 + unloadedMass__kg * (unloadedCoM__m - flightCoM__m)**2 +
        motorMoI__kgm2 + motorCasingMass__kg * (motorCoM__m - flightCoM__m)**2 +
        propellantMoI__kgm2 * (propellantMass__kg / propellantMass__kg[0]) +
        propellantMass__kg * (propellantCoM__m - flightCoM__m)**2
    )

    return propellantMass__kg, flightCoM__m, flightMoI__kgm2

def setup():
    # Parse input arguments
    parser = argparse.ArgumentParser(description="G2B2 Flight Sim Tool")
    parser.add_argument("-fd", "--force_definition", action="store_true", help="Force regeneration of RASAero rocket definition")
    parser.add_argument("-fa", "--force_aerodata", action="store_true", help="Force regeneration of RASAero aerodata")
    args = parser.parse_args()

    # Get the directory where this script is located
    scriptDirectory = os.path.dirname(os.path.abspath(__file__))

    # Construct absolute paths by joining script directory with filenames
    rocketDefinitionFullPath = os.path.normpath(os.path.join(scriptDirectory, RocketDefinitionFilename))
    flightSimulationFullPath = os.path.normpath(os.path.join(scriptDirectory, FlightSimulationFilename))
    aeroPlotsFullPath = os.path.normpath(os.path.join(scriptDirectory, AeroPlotsFilename))

    # Initilise the RASAero interface
    rasaero = RASAero(rocketDefinitionFullPath, None, flightSimulationFullPath, aeroPlotsFullPath)

    # Check if at least one version of each input file exists
    rocketDefinitionExists = len(glob.glob(f"{os.path.splitext(RocketDefinitionFilename)[0]}*{os.path.splitext(RocketDefinitionFilename)[1]}")) > 0
    aeroDataExists = all(
        len(glob.glob(f"{os.path.splitext(file)[0]}*{os.path.splitext(file)[1]}")) > 0
        for file in (FlightSimulationFilename, AeroPlotsFilename)
    )

    # Generate rocket defintion if it is missing or if forced to do so
    if args.force_definition or not rocketDefinitionExists:
        # Remove existing rocket definition (avoids the "Replace file?" pop-ups in RASAero)
        base, extension = os.path.splitext(RocketDefinitionFilename)
        for match in glob.glob(f"{base}*{extension}"):
            if os.path.isfile(match):
                os.remove(match)

        print(f"{Fore.green}GENERATING ROCKET DEFINITION...{Style.reset}")

        rasaero.exportRocketDefinition(G2B2, HighAltitudeSimulation)
        rasaero.exportFlightSimulation()

    # Generate aerodata if it is missing, or if we just generated the rocket definition or if forced to do so
    if args.force_aerodata or not aeroDataExists or not rocketDefinitionExists:
        # Remove all existing aerodata input files (avoids the "Replace file?" pop-ups in RASAero)
        for file in (FlightSimulationFilename, AeroPlotsFilename):
            base, extension = os.path.splitext(AeroPlotsFilename) # TODO: Replace "file"
            for match in glob.glob(f"{base}*{extension}"):
                if os.path.isfile(match):
                    os.remove(match)

        print(f"{Fore.green}GENERATING AERODATA...{Style.reset}")

        rasaero.exportFlightSimulation()
        simulation = rasaero.parseFlightSimulation()
        altitudes = np.arange(0, simulation.apogee__m + CoefficientAltitudeStepover__m, CoefficientAltitudeStepover__m)
        rasaero.exportAeroPlots(altitudes)
        rasaero.closeWindow()

    else:
        print(f"{Fore.red}RASAERO DATA PROVIDED. ENSURE IT'S NOT STALE!{Style.reset}")

    # Parse RASAero data
    print(f"{Fore.green}PARSING RASAERO DATA...{Style.reset}")
    simulation = rasaero.parseFlightSimulation()
    rocket, components = rasaero.parseAeroParameters()

    return simulation, rocket, components

def main():
    # Get things ready
    simulation, rocket, components = setup()

    # TODO: Write code here!
    rocket.loadedMoI__kgm2 = 1/12 * 40/2.2 * (1857.19670/1000) **2 # TODO: Review how I'd like to enter this
    compareInterpolation(components, 0, 0.01)
    plotCD(rocket, 3)
    calculateMaximumCPMovement(components, 3)

    # Show plots
    plt.show()

if __name__ == "__main__":
    main()
