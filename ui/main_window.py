
import config
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QFrame, QDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtSvgWidgets import QSvgWidget



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



class SvgHoverButton(QPushButton):
    """A custom button that swaps SVG files on hover to simulate a color change."""
    def __init__(self, normal_svg_path, hover_svg_path, icon_size=35):
        super().__init__()
        self.normal_svg = normal_svg_path
        self.hover_svg = hover_svg_path

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: transparent; border: none;")

        # --- THE FIX ---
        # Make the outer button exactly big enough to hold the icon safely
        self.setFixedSize(icon_size + 10, icon_size + 10) 

        # Layout to perfectly center the SVG
        layout = QVBoxLayout(self)
        # Remove the bottom margin we had before so it perfectly centers
        layout.setContentsMargins(0, 0, 0, 0) 
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Create the razor-sharp SVG widget
        self.icon_widget = QSvgWidget(self.normal_svg)
        self.icon_widget.setFixedSize(icon_size, icon_size)
        self.icon_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.icon_widget.setStyleSheet("background: transparent; border: none;")

        layout.addWidget(self.icon_widget)

    # --- THE HOVER MAGIC ---
    def enterEvent(self, event):
        """Triggered when the mouse touches the button."""
        self.icon_widget.load(self.hover_svg)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Triggered when the mouse leaves the button."""
        self.icon_widget.load(self.normal_svg)
        super().leaveEvent(event)



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

        # --- SVG HAMBURGER (MENU) BUTTON ---
        self.hamburger_btn = SvgHoverButton("icons/Menu.svg", "icons/Menu_gray.svg", icon_size=35)
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

        # " ✕ close menu" button
        self.close_menu_btn = QPushButton()
        self.close_menu_btn.setFixedHeight(60) 
        self.close_menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_menu_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                border-bottom: 2px solid #026BBC; 
            }
            QPushButton:hover { background-color: #E6F0FA; }
        """)
        self.close_menu_btn.clicked.connect(self.toggle_drawer)

        # Put a layout INSIDE the close button to hold the icon perfectly
        close_layout = QHBoxLayout(self.close_menu_btn)
        close_layout.setContentsMargins(17, 0, 0, 4) 

        close_icon = QSvgWidget("icons/Cross.svg")
        close_icon.setFixedSize(50, 50)
        
        # Force complete transparency behind the SVG
        close_icon.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        close_icon.setStyleSheet("background: transparent; border: none;")

        # Add the icon to the layout and push it to the left
        close_layout.addWidget(close_icon)
        close_layout.addStretch()

        # "About" button
        self.about_btn = QPushButton()
        self.about_btn.setFixedHeight(60)
        self.about_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.about_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                border-bottom: 2px solid #026BBC; 
            }
            QPushButton:hover { background-color: #E6F0FA; }
        """)
        self.about_btn.clicked.connect(self.show_about_dialog)
        # --------------------------------------

        # 2. Put a layout INSIDE the button to hold the icon and text
        btn_layout = QHBoxLayout(self.about_btn)
        
        # offset format: (Left, Top, Right, Bottom)
        btn_layout.setContentsMargins(25, 0, 0, 4) 
        btn_layout.setSpacing(15) # Space between the icon and the text

        icon_widget = QSvgWidget("icons/Info.svg")
        icon_widget.setFixedSize(35, 35)
        
        # Delete the Qt white background just in case!
        icon_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        icon_widget.setStyleSheet("background: transparent; border: none;")
        
        # 4. Create the Text
        text_label = QLabel("About")
        text_label.setStyleSheet("color: #026BBC; font-size: 26px; font-weight: bold; background: transparent; border: none;")

        # 5. Add them to the button's layout
        btn_layout.addWidget(icon_widget)
        btn_layout.addWidget(text_label)
        btn_layout.addStretch() # Pushes everything to the left

        #self.about_btn.clicked.connect(self.show_about_dialog)

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