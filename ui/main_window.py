
import config
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QFrame, QDialog)
from PyQt6.QtCore import Qt, pyqtSignal



class AboutDialog(QDialog):
    """A beautifully styled, custom popup dialog for the About info."""
    def __init__(self, parent=None):
        super().__init__(parent)
        # Make the window frameless and transparent so we can draw our own rounded corners
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True) # This blocks the user from clicking the main app while open
        self.setFixedSize(400, 220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # The white visible box
        bg_frame = QFrame()
        bg_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 16px;
                border: 1px solid #CCCCCC;
            }
        """)
        bg_layout = QVBoxLayout(bg_frame)
        bg_layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel(f"{config.APP_NAME}")
        title.setStyleSheet("color: #026BBC; font-size: 28px; font-weight: bold; border: none; letter-spacing: -2px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        version = QLabel(f"Version {config.APP_VERSION}")
        version.setStyleSheet("color: #777777; font-size: 16px; border: none;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)

        desc = QLabel("A historical voice books transcription tool.")
        desc.setStyleSheet("color: #333333; font-size: 16px; border: none; margin-top: 10px;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        close_btn = QPushButton("Close")
        close_btn.setFixedSize(100, 40)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #026BBC; color: white; font-weight: bold; border-radius: 8px; font-size: 16px;
            }
            QPushButton:hover { background-color: #005BB5; }
        """)
        close_btn.clicked.connect(self.accept) # Closes the dialog

        bg_layout.addWidget(title)
        bg_layout.addWidget(version)
        bg_layout.addWidget(desc)
        bg_layout.addStretch()
        bg_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(bg_frame)



class MainMenuScreen(QWidget):
    # signal tells the Master Window to switch screens
    go_to_create_project = pyqtSignal() 

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #FAFAFA;") 

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 1. The Header Bar ---
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet("background-color: #026BBC;") 
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        self.hamburger_btn = QPushButton("≡")
        self.hamburger_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hamburger_btn.setStyleSheet(
            """
            QPushButton { 
            color: white; 
            font-size: 48px; 
            border: none; 
            background: transparent; 
            padding-bottom: 12px; 
            }
            QPushButton:hover { color: #CCCCCC; }
        """)

        self.hamburger_btn.clicked.connect(self.toggle_drawer)
        title_label = QLabel(config.APP_NAME)
        title_label.setStyleSheet(
            """
            color: white; 
            font-family: "Segoe UI"; 
            font-size: 40px;
            font-style: normal; 
            font-weight: 600; 
            line-height: normal; 
            margin-bottom: 4px;
            letter-spacing: -3px;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        right_spacer = QLabel()
        right_spacer.setFixedWidth(self.hamburger_btn.sizeHint().width())

        header_layout.addWidget(self.hamburger_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(title_label, 1, Qt.AlignmentFlag.AlignVCenter) 
        header_layout.addWidget(right_spacer, 0, Qt.AlignmentFlag.AlignVCenter)

        main_layout.addWidget(header)

        # --- 2. The Main Body (Buttons) ---
        body_widget = QWidget()
        body_layout = QVBoxLayout(body_widget)
        body_layout.setAlignment(Qt.AlignmentFlag.AlignCenter) 
        body_layout.setSpacing(20) 

        create_btn = QPushButton("+ Create new project")
        create_btn.setFixedSize(700, 120)
        create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #026BBC; color: white; font-size: 64px;
                font-style: normal; font-weight: 650; line-height: normal;
                border-radius: 20px; padding-bottom: 10px;
            }
            QPushButton:hover { background-color: #005BB5; }
        """)
        # EMIT THE SIGNAL INSTEAD OF OPENING A WINDOW
        create_btn.clicked.connect(self.go_to_create_project.emit)

        open_btn = QPushButton("Open existing project")
        open_btn.setFixedSize(700, 70) 
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: white; color: #026BBC; font-size: 42px;
                font-weight: 600; border-radius: 20px; border: 4px solid #026BBC; padding-bottom: 5px;
            }
            QPushButton:hover { background-color: #E6F0FA; }
        """)

        body_layout.addWidget(create_btn)
        body_layout.addWidget(open_btn)

        main_layout.addWidget(body_widget, 1)


        # --- The Overlay Layers ---
        # These are created after the main layout, so they float on top!
        # The Dark Background Overlay (Also acts as a giant button to close the menu)
        self.dim_overlay = QPushButton(self)
        self.dim_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 100); border: none;") # 100 is the opacity (0-255)
        self.dim_overlay.setVisible(False)
        self.dim_overlay.clicked.connect(self.toggle_drawer)

        # The Side Drawer Menu
        self.drawer_menu = QFrame(self)
        self.drawer_menu.setFixedWidth(280) 
        self.drawer_menu.setStyleSheet("background-color: #FFFFFF; border-right: 1px solid #CCCCCC;")
        self.drawer_menu.setVisible(False) 
        
        drawer_layout = QVBoxLayout(self.drawer_menu)
        drawer_layout.setContentsMargins(0, 0, 0, 0) 
        drawer_layout.setSpacing(0)

        self.close_menu_btn = QPushButton("✕")
        self.close_menu_btn.setFixedHeight(60) 
        self.close_menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_menu_btn.setStyleSheet("""
            QPushButton {
                color: #026BBC; font-size: 32px; background: transparent; border: none;
                border-bottom: 2px solid #026BBC; text-align: left; padding-left: 25px; padding-bottom: 4px;
            }
            QPushButton:hover { background-color: #E6F0FA; }
        """)
        self.close_menu_btn.clicked.connect(self.toggle_drawer)

        self.about_btn = QPushButton("ⓘ  About")
        self.about_btn.setFixedHeight(60)
        self.about_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.about_btn.setStyleSheet("""
            QPushButton {
                color: #026BBC; font-size: 26px; font-weight: bold; background: transparent; border: none;
                border-bottom: 2px solid #026BBC; text-align: left; padding-left: 20px; padding-bottom: 4px;
            }
            QPushButton:hover { background-color: #E6F0FA; }
        """)
        self.about_btn.clicked.connect(self.show_about_dialog)

        drawer_layout.addWidget(self.close_menu_btn)
        drawer_layout.addWidget(self.about_btn)
        drawer_layout.addStretch() 


    def resizeEvent(self, event):
        """This automatically runs when the window resizes to ensure the overlays stretch to fit."""
        super().resizeEvent(event)
        # Stretch the dim overlay to cover the whole screen
        self.dim_overlay.resize(self.size())
        # Stretch the drawer to reach the bottom of the screen
        self.drawer_menu.resize(280, self.height())


    def toggle_drawer(self):
        """Flips the visibility of the side menu."""
        is_visible = self.drawer_menu.isVisible()
        # Toggle both the drawer and the dark background
        self.dim_overlay.setVisible(not is_visible)
        self.drawer_menu.setVisible(not is_visible)

        # Ensure they are drawn on top of everything else
        if not is_visible:
            self.dim_overlay.raise_()
            self.drawer_menu.raise_()

    def show_about_dialog(self):
        # We close the drawer first for a cleaner transition
        self.toggle_drawer()
        
        # Open our beautiful custom popup
        dialog = AboutDialog(self)
        dialog.exec()