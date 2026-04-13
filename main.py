import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from ui.main_window import MainMenuScreen
from ui.create_new_project import CreateProjectScreen
from ui.transcription_progress_screen import TranscriptionProgressScreen

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
        
        # 2. Add screens to the Stacked Widget
        self.stacked_widget.addWidget(self.main_menu)
        self.stacked_widget.addWidget(self.create_project)
        self.stacked_widget.addWidget(self.progress_screen)
        
        # 3. Connect basic navigation signals
        self.main_menu.go_to_create_project.connect(
            lambda: self.stacked_widget.setCurrentWidget(self.create_project)
        )
        self.create_project.go_back_requested.connect(
            lambda: self.stacked_widget.setCurrentWidget(self.main_menu)
        )
        self.progress_screen.cancel_transcription_requested.connect(
            lambda: self.stacked_widget.setCurrentWidget(self.main_menu)
        )
        
        # --- THE MAGIC HAPPENS HERE ---
        # Catch the emission from CreateProjectScreen to pass data & swap views
        self.create_project.start_transcription_requested.connect(self.on_start_transcription)

    def on_start_transcription(self, project_name, voices_data):
        self.stacked_widget.setCurrentWidget(self.progress_screen)
        self.progress_screen.start_transcription(project_name, voices_data)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MasterWindow()
    window.show()
    sys.exit(app.exec())