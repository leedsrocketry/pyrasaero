# pyrasaero
Python library to automate RASAero II

## Usage
This only works on Windows (which sort of goes without saying as RASAero is only built for Windows...)

1. Install Python3+
2. Install RASAero II
3. Download and extract this repository to your computer
4. Run `example.py` to get a feel for how it all works
5. Run with it

Note: You won't be able to do anything else with your computer while the simulations are running (well you will but if you do it will mess everything up)

## Debugging
If example.py is having trouble finding the buttons to press to export the CSV data from RASAero:
1. Open RASAero manually
2. Import a `.CDX` file into RASAero (could use the one supplied in this repo)
3. Get screenshots of the "File", "Export" and "Save To CSV" buttons from the "Aero Plots" (framed the same as the ones provided in this repo)
4. Save the screenshots in the same directory as example.py and modidy example.py to use the names of these files in it's ExportGUIImages array
