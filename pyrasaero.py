import cv2
import keyboard
from time import sleep
from gui_automation import GuiAuto
from pywinauto.application import Application

class RASAero():
    # Change this as appropriate (notice use of double "\")
    RasaeroPath = "C:\\Program Files (x86)\\RASAero II\\RASAero II.exe"
    
    ParamaterInputNameMap = {  "noseconeDiameter__in" : "mtb_Diameter",
                               "bodytubeLength__in" : "mtb_Length",
                               "noseconeLength__in" : "mtb_Length",
                               "noseconeTipRadius__in" : "mtb_LEBluntRadius",
                               "finspan__in" : "Span",
                               "finRootChord__in" : "Chord"     }
    BaselineFullFilePath = ""
    ExportGUIImages = []
    
    Window = None
    GUIAuto = None
    
    def __init__(self, exportGUIImages, baselineFilePath, baselineFilename):
        self.GUIAuto = GuiAuto()
        
        self.ExportGUIImages = exportGUIImages
        self.baselineFileFullPath = baselineFilePath + "\\" + baselineFilename
    
    # Load the RASAero template file
    def openFile(self, filename):
        # Press "Ctrl+O"
        self.Window.type_keys("^o")
        
        fileNameBox = self.Window.child_window(title="File name:", control_type="Edit").wrapper_object()
        fileNameBox.type_keys(filename)
        
        # Press "Enter"
        fileNameBox.type_keys("~")

    def replaceTextValue(self, control, value):
        # Press "Ctrl+A, delete then then input the new value"
        control.type_keys("^a {DELETE} " + str(value))
    
    # Fin and bodytube modifications rolled into one function as the RASAero fin menu is accessed from inside the bodytube menu
    def inputBodytubeParameters(self, parameters):
        if parameters:
            # Open the bodytube window
            self.Window.child_window(title_re=".*Body Tube", control_type="ListItem").wrapper_object().double_click_input()
        
            try:
                bodytubeLength__in = parameters["bodytubeLength__in"]
                textInput = self.Window.child_window(auto_id=self.ParamaterInputNameMap["bodytubeLength__in"], control_type="Pane").wrapper_object()
                self.replaceTextValue(textInput, bodytubeLength__in)
                del parameters["bodytubeLength__in"]
            
            except:
                pass
            
            if parameters:
                # Open the fins sub-window
                self.Window.child_window(title="Fins", auto_id="btn_Fins", control_type="Button").click_input()
                
                for parameterName in parameters.keys():
                    textInput = self.Window.child_window(auto_id=self.ParamaterInputNameMap[parameterName], control_type="Pane").wrapper_object()
                    self.replaceTextValue(textInput, parameters[parameterName])
                
                self.Window.child_window(title="OK", auto_id="btn_AddFin", control_type="Button").wrapper_object().click_input()
            
            self.Window.child_window(title="Save", auto_id="btn_Save", control_type="Button").wrapper_object().click_input()
    
    def inputNoseconeParameters(self, parameters):
        if parameters:
            # Open the nosecone window
            self.Window.child_window(title_re=".*Nose Cone", control_type="ListItem").wrapper_object().double_click_input()
            
            for parameterName in parameters.keys():
                textInput = self.Window.child_window(auto_id=self.ParamaterInputNameMap[parameterName], control_type="Pane").wrapper_object()
                self.replaceTextValue(textInput, parameters[parameterName])
        
            self.Window.child_window(title="Save", auto_id="btn_Save", control_type="Button").wrapper_object().click_input()
    
    # This function brings great shame...
    # Use of gui_automation rather than pywinauto driven by what appears to be a straight bug in the Windows' UIA framework (surprise surprise)
    # When attempting to use the pywinauto on the child elements of the freshly popped-up "Aero Plots" window, the program was crashing with
    # behaviour very similar to that found here: https://github.com/pywinauto/pywinauto/issues/563
    # It was 3AM. This was the final hurdle. Please forgive me
    def exportAeroData(self, exportFilepath):
        # Open the "Aero Plots" window
        self.Window.child_window(title_re="Aero Plots", control_type="Button").wrapper_object().click_input()
        
        # Give the "Aero Plots" window time to open before we look for buttons
        sleep(2)
        
        # Looking for "File --> Export --> To CSV File
        for filename in self.ExportGUIImages:
            spot = self.GUIAuto.detect(cv2.imread(filename), 0.95)

            if spot:
                x, y = spot.custom_position(1, 9, 1, 3)
                self.GUIAuto.click(coords=(x, y), clicks=1)
            
            else:
                print("UNABLE TO FIND ONE OF THE BUTTONS REQUIRED FOR CSV EXPORT")
                exit()
        
        # Export the "Aero Plots" data
        keyboard.write(exportFilepath)
        keyboard.send("enter")

        # Close "Aero Plots" window
        keyboard.send("alt + f4")

    def close(self):
        # Close main window
        keyboard.send("alt + f4")
        
        # Don't save changes
        keyboard.send("tab")
        keyboard.send("enter")
    
    def run(self, RunName, aeroplotDirectory, parameters):
        aeroplotFullFilePath = aeroplotDirectory + "\\" + RunName + ".csv"
        
        rasaero = Application(backend="uia").start(self.RasaeroPath).connect(title="RASAero II ", timeout=10)
        self.Window = rasaero.top_window()
        
        self.openFile(self.baselineFileFullPath)
        
        bodytubeParameters = {}
        noseconeParameters = {}
        
        for parameterName in parameters.keys():
            parameter = parameters[parameterName]
            
            if not parameter:
                continue
            
            if parameterName.__contains__("bodytube") or parameterName.__contains__("fin"):
                bodytubeParameters[parameterName] = parameter
            
            elif parameterName.__contains__("nosecone"):
                noseconeParameters[parameterName] = parameter
            
            else:
                continue
        
        self.inputBodytubeParameters(bodytubeParameters)
        self.inputNoseconeParameters(noseconeParameters)
        
        self.exportAeroData(aeroplotFullFilePath)
        self.close()
        
        return aeroplotFullFilePath

class Simulation():
    RunName = ""
    Parameters = {}
    Rasaero = None
    
    def __init__(self, exportImages, baselineFilePath, baselineFilename, bodytubeDiameter__mm=0, bodytubeLength__mm=0, noseconeLength__mm=0, noseconeTipRadius__mm=0, finspan__mm=0, finRootChord__mm=0):        
        self.Rasaero = RASAero(exportImages, baselineFilePath, (baselineFilename + ".CDX1"))
        
        # nosecone diameter == body tube diameter. RASAero requires us to set the body diameter in the nosecone section
        self.Parameters["noseconeDiameter__in"] = self.mmtoin(bodytubeDiameter__mm)
        self.Parameters["bodytubeLength__in"] = self.mmtoin(bodytubeLength__mm)
        self.Parameters["noseconeLength__in"] = self.mmtoin(noseconeLength__mm)
        self.Parameters["noseconeTipRadius__in"] = self.mmtoin(noseconeTipRadius__mm)
        self.Parameters["finspan__in"] = self.mmtoin(finspan__mm)
        self.Parameters["finRootChord__in"] = self.mmtoin(finRootChord__mm)
        
        self.RunName = f"%s_BD[%f]-BL[%f]-NL[%f]-NTR[%f]-FS[%f]-FRC[%f]" % (baselineFilename, bodytubeDiameter__mm, bodytubeLength__mm, noseconeLength__mm, noseconeTipRadius__mm, finspan__mm, finRootChord__mm)
    
    def mmtoin(self, mm):
        return (mm / 25.4)
    
    def run(self, aeroplotDirectory):
        return self.Rasaero.run(self.RunName, aeroplotDirectory, self.Parameters)