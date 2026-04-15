import sys
import shutil
import json
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QFileDialog
from PyQt6.QtCore import QTimer

from ui.main_window import MainMenuScreen
from ui.create_new_project import CreateProjectScreen
from ui.transcription_progress_screen import TranscriptionProgressScreen
from ui.validation_results_screen import ValidationResultsScreen
from ui.open_project_screen import OpenProjectScreen
from ui.project_info_screen import ProjectInfoScreen

class MasterWindow(QMainWindow):
    """Central application controller that manages view routing and data passing."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("nanoScore")
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
        
        # 2. Add screens to the Stacked Widget
        self.stacked_widget.addWidget(self.main_menu)
        self.stacked_widget.addWidget(self.create_project)
        self.stacked_widget.addWidget(self.progress_screen)
        self.stacked_widget.addWidget(self.validation_screen)
        self.stacked_widget.addWidget(self.open_project)
        self.stacked_widget.addWidget(self.project_info)
        
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
        
        # --- THE MAGIC HAPPENS HERE ---
        # Catch the emission from CreateProjectScreen to pass data & swap views
        self.create_project.start_transcription_requested.connect(self.on_start_transcription)
        self.progress_screen.transcription_finished.connect(self.on_transcription_finished)
        self.validation_screen.export_requested.connect(self.on_export_requested)

    def on_start_transcription(self, project_name, voices_data):
        self.stacked_widget.setCurrentWidget(self.progress_screen)
        self.progress_screen.start_transcription(project_name, voices_data)
        
    def on_go_to_open_project(self):
        self.stacked_widget.setCurrentWidget(self.open_project)
        self.open_project.load_projects()
        
    def on_open_project_info(self, project_name):
        self.current_project_name = project_name
        self.project_info.load_project_from_name(project_name)
        self.stacked_widget.setCurrentWidget(self.project_info)
        
    def on_open_validation_from_info(self, project_name):
        self.current_project_name = project_name
        self.stacked_widget.setCurrentWidget(self.validation_screen)
        QTimer.singleShot(100, lambda: self.validation_screen.load_project_results(project_name, show_popup=False))

    def on_resume_transcription(self, project_name):
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

    def on_transcription_finished(self, project_name):
        self.current_project_name = project_name
        self.stacked_widget.setCurrentWidget(self.validation_screen)
        # Delay slightly to allow the UI to transition before the popup blocks it
        QTimer.singleShot(100, lambda: self.validation_screen.load_project_results(project_name))
        
    def on_export_requested(self):
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
    app = QApplication(sys.argv)
    window = MasterWindow()
    window.show()
    sys.exit(app.exec())