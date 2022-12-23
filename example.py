import pyrasaero
import os
import csv
from time import sleep

# Images of the interface for the simulation CV
# Replace these with ones taken for the computer this is running on
# Ensure the button to click is in the quadrant 1/9th from the left and 1/3rd from the top (see RASAero.exportAeroData for why)
ExportGUIImages = ["export-gui-0.png", "export-gui-1.png", "export-gui-2.png"]

# Ensure this is in the same directory as this file (and there is no extension!)
BaselineFilename = "example-base-parametric-model"

MachNumberOfInterest = 3

# Set to "0" if you're not interested in modifying this value
BodytubeDiameter__mm = 120
BodytubeLength__mm = 0
NoseconeLength__mm = 0
NoseconeTipRadius__mm = 0
Finspan__mm = 0
FinRootChord__mm = 0

def main():
    programPath = os.path.dirname(os.path.realpath(__file__))
    outputDirectory = programPath + "\\output-aeroplots"
    
    try:
        os.mkdir(outputDirectory)
    
    except OSError as error:
        print("ERROR: OUTPUT DIRECTORY NEEDS TO NOT EXIST BEFORE RUNNING THIS PROGRAM")
        exit()
    
    for i in range(0, 10):
        sim = pyrasaero.Simulation(ExportGUIImages, programPath, BaselineFilename, BodytubeDiameter__mm + (i * 5), BodytubeLength__mm, NoseconeLength__mm, NoseconeTipRadius__mm, Finspan__mm, FinRootChord__mm)
        simOutputFullFilePath = sim.run(outputDirectory)
        
        # Required to give the file time to be written
        sleep(0.5)
        
        with open(simOutputFullFilePath) as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                if float(row["Mach"]) == MachNumberOfInterest:
                    cd = float(row["CD"])
                    print(f"Cd OF THE %iTH ITERATION AT MACH %f IS %s" % (i, MachNumberOfInterest, cd))
                    break

if __name__ == "__main__":
    main()