import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget
from ui.main_window import MainMenuScreen
from ui.create_new_project import CreateProjectScreen

class MasterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 1. Setup the One True Window
        self.setWindowTitle("nanoScore")
        self.resize(1280, 720)

        # 2. Create the Stacked Widget and make it the center of the window
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # 3. Import and initialize our separate screens
        self.main_menu = MainMenuScreen()
        self.create_project = CreateProjectScreen()

        # 4. Add the screens into the "deck of cards"
        self.stacked_widget.addWidget(self.main_menu)       # Index 0
        self.stacked_widget.addWidget(self.create_project)  # Index 1

        # 5. Connect the signals so they can swap the cards
        self.main_menu.go_to_create_project.connect(self.show_create_project)
        self.create_project.go_back_requested.connect(self.show_main_menu)

    def show_create_project(self):
        # Instantly swaps the view to the Create Project screen
        self.stacked_widget.setCurrentWidget(self.create_project)

    def show_main_menu(self):
        # Instantly swaps the view back to the Main Menu
        self.stacked_widget.setCurrentWidget(self.main_menu)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MasterWindow()
    window.show()
    sys.exit(app.exec())
