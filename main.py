import sys
import os
import shutil
import json
import ctypes
import config
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QFileDialog
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon

from ui.main_window import MainMenuScreen
from ui.create_new_project import CreateProjectScreen
from ui.transcription_progress_screen import TranscriptionProgressScreen
from ui.validation_results_screen import ValidationResultsScreen
from ui.open_project_screen import OpenProjectScreen
from ui.project_info_screen import ProjectInfoScreen
from ui.validate_staves_screen import ValidateStavesScreen
from ui.validate_notation_screen import ValidateNotationScreen

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(base_path, relative_path))

class MasterWindow(QMainWindow):
    """Central application controller that manages view routing and data passing."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("nanoScore")
        self.setWindowIcon(QIcon(resource_path(os.path.join("icons", "nanoScore.ico"))))
        self.resize(1280, 720)
        
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        # 1. Instantiate the individual screens
        self.main_menu = MainMenuScreen()
        self.create_project = CreateProjectScreen()
        self.progress_screen = TranscriptionProgressScreen()
        self.validation_screen = ValidationResultsScreen()
        self.open_project = OpenProjectScreen()
        self.project_info = ProjectInfoScreen()
        self.validate_staves = ValidateStavesScreen()
        self.validate_notation = ValidateNotationScreen()
        
        # 2. Add screens to the Stacked Widget
        self.stacked_widget.addWidget(self.main_menu)
        self.stacked_widget.addWidget(self.create_project)
        self.stacked_widget.addWidget(self.progress_screen)
        self.stacked_widget.addWidget(self.validation_screen)
        self.stacked_widget.addWidget(self.open_project)
        self.stacked_widget.addWidget(self.project_info)
        self.stacked_widget.addWidget(self.validate_staves)
        self.stacked_widget.addWidget(self.validate_notation)
        
        # 3. Connect basic navigation signals
        self.main_menu.go_to_create_project.connect(
            lambda: self.stacked_widget.setCurrentWidget(self.create_project)
        )
        self.main_menu.go_to_open_project.connect(self.on_go_to_open_project)
        self.create_project.go_back_requested.connect(
            lambda: self.stacked_widget.setCurrentWidget(self.main_menu)
        )
        self.progress_screen.cancel_transcription_requested.connect(
            lambda: self.stacked_widget.setCurrentWidget(self.main_menu)
        )
        self.validation_screen.exit_requested.connect(
            lambda: self.stacked_widget.setCurrentWidget(self.main_menu)
        )
        self.open_project.go_back_requested.connect(
            lambda: self.stacked_widget.setCurrentWidget(self.main_menu)
        )
        self.open_project.open_project_requested.connect(self.on_open_project_info)
        self.project_info.go_back_requested.connect(self.on_go_to_open_project)
        self.project_info.validation_requested.connect(self.on_open_validation_from_info)
        self.project_info.export_requested.connect(self.on_export_requested)
        self.project_info.resume_requested.connect(self.on_resume_transcription)
        self.project_info.semiauto_requested.connect(self.on_resume_semiautomatic_transcription)
        self.validate_staves.exit_requested.connect(self.on_exit_validation)
        self.validate_notation.exit_requested.connect(self.on_exit_validation)
        self.validate_staves.forward_requested.connect(self.on_start_semiautomatic_phase2)
        self.validate_notation.forward_requested.connect(self.on_start_semiautomatic_phase3)
        
        # --- THE MAGIC HAPPENS HERE ---
        # Catch the emission from CreateProjectScreen to pass data & swap views
        self.create_project.start_transcription_requested.connect(self.on_start_transcription)
        self.create_project.start_semiautomatic_requested.connect(self.on_start_semiautomatic_transcription)
        
        self.progress_screen.transcription_finished.connect(self.on_transcription_finished)
        self.progress_screen.semiautomatic_ready.connect(self.on_semiautomatic_ready)
        self.progress_screen.semiautomatic_phase2_ready.connect(self.on_semiautomatic_phase2_ready)
        
        self.validation_screen.export_requested.connect(self.on_export_requested)

    def on_start_transcription(self, project_name, voices_data):
        """Starts a fully automatic transcription and switches to the progress screen."""
        self.stacked_widget.setCurrentWidget(self.progress_screen)
        self.progress_screen.start_transcription(project_name, voices_data)
        
    def on_start_semiautomatic_transcription(self, project_name, voices_data):
        """Starts Phase 1 of semiautomatic transcription (Staff Detection)."""
        self.stacked_widget.setCurrentWidget(self.progress_screen)
        self.progress_screen.start_transcription(project_name, voices_data, mode="semi")

    def on_start_semiautomatic_phase2(self):
        """Transitions to Phase 2 (Notes & Position Detection) after manual staff validation."""
        project_name = getattr(self, "current_project_name", "")
        if not project_name: return
        state_path = Path("Projects") / project_name / "project_state.json"
        voices_data = []
        if state_path.exists():
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            voices_dict = state.get("voices", {})
            for v_folder in sorted(voices_dict.keys()):
                v_name = voices_dict[v_folder].get("metadata", {}).get("voice_name", v_folder)
                voices_data.append({"name": v_name})
        self.stacked_widget.setCurrentWidget(self.progress_screen)
        self.progress_screen.start_transcription(project_name, voices_data, mode="semi2")

    def on_start_semiautomatic_phase3(self):
        """Transitions to Phase 3 (Score Reconstruction) after manual notation validation."""
        project_name = getattr(self, "current_project_name", "")
        if not project_name: return
        state_path = Path("Projects") / project_name / "project_state.json"
        voices_data = []
        if state_path.exists():
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            voices_dict = state.get("voices", {})
            for v_folder in sorted(voices_dict.keys()):
                v_name = voices_dict[v_folder].get("metadata", {}).get("voice_name", v_folder)
                voices_data.append({"name": v_name})
        self.stacked_widget.setCurrentWidget(self.progress_screen)
        self.progress_screen.start_transcription(project_name, voices_data, mode="semi3")

    def on_go_to_open_project(self):
        """Navigates to the Open Project screen and refreshes the project list."""
        self.stacked_widget.setCurrentWidget(self.open_project)
        self.open_project.load_projects()
        
    def on_open_project_info(self, project_name):
        """Loads metadata for a selected project and navigates to the Project Info screen."""
        self.current_project_name = project_name
        self.project_info.load_project_from_name(project_name)
        self.stacked_widget.setCurrentWidget(self.project_info)
        
    def on_open_validation_from_info(self, project_name):
        """Jumps directly to the validation results from the project info screen."""
        self.current_project_name = project_name
        self.stacked_widget.setCurrentWidget(self.validation_screen)
        QTimer.singleShot(100, lambda: self.validation_screen.load_project_results(project_name, show_popup=False))

    def on_resume_transcription(self, project_name):
        """Resumes a fully automatic transcription that was previously aborted or crashed."""
        state_path = Path("Projects") / project_name / "project_state.json"
        voices_data = []
        if state_path.exists():
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            
            # Reconstruct voices_data using the saved metadata
            voices_dict = state.get("voices", {})
            for v_folder in sorted(voices_dict.keys()):
                v_name = voices_dict[v_folder].get("metadata", {}).get("voice_name", v_folder)
                voices_data.append({"name": v_name})
                
        self.on_start_transcription(project_name, voices_data)

    def on_resume_semiautomatic_transcription(self, project_name):
        """Evaluates the JSON state of a semiautomatic project and routes the user to the correct pending phase."""
        state_path = Path("Projects") / project_name / "project_state.json"
        voices_data = []
        if not state_path.exists():
            return
            
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
            
        voices_dict = state.get("voices", {})
        for v_folder in sorted(voices_dict.keys()):
            v_name = voices_dict[v_folder].get("metadata", {}).get("voice_name", v_folder)
            voices_data.append({"name": v_name})
            
        all_staff_prediction_done = True
        all_position_classification_done = True
        
        for v_folder, v_data in voices_dict.items():
            pred_status = v_data.get("prediction_status", {})
            if pred_status.get("staff_prediction") != 1:
                all_staff_prediction_done = False
            if pred_status.get("position_classification") != 1 or pred_status.get("notes_prediction") != 1:
                all_position_classification_done = False

        if not all_staff_prediction_done:
            self.stacked_widget.setCurrentWidget(self.progress_screen)
            self.progress_screen.start_transcription(project_name, voices_data, mode="semi")
        elif not all_position_classification_done:
            self.on_semiautomatic_ready(project_name)
        else:
            self.on_semiautomatic_phase2_ready(project_name)

    def on_transcription_finished(self, project_name):
        """Handler for when the automatic transcription completely finishes."""
        self.current_project_name = project_name
        self.stacked_widget.setCurrentWidget(self.validation_screen)
        # Delay slightly to allow the UI to transition before the popup blocks it
        QTimer.singleShot(100, lambda: self.validation_screen.load_project_results(project_name))
        
    def on_semiautomatic_ready(self, project_name):
        """Handler for when Phase 1 finishes, routing to the Validate Staves screen."""
        self.current_project_name = project_name
        self.stacked_widget.setCurrentWidget(self.validate_staves)
        project_path = Path("Projects") / project_name
        self.validate_staves.load_voices_from_disk(str(project_path))

    def on_semiautomatic_phase2_ready(self, project_name):
        """Handler for when Phase 2 finishes, routing to the Validate Notation screen."""
        self.current_project_name = project_name
        self.stacked_widget.setCurrentWidget(self.validate_notation)
        project_path = Path("Projects") / project_name
        self.validate_notation.load_voices_from_disk(str(project_path))
        
    def on_exit_validation(self):
        """Stops any background prediction tasks and returns to the main menu."""
        self.progress_screen.force_cancel()
        self.stacked_widget.setCurrentWidget(self.main_menu)

    def on_export_requested(self):
        """Opens a file dialog allowing the user to save a copy of the final MusicXML file."""
        if not hasattr(self, 'current_project_name'):
            return
        source_xml = Path("Projects") / self.current_project_name / f"{self.current_project_name}.musicxml"
        if not source_xml.exists():
            return
            
        dest_path, _ = QFileDialog.getSaveFileName(
            self, "Export MusicXML", f"{self.current_project_name}.musicxml", "MusicXML Files (*.musicxml)"
        )
        if dest_path:
            shutil.copy2(source_xml, dest_path)

if __name__ == "__main__":
    # Tell Windows to treat this script as a distinct application (Fixes Taskbar Icon)
    try:
        myappid = f'nanoscore.app.{config.APP_VERSION}'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass
        
    
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path(os.path.join("icons", "nanoScore.ico"))))
    window = MasterWindow()
    window.show()
    
    # Brute-force the taskbar icon via Windows API (Fixes flaky loading in dev mode)
    if os.name == 'nt':
        hwnd = int(window.winId()) # Get the raw Windows window handle
        icon_path = resource_path(os.path.join("icons", "nanoScore.ico"))
        
        # Dynamically get the system's preferred icon sizes (accounts for display scaling / high DPI)
        SM_CXSMICON, SM_CYSMICON = 49, 50
        SM_CXICON, SM_CYICON = 11, 12
        
        cx_sm = ctypes.windll.user32.GetSystemMetrics(SM_CXSMICON)
        cy_sm = ctypes.windll.user32.GetSystemMetrics(SM_CYSMICON)
        cx_lg = ctypes.windll.user32.GetSystemMetrics(SM_CXICON)
        cy_lg = ctypes.windll.user32.GetSystemMetrics(SM_CYICON)
        
        LR_LOADFROMFILE = 0x0010
        hicon_small = ctypes.windll.user32.LoadImageW(0, icon_path, 1, cx_sm, cy_sm, LR_LOADFROMFILE)
        hicon_big = ctypes.windll.user32.LoadImageW(0, icon_path, 1, cx_lg, cy_lg, LR_LOADFROMFILE)
        
        if hicon_small:
            ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon_small) # Force Small Icon (Taskbar)
        if hicon_big:
            ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon_big) # Force Big Icon (Alt+Tab)
            
    sys.exit(app.exec())