import sys
import os
import shutil
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFrame, QListWidget, QListWidgetItem,
                             QMessageBox, QDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThread
from PyQt6.QtSvgWidgets import QSvgWidget


class SizeCalculatorWorker(QThread):
    """Runs the heavy folder size calculation in the background."""
    size_calculated = pyqtSignal(int)

    def __init__(self, folder_path):
        super().__init__()
        """Initializes the worker with a target folder path and a cancellation flag."""
        self.folder_path = folder_path
        self._is_cancelled = False

    def run(self):
        """Iterates through all files in the folder, summing their sizes while checking for cancellation."""
        if not self.folder_path.exists():
            self.size_calculated.emit(0)
            return
        total_size_bytes = 0
        for f in self.folder_path.glob('**/*'):
            if self._is_cancelled:
                return
            if f.is_file():
                total_size_bytes += f.stat().st_size
        size_mb = round(total_size_bytes / (1024 * 1024))
        if not self._is_cancelled:
            self.size_calculated.emit(size_mb)

    def cancel(self):
        """Flags the thread to stop processing early to prevent hanging on screen transitions."""
        self._is_cancelled = True



class DeleteProjectDialog(QDialog):
    """A beautifully styled, custom popup to confirm project deletion."""
    def __init__(self, project_name, parent=None):
        super().__init__(parent)
        """Constructs a frameless, modal warning dialog asking the user to confirm project deletion."""
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(450, 220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

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

        # Red Title for warning
        title = QLabel("Delete Project")
        title.setStyleSheet("color: #D32F2F; font-size: 26px; font-weight: bold; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Inject the project name into the description!
        desc = QLabel(f"Are you sure you want to permanently delete\n'{project_name}'?")
        desc.setStyleSheet("color: #333333; font-size: 16px; border: none; margin-top: 10px;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Buttons Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)

        delete_btn = QPushButton("Yes, Delete")
        delete_btn.setFixedSize(140, 40)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: white; color: #D32F2F; font-weight: bold; 
                border-radius: 8px; font-size: 16px; border: 2px solid #D32F2F;
            }
            QPushButton:hover { background-color: #FFF0F2; }
        """)
        # accept() means the user clicked YES to deleting
        delete_btn.clicked.connect(self.accept) 

        keep_btn = QPushButton("No, Keep it")
        keep_btn.setFixedSize(140, 40)
        keep_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        keep_btn.setStyleSheet("""
            QPushButton {
                background-color: #026BBC; color: white; font-weight: bold; border-radius: 8px; font-size: 16px;
            }
            QPushButton:hover { background-color: #005BB5; }
        """)
        # reject() means the user wants to close the popup and keep the project
        keep_btn.clicked.connect(self.reject) 

        btn_layout.addStretch()
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(keep_btn)
        btn_layout.addStretch()

        bg_layout.addWidget(title)
        bg_layout.addWidget(desc)
        bg_layout.addStretch()
        bg_layout.addLayout(btn_layout)

        layout.addWidget(bg_frame)



# --- REUSED CUSTOM BUTTONS ---
class SvgTextHoverButton(QPushButton):
    def __init__(self, text, normal_svg_path, hover_svg_path, icon_size=24, width=150):
        super().__init__()
        self.normal_svg = normal_svg_path
        self.hover_svg = hover_svg_path
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: transparent; border: none;")
        self.setFixedSize(width, icon_size + 16)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 2) 
        layout.setSpacing(8) 
        self.icon_widget = QSvgWidget(self.normal_svg)
        self.icon_widget.setFixedSize(icon_size, icon_size)
        self.icon_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.icon_widget.setStyleSheet("background: transparent; border: none;")
        self.text_label = QLabel(text)
        self.text_label.setStyleSheet("color: white; font-size: 20px; font-weight: bold; background: transparent; border: none;")
        layout.addWidget(self.icon_widget)
        layout.addWidget(self.text_label)
        layout.addStretch()

    def enterEvent(self, event):
        self.icon_widget.load(self.hover_svg)
        self.text_label.setStyleSheet("color: #CCCCCC; font-size: 20px; font-weight: bold; background: transparent; border: none;")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.icon_widget.load(self.normal_svg)
        self.text_label.setStyleSheet("color: white; font-size: 20px; font-weight: bold; background: transparent; border: none;")
        super().leaveEvent(event)

class SvgHoverButton(QPushButton):
    def __init__(self, normal_svg_path, hover_svg_path, icon_size=28):
        super().__init__()
        self.normal_svg = normal_svg_path
        self.hover_svg = hover_svg_path
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: transparent; border: none;")
        self.setFixedSize(icon_size + 10, icon_size + 10) 
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) 
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_widget = QSvgWidget(self.normal_svg)
        self.icon_widget.setFixedSize(icon_size, icon_size)
        self.icon_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.icon_widget.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.icon_widget)

    def enterEvent(self, event):
        self.icon_widget.load(self.hover_svg)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.icon_widget.load(self.normal_svg)
        super().leaveEvent(event)


# --- NEW ROW WIDGET ---
class ProjectRowWidget(QWidget):
    open_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str, QWidget) # Sends the project name and the widget itself

    def __init__(self, project_name, size_text):
        super().__init__()
        """Builds a clickable row containing the project name, its calculated size, and a delete button."""
        self.project_name = project_name
        self.setCursor(Qt.CursorShape.PointingHandCursor) # Make the whole row look clickable

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        
        self.box = QFrame()
        self.box.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 2px solid #026BBC; 
                border-radius: 12px;
            }
            QFrame:hover { background-color: #FAFAFA; }
        """)
        box_layout = QHBoxLayout(self.box)
        box_layout.setContentsMargins(20, 10, 15, 10)
        
        # 1. Project Name
        name_label = QLabel(self.project_name)
        name_label.setStyleSheet("color: #026BBC; font-size: 22px; font-weight: bold; border: none; background: transparent;")
        
        # 2. Size Label
        self.size_label = QLabel(size_text)
        self.size_label.setStyleSheet("color: #026BBC; font-size: 20px; border: none; background: transparent;")
        
        # 3. Trash Can Button
        self.trash_btn = SvgHoverButton("icons/Trash.svg", "icons/Trash_X_mark_red.svg", icon_size=28)
        self.trash_btn.clicked.connect(self.handle_delete_click)

        # Assemble the row
        box_layout.addWidget(name_label)
        box_layout.addStretch(1) # Pushes the size and trash to the right
        box_layout.addWidget(self.size_label)
        box_layout.addSpacing(15)
        box_layout.addWidget(self.trash_btn)
        
        layout.addWidget(self.box)

    def update_size(self, size_mb):
        """Updates the size label once the background SizeCalculatorWorker finishes."""
        self.size_label.setText(f"{size_mb} MB")

    def mousePressEvent(self, event):
        """This triggers when the user clicks ANYWHERE on the row (except the trash can)."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_requested.emit(self.project_name)
            
    def handle_delete_click(self):
        """Emits the delete signal, passing the row itself so the parent can remove it from the list."""
        self.delete_requested.emit(self.project_name, self)


# --- MAIN SCREEN WIDGET ---
class OpenProjectScreen(QWidget):
    go_back_requested = pyqtSignal()
    open_project_requested = pyqtSignal(str) # Tells master window to load this project

    def __init__(self):
        super().__init__()
        """Constructs the Open Project screen, including the header, dynamically populated list, and thread management."""
        self.setStyleSheet("background-color: #FAFAFA;")
        self.size_threads = []
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 1. Header Bar ---
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet("background-color: #026BBC;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        self.back_btn = SvgTextHoverButton("Go back", "icons/Back.svg", "icons/Back_gray.svg", icon_size=24, width=150)
        self.back_btn.clicked.connect(self.handle_go_back)

        title_label = QLabel("Open project")
        title_label.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Absolute Centering Trick
        left_container = QWidget()
        left_container.setFixedWidth(200)
        left_layout = QHBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.back_btn, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        right_container = QWidget()
        right_container.setFixedWidth(200) # Must match the left side exactly!
        
        header_layout.addWidget(left_container)
        header_layout.addWidget(title_label, 1, Qt.AlignmentFlag.AlignCenter) 
        header_layout.addWidget(right_container)
        
        main_layout.addWidget(header)

        # --- 2. Content Area ---
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(150, 40, 150, 40)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # --- The Scrollable List ---
        self.project_list = QListWidget()
        self.project_list.setFixedWidth(700)
        self.project_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.project_list.setStyleSheet("""
            QListWidget { border: none; background: transparent; outline: none; }
            QListWidget:focus { outline: none; border: none; }
            QListWidget::item { background: transparent; border: none; outline: none; }
            QListWidget::item:selected { background: transparent; }
            QScrollBar:vertical { border: none; background: transparent; width: 8px; margin: 0px 0px 0px 0px; }
            QScrollBar::handle:vertical { background: #CCCCCC; min-height: 30px; border-radius: 4px; }
            QScrollBar::handle:vertical:hover { background: #AAAAAA; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; background: none; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; } 
        """)
        
        content_layout.addWidget(self.project_list, 1, Qt.AlignmentFlag.AlignHCenter)
        main_layout.addWidget(content_widget, 1)

    def handle_go_back(self):
        """Safely cancel all background threads before navigating away."""
        for worker in self.size_threads:
            if worker.isRunning():
                worker.cancel()
                worker.wait()
        self.go_back_requested.emit()

    def load_projects(self):
        """Scans the Projects directory, populates the list with placeholders, and spawns background threads for size calculation."""
        for worker in self.size_threads:
            if worker.isRunning():
                worker.cancel()
                worker.wait()
        self.project_list.clear()
        self.size_threads.clear()
        projects_dir = Path("Projects")
        
        if not projects_dir.exists():
            return # Folder doesn't exist yet, list stays empty

        # Find all immediate subdirectories in the Projects folder
        for project_folder in projects_dir.iterdir():
            if project_folder.is_dir():
                # Add it to the UI with placeholder size
                row_widget = self.add_project_row(project_folder.name, "-- MB")
                
                # Calculate size in a background thread to completely avoid UI freeze
                worker = SizeCalculatorWorker(project_folder)
                worker.size_calculated.connect(row_widget.update_size)
                self.size_threads.append(worker) # Keep reference to avoid garbage collection
                worker.start()

    def add_project_row(self, name, size_text):
        """Creates a new ProjectRowWidget, connects its interactive signals, and appends it to the visual list."""
        row_widget = ProjectRowWidget(name, size_text)
        row_widget.open_requested.connect(self.handle_open_project)
        row_widget.delete_requested.connect(self.handle_delete_project)
        
        list_item = QListWidgetItem(self.project_list)
        list_item.setSizeHint(QSize(100, 75)) # 100px width allows it to shrink automatically when scrollbar appears
        
        self.project_list.addItem(list_item)
        self.project_list.setItemWidget(list_item, row_widget)
        
        return row_widget

    def handle_open_project(self, project_name):
        """Safely stops background scanning and tells the MasterWindow to navigate to the project info screen."""
        print(f"Opening project: {project_name}")
        for worker in self.size_threads:
            if worker.isRunning():
                worker.cancel()
                worker.wait()
        self.open_project_requested.emit(project_name)

    def handle_delete_project(self, project_name, row_widget):
        """Displays a confirmation dialog, and if accepted, deletes the project folder and removes the row from the UI."""
        # 1. Open our new beautifully styled dialog
        dialog = DeleteProjectDialog(project_name, self)
        
        # 2. Wait for the user's response
        if dialog.exec() == QDialog.DialogCode.Accepted:
            print(f"Deleting project: {project_name} from disk...")
            
            project_path = Path("Projects") / project_name
            if project_path.exists() and project_path.is_dir():
                shutil.rmtree(project_path)
            
            # Remove the row from the UI visually
            for i in range(self.project_list.count()):
                item = self.project_list.item(i)
                if self.project_list.itemWidget(item) == row_widget:
                    self.project_list.takeItem(i)
                    break

# --- For standalone testing ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OpenProjectScreen()
    window.resize(1280, 720)
    
    # Manually add some dummy rows to see how it looks before the real folder is scanned
    window.add_project_row("Beethoven_Opus1", "320 MB")
    window.add_project_row("Mozart_Symphony_40", "285 MB")
    window.add_project_row("Chopin_Nocturnes", "305 MB")
    
    window.show()
    sys.exit(app.exec())