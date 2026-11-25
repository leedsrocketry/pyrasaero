import os
import shutil
import xml.etree.ElementTree as ET
from time import sleep, time

import pandas as pd
from pywinauto import Desktop
from pywinauto.application import Application

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
    # Aft-to-fore: each entry is exported (as a cumulative assembly), then
    # stripped from the working CDX1 before the next.  The aftmost component
    # in each assembly gives its name to the exported CSV.
    aftComponentOrder = ("Fin", "BoatTail", "BodyTube", "NoseCone")

    # GUI timing.  Each step waits for the window or file it needs, up to
    # these limits; increase them on a slow machine.
    windowTimeout__s = 20.0       # a window or dialog to appear
    simulationTimeout__s = 60.0   # the flight simulation to finish
    fileTimeout__s = 180.0        # an exported CSV to be fully written
    settleDelay__s = 0.3          # pause after each click

    @staticmethod
    def engineFilePath() -> str:
        """Return the motor (.eng) file RASAero II currently uses.

        RASAero stores the file chosen via File -> Select Motor File in its
        user.config (``EngineFilename``) and only searches that one file.
        With no setting it uses Documents\\RASAero II\\rasp.eng.
        """
        import glob
        default = os.path.join(os.path.expanduser("~"), "Documents", "RASAero II", "rasp.eng")
        configs = glob.glob(os.path.join(
            os.environ.get("LOCALAPPDATA", ""), "RASAero", "*", "*", "user.config"))
        for cfgPath in sorted(configs, key=os.path.getmtime, reverse=True):
            setting = ET.parse(cfgPath).getroot().find(".//setting[@name='EngineFilename']/value")
            if setting is not None and setting.text and setting.text.strip():
                return setting.text.strip()
        return default

    @staticmethod
    def engineNames(engPath: str) -> set:
        """Motor names in a RASP .eng file, formatted as RASAero shows them
        (``"<designation>  (<manufacturer>)"``, two spaces)."""
        names = set()
        with open(engPath, encoding="latin-1") as fh:
            for line in fh:
                if not line.strip() or line.startswith(";") or line[0].isspace():
                    continue
                tokens = line.split()
                if len(tokens) >= 7 and not tokens[0][0].isdigit():
                    names.add(f"{tokens[0]}  ({tokens[-1]})")
        return names

    @classmethod
    def checkMotor(cls, motor: str) -> None:
        """Raise a clear error if RASAero will not find *motor*.

        Without this, RASAero shows a "motor ... was not found in the
        currently selected engine file" pop-up mid-automation.
        """
        engPath = cls.engineFilePath()
        fix = ("In RASAero II use File -> Select Motor File and choose a file "
               "containing the motor (the bundled database is "
               "Documents\\RASAero II\\rasp.eng).")
        if not os.path.isfile(engPath):
            raise RuntimeError(f"RASAero's selected motor file does not exist: {engPath}. {fix}")
        names = cls.engineNames(engPath)
        if motor not in names:
            close = sorted(n for n in names if n.split()[0].lower() == motor.split()[0].lower())
            hint = f" Did you mean {close[0]!r}?" if close else ""
            raise RuntimeError(
                f"Motor {motor!r} is not in RASAero's selected motor file "
                f"{engPath}.{hint} {fix}"
            )

    @staticmethod
    def killAll():
        """Kill all running RASAero II processes."""
        import subprocess
        subprocess.run(
            ["taskkill", "/F", "/IM", "RASAero II.exe"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def __init__(self, rocketDefinitionPath, flightSimulationFullPath, aeroPlotsFullPath):
        self.rocketDefinitionPath = rocketDefinitionPath
        self.flightSimulationFullPath = flightSimulationFullPath
        self.aeroPlotsFullPath = aeroPlotsFullPath
        self.app = None
        self.main = None

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
    def degC2degF(self, degC): return self._rnd((degC * (9 / 5)) + 32)

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
    
    # ------------------------------------------------------------------
    # GUI automation
    #
    # Design rules (RASAero II is a WinForms app driven through UIA):
    #   * No global keystrokes.  Buttons and menus are clicked at the
    #     position UIA reports, only after checking the control is visible
    #     inside its window.  Text is typed only into a confirmed dialog.
    #   * Never UIA-Invoke something that opens a window: RASAero opens its
    #     windows modally, so Invoke blocks and deadlocks.
    #   * Every step waits for the window or file it expects, with a
    #     timeout and a clear error.
    #   * RASAero is closed by killing its process, never with Alt+F4.
    #     The CDX1 on disk is the source of truth, so nothing is lost.
    #   * Never search the full control tree of the flight data window: its
    #     grid has thousands of rows and UIA searches take minutes.
    # ------------------------------------------------------------------

    _SAVE_DIALOG_CLASS = "#32770"
    _TIME_BASE_RADIO = {0.01: "RadioButton1", 0.1: "RadioButton2",
                        0.5: "RadioButton3", 1.0: "RadioButton4"}

    @staticmethod
    def isRunning() -> bool:
        """True if any RASAero II process is running."""
        import subprocess
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq RASAero II.exe", "/NH"],
            capture_output=True, text=True,
        ).stdout
        return "RASAero II.exe" in out

    def _start(self, cdx1Path):
        """Launch RASAero II with *cdx1Path* open and wait until it is usable.

        The file is passed on the command line (as when double-clicking a
        .CDX1), which is much faster than the Open dialog.  The parts list
        at the top left of the main window confirms the file loaded.
        """
        if self.isRunning():
            raise RuntimeError(
                "RASAero II is already running. Close it before running "
                "pyrasaero, which needs sole control of RASAero.")
        if not os.path.isfile(cdx1Path):
            raise FileNotFoundError(cdx1Path)
        self.app = Application(backend="uia").start(f'"{RASAeroPath}" "{cdx1Path}"')
        spec = self.app.window(title="RASAero II ")
        spec.wait("visible", timeout=self.windowTimeout__s)
        # Resolve the main window once: every access through a pywinauto
        # WindowSpecification re-searches the UI tree (~0.6 s each time)
        main = spec.wrapper_object()

        def partsListLoaded():
            # Parts list: main > Pane > Pane > List (searched level by level;
            # a full-tree search is slow)
            for p in main.children(control_type="Pane"):
                for q in p.children(control_type="Pane"):
                    for lst in q.children(control_type="List"):
                        if any(i.window_text() != "Horizontal" for i in lst.children()):
                            return True
            return False

        deadline = time() + self.windowTimeout__s
        stable = 0
        while True:
            if time() > deadline:
                raise RuntimeError(
                    f"RASAero did not load {cdx1Path} (its parts list stayed "
                    "empty). Open the file in RASAero by hand to see why.")
            loaded = self._ifAlive(partsListLoaded, False)
            # A splash screen briefly disables the main window at startup
            stable = stable + 1 if loaded and main.is_enabled() else 0
            if stable >= 2:
                break
            sleep(0.1)
        self.main = main

    def _quit(self):
        """Kill this RASAero process and wait for it to exit."""
        app = getattr(self, "app", None)
        self.app = None
        if app is not None:
            try:
                app.kill()
            except Exception:
                pass
        deadline = time() + 10
        while self.isRunning() and time() < deadline:
            sleep(0.25)
        if self.isRunning():
            self.killAll()

    @staticmethod
    def _ifAlive(fn, default=None):
        """Run *fn*, returning *default* if the window it touches has gone.

        RASAero creates and destroys short-lived windows (splash screen,
        menus, closing pop-ups), so any window can vanish between being
        listed and being inspected.
        """
        from _ctypes import COMError
        from pywinauto.controls.hwndwrapper import InvalidWindowHandle
        from pywinauto.findwindows import ElementNotFoundError
        try:
            return fn()
        except (InvalidWindowHandle, ElementNotFoundError, COMError):
            return default

    def _visibleWindows(self):
        """Visible top-level and owned windows of this RASAero process."""
        from pywinauto.controls.hwndwrapper import InvalidWindowHandle
        pid = self.app.process
        # Desktop.windows() wraps every top-level window on the desktop, and
        # raises if any of them (in any app) closes between being listed and
        # being wrapped, so retry on that race.
        for attempt in range(10):
            try:
                windows = Desktop(backend="win32").windows()
                break
            except InvalidWindowHandle:
                if attempt == 9:
                    raise
                sleep(0.1)
        return [w for w in windows
                if self._ifAlive(lambda: w.process_id() == pid and w.is_visible(), False)]

    @staticmethod
    def _uia(win32Window):
        return Desktop(backend="uia").window(handle=win32Window.handle).wrapper_object()

    def _click(self, element, container):
        """Click *element* after checking it is shown inside *container*."""
        r, c = element.rectangle(), container.rectangle()
        if not (r.width() > 0 and c.left <= r.left and r.right <= c.right
                and c.top <= r.top and r.bottom <= c.bottom):
            raise RuntimeError(
                f"RASAero control {element.window_text()!r} is not visible; "
                "refusing to click blind")
        container.set_focus()
        element.click_input()
        sleep(self.settleDelay__s)

    def _menu(self, window, *path):
        """Click through a menu, e.g. ``_menu(w, "File", "Export", "To CSV")``."""
        bars = [c for c in window.children() if c.element_info.control_type == "MenuBar"]
        items = [m for b in bars for m in b.children(control_type="MenuItem")]
        for depth, name in enumerate(path):
            matches = [m for m in items if m.window_text().strip() == name]
            if not matches:
                raise RuntimeError(
                    f"RASAero menu item {name!r} not found; have "
                    f"{[m.window_text().strip() for m in items]}")
            item = matches[0]
            if depth == 0:
                self._click(item, window)
            else:
                # Drop-down items are drawn outside the window's rectangle,
                # so check they are on screen rather than inside the window
                deadline = time() + self.windowTimeout__s
                while item.rectangle().width() <= 0:
                    if time() > deadline:
                        raise RuntimeError(f"RASAero menu {name!r} did not open")
                    sleep(0.2)
                item.click_input()
                sleep(self.settleDelay__s)
            items = item.children(control_type="MenuItem")

    @staticmethod
    def _popupText(uiaWindow):
        """Message text of a (small) RASAero pop-up window."""
        texts = []
        for c in uiaWindow.children():
            kind = c.element_info.control_type
            if kind == "Text":
                texts.append(c.window_text().strip())
            elif kind == "Pane":
                texts += [g.window_text().strip() for g in c.children()
                          if g.element_info.control_type == "Text"]
        return " ".join(t for t in texts if t)

    def _closePopups(self, known, firstSeen, isTarget=None, grace=1.5):
        """Close RASAero warning pop-ups, reporting their text.

        A pop-up is a visible window not in *known* that is not a target
        (per *isTarget*) and has existed for at least *grace* seconds; the
        grace period stops a window that is still being built (and so does
        not match *isTarget* yet) from being closed.  *firstSeen* maps window
        handles to when they were first seen and must persist between calls.
        Returns the messages seen.
        """
        import warnings
        seen = []
        now = time()
        for w in self._visibleWindows():
            if w.handle in known:
                continue
            if isTarget is not None and self._ifAlive(lambda: isTarget(w), True):
                continue  # a target (or gone): never close it
            if now - firstSeen.setdefault(w.handle, now) < grace:
                continue

            def report_and_close():
                u = self._uia(w)
                message = f"RASAero '{w.window_text()}': {self._popupText(u)}"
                u.close()
                return message
            message = self._ifAlive(report_and_close)
            if message:
                warnings.warn(message)
                seen.append(message)
                sleep(self.settleDelay__s)
        return seen

    def _waitFor(self, known, isTarget, what, timeout=None):
        """Wait for a new RASAero window matching *isTarget* and return it.

        Other new windows are treated as warning pop-ups: their message is
        reported with ``warnings.warn`` and they are closed.
        """
        deadline = time() + (timeout or self.windowTimeout__s)
        seen, firstSeen = [], {}
        while time() < deadline:
            for w in self._visibleWindows():
                if w.handle not in known and self._ifAlive(lambda: isTarget(w), False):
                    return w
            seen += self._closePopups(known, firstSeen, isTarget)
            sleep(0.1)
        extra = f" RASAero showed: {seen}" if seen else ""
        raise RuntimeError(f"Timed out waiting for {what}.{extra}")

    @staticmethod
    def _lastRow(fullPath):
        """Header and last data row of a CSV, as lists of strings."""
        with open(fullPath, "rb") as fh:
            header = fh.readline().decode("latin-1").strip().split(",")
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - 4096))
            lines = [l for l in fh.read().decode("latin-1").splitlines() if l.strip()]
        return header, (lines[-1].split(",") if lines else [])

    @classmethod
    def _flightCsvComplete(cls, fullPath):
        """RASAero simulates to ground impact: the last row's altitude is
        near zero.  A partly written file ends mid-flight."""
        header, last = cls._lastRow(fullPath)
        try:
            return float(last[header.index("Altitude (ft)")]) < 100.0
        except (ValueError, IndexError):
            return False

    @classmethod
    def _aeroCsvComplete(cls, fullPath):
        """Aero plot exports run up to Mach 24.99 (the Mach-Alt table goes to 25)."""
        header, last = cls._lastRow(fullPath)
        try:
            return float(last[0]) >= 24.9
        except (ValueError, IndexError):
            return False

    def _saveAs(self, known, fullPath, isComplete=None):
        """Fill in the Save As dialog that is opening and wait until the file
        is fully written: passing the *isComplete* content check and unchanged
        in size for 1 s, or, with no content check, unchanged for 4 s."""
        if os.path.isfile(fullPath):
            os.remove(fullPath)  # avoids RASAero's overwrite prompt
        dlg = self._waitFor(
            known, lambda w: w.class_name() == self._SAVE_DIALOG_CLASS,
            "the Save As dialog")
        box = [e for e in self._uia(dlg).descendants(control_type="Edit")
               if e.element_info.automation_id == "1001"]
        if not box:
            raise RuntimeError("File name box not found in RASAero's Save As dialog")
        box[0].set_edit_text(fullPath)
        box[0].type_keys("{ENTER}")
        # RASAero writes in bursts with pauses, so a short "stopped growing"
        # check alone passes too early and the file gets cut off when RASAero
        # is killed.  The content check is the real proof of completion.
        quiet = 1.0 if isComplete else 4.0
        deadline = time() + self.fileTimeout__s
        last, stableSince = -1, None
        while time() < deadline:
            size = os.path.getsize(fullPath) if os.path.isfile(fullPath) else -1
            if size != last:
                last, stableSince = size, time()
            elif (size > 0 and time() - stableSince >= quiet
                  and (isComplete is None or isComplete(fullPath))):
                return
            sleep(0.2)
        state = "was not created" if last <= 0 else "is incomplete"
        raise RuntimeError(f"RASAero export {fullPath} {state} after {self.fileTimeout__s:.0f} s")

    def _launchWindow(self, buttonTitle, isTarget, what):
        """Click a main-window toolbar button and wait for the window it opens."""
        known = {w.handle for w in self._visibleWindows()}
        buttons = [b for t in self.main.children(control_type="ToolBar")
                   for b in t.children(control_type="Button")
                   if b.window_text() == buttonTitle]
        if not buttons:
            raise RuntimeError(f"RASAero toolbar button {buttonTitle!r} not found")
        self._click(buttons[0], self.main)
        return self._uia(self._waitFor(known, isTarget, what))

    @staticmethod
    def _legacy(element):
        from pywinauto.uia_defines import get_elem_interface
        return get_elem_interface(element.element_info.element, "LegacyIAccessible")

    @staticmethod
    def _gridCells(window):
        """DataGridView cells by name, first occurrence wins (the flight
        grid has two columns called "Max Alt (ft)")."""
        cells = {}
        for d in window.descendants(control_type="DataItem"):
            cells.setdefault(d.window_text(), d)
        return cells

    def exportFlightSimulation(self, timeBase: float = 0.01):
        """Run the RASAero II flight simulation and export it to CSV.

        Parameters
        ----------
        timeBase
            Desired export time step in seconds.  Snapped down to the nearest
            valid RASAero option: 0.01, 0.1, 0.5, or 1.0.
        """
        import warnings

        snapped = max([v for v in self._TIME_BASE_RADIO if v <= timeBase], default=0.01)
        if snapped != timeBase:
            warnings.warn(f"Time base {timeBase} snapped to {snapped}")

        self._start(self.rocketDefinitionPath)
        try:

            flight = self._launchWindow(
                "Flight Simulation", lambda w: w.window_text() == "Flight",
                "the Flight Simulation window")
            known = {w.handle for w in self._visibleWindows()}

            # Run, then wait for a result in the grid, closing any warning
            # pop-ups (e.g. "Marginal Stability") as they appear
            self._menu(flight, "Simulations", "Rerun All Simulations")
            deadline = time() + self.simulationTimeout__s
            seen, firstSeen = [], {}
            while True:
                seen += self._closePopups(known, firstSeen)
                cells = self._gridCells(flight)
                if self._legacy(cells["Max Alt (ft) Row 0"]).CurrentValue not in ("", "0", None):
                    break
                if time() > deadline:
                    raise RuntimeError(
                        f"RASAero flight simulation produced no result. RASAero showed: {seen}")
                sleep(0.5)
            # Give an end-of-run pop-up time to appear, then close it
            sleep(2.0)
            self._closePopups(known, firstSeen, grace=0)

            # "View Data" is a button cell scrolled out of view: selecting it
            # makes the grid scroll to it, then it can be clicked
            self._legacy(cells["ViewData Row 0"]).Select(3)  # focus + select
            sleep(self.settleDelay__s)
            viewData = self._gridCells(flight)["ViewData Row 0"]
            self._click(viewData, flight)

            # The data window is also titled "Flight"; it has a File menu.
            # RASAero re-shows any stability warning first.
            def isDataWindow(w):
                if w.window_text() != "Flight":
                    return False
                bars = [c for c in self._uia(w).children()
                        if c.element_info.control_type == "MenuBar"]
                return any(m.window_text() == "File" for b in bars for m in b.children())
            data = self._uia(self._waitFor(
                known, isDataWindow, "the flight data window",
                timeout=self.simulationTimeout__s))

            # File > Export > To CSV, choose the time base, save
            known = {w.handle for w in self._visibleWindows()}
            self._menu(data, "File", "Export", "To CSV")
            timeDialog = self._uia(self._waitFor(
                known, lambda w: w.window_text() == "CSV_Time Increment",
                "the CSV time increment dialog"))
            radio = [r for r in timeDialog.descendants(control_type="RadioButton")
                     if r.element_info.automation_id == self._TIME_BASE_RADIO[snapped]][0]
            self._click(radio, timeDialog)
            done = [b for b in timeDialog.descendants(control_type="Button")
                    if b.element_info.automation_id == "btn_Done"][0]
            known = {w.handle for w in self._visibleWindows()}
            self._click(done, timeDialog)
            self._saveAs(known, self.flightSimulationFullPath, self._flightCsvComplete)
        finally:
            self._quit()

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
    
    def exportAeroPlots(self, altitudes, progress=None, resume=False):
        """Export aero plot CSVs for each cumulative assembly and altitude.

        Components are stripped aft-to-fore from a working copy of the CDX1,
        because RASAero can analyse a lone nose cone but not lone fins.
        RASAero is restarted for every export so the previous Mach-Alt table
        is dropped.  *progress*, if given, is called as
        ``progress(done, total, component, altitude)`` after each export.

        With *resume*, existing complete CSVs are kept and their exports
        skipped; otherwise all old aeroplots CSVs are deleted first.  Only
        resume when the vehicle is unchanged since those CSVs were written.
        """
        aeroDir = os.path.dirname(self.aeroPlotsFullPath)
        if not resume and os.path.isdir(aeroDir):
            for f in os.listdir(aeroDir):
                if f.lower().startswith("aeroplots") and f.lower().endswith(".csv"):
                    os.remove(os.path.join(aeroDir, f))

        base, extension = os.path.splitext(self.rocketDefinitionPath)
        workingPath = f"{base}-working{extension}"
        shutil.copy(self.rocketDefinitionPath, workingPath)
        csvBase, csvExt = os.path.splitext(self.aeroPlotsFullPath)

        total = len(self.aftComponentOrder) * len(altitudes)
        done = 0
        try:
            for component in self.aftComponentOrder:
                for altitude in altitudes:
                    outPath = f"{csvBase}-{component.lower()}-{altitude:.0f}{csvExt}"
                    if (resume and os.path.isfile(outPath)
                            and self._aeroCsvComplete(outPath)):
                        done += 1
                        if progress:
                            progress(done, total, component, altitude)
                        continue

                    # Replace the Mach-Alt table with this altitude
                    self.removeCDX1Element(workingPath, "MachAlt")
                    root = ET.parse(workingPath).getroot()
                    machalt = ET.SubElement(root, "MachAlt")
                    for mach in (0, 25):
                        self.addElement(machalt, "Item", f"{mach}, {self.m2ft(altitude)}")
                    self.writeCDX1File(root, workingPath)

                    self._start(workingPath)
                    try:
                        plots = self._launchWindow(
                            "Aero Plots", lambda w: w.window_text() == "Aero Plots",
                            "the Aero Plots window")
                        known = {w.handle for w in self._visibleWindows()}
                        self._menu(plots, "File", "Export", "To CSV File")
                        self._saveAs(known, outPath, self._aeroCsvComplete)
                    finally:
                        self._quit()

                    done += 1
                    if progress:
                        progress(done, total, component, altitude)

                # Strip this component for the next, shorter, assembly
                self.removeCDX1Element(workingPath, component)
        finally:
            if os.path.isfile(workingPath):
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
        self.addElement(launchsite, "WindSpeed", 0)  # aeroplots must be generated in still air

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
