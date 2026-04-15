import sys
import json
import datetime
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFrame, QListWidget, QListWidgetItem,
                             QProgressBar, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThread
from PyQt6.QtSvgWidgets import QSvgWidget


class SizeCalculatorWorker(QThread):
    """Runs the heavy folder size calculation in the background."""
    size_calculated = pyqtSignal(int)

    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path

    def run(self):
        if not self.folder_path.exists():
            self.size_calculated.emit(0)
            return
        total_size_bytes = sum(f.stat().st_size for f in self.folder_path.glob('**/*') if f.is_file())
        size_mb = round(total_size_bytes / (1024 * 1024))
        self.size_calculated.emit(size_mb)

class SvgTextHoverButton(QPushButton):
    """Reused custom back button."""
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


class VoiceStatusRowWidget(QWidget):
    """The custom row for the progress of each voice."""
    def __init__(self, voice_name, steps_finished, total_steps=4):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        
        self.box = QFrame()
        self.box.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 2px solid #026BBC; 
                border-radius: 12px;
            }
        """)
        box_layout = QVBoxLayout(self.box)
        box_layout.setContentsMargins(20, 15, 20, 15)
        box_layout.setSpacing(10)

        # Top row: Name and Status Text
        text_layout = QHBoxLayout()
        
        name_label = QLabel(voice_name)
        name_label.setStyleSheet("color: #333333; font-size: 18px; border: none;")
        
        status_label = QLabel(f"{steps_finished} steps of {total_steps} are finished")
        status_label.setStyleSheet("color: #026BBC; font-size: 16px; border: none;")
        status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        text_layout.addWidget(name_label)
        text_layout.addStretch()
        text_layout.addWidget(status_label)

        # Bottom row: The custom Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setTextVisible(False) # Hides the default percentage text
        self.progress_bar.setMaximum(total_steps)
        self.progress_bar.setValue(steps_finished)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #E0E0E0;
                border-radius: 5px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #026BBC;
                border-radius: 5px;
            }
        """)

        box_layout.addLayout(text_layout)
        box_layout.addWidget(self.progress_bar)
        
        layout.addWidget(self.box)


class ProjectInfoScreen(QWidget):
    go_back_requested = pyqtSignal()
    resume_requested = pyqtSignal(str)
    semiauto_requested = pyqtSignal(str)
    validation_requested = pyqtSignal(str)
    export_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.setStyleSheet("background-color: #FAFAFA;")
        self.current_project = ""
        self.size_thread = None
        
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
        self.back_btn.clicked.connect(self.go_back_requested.emit)

        title_label = QLabel("Project info")
        title_label.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        left_container = QWidget()
        left_container.setFixedWidth(200)
        QHBoxLayout(left_container).addWidget(self.back_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        left_container.layout().setContentsMargins(0,0,0,0)

        right_container = QWidget()
        right_container.setFixedWidth(200)

        header_layout.addWidget(left_container)
        header_layout.addWidget(title_label, 1, Qt.AlignmentFlag.AlignCenter) 
        header_layout.addWidget(right_container)
        
        main_layout.addWidget(header)

        # --- 2. Center Constrained Content Area ---
        # This layout ensures the content never exceeds 1100px wide, keeping columns tight!
        scroll_constraint_layout = QHBoxLayout()
        scroll_constraint_layout.addStretch(1) # Pushes from left

        self.content_container = QWidget()
        self.content_container.setMaximumWidth(1100) 
        content_layout = QVBoxLayout(self.content_container)
        content_layout.setContentsMargins(20, 40, 20, 40)
        
        # Two Columns Layout
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(20) # Gap between left and right column

        # --- LEFT COLUMN (Info) ---
        left_col = QWidget()
        left_col.setMinimumWidth(1)
        left_col.setMaximumWidth(500) # 540  #Locks it to exactly half the container width
        left_layout = QVBoxLayout(left_col)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        left_layout.setSpacing(25)

        self.project_name_lbl = QLabel("<Project name>")
        self.project_name_lbl.setStyleSheet("color: #026BBC; font-size: 32px; font-weight: bold;")
        self.project_name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.project_name_lbl.setMinimumWidth(1) # Allows the label to shrink and wrap instead of pushing

        self.project_name_lbl.setWordWrap(True)
        left_layout.addWidget(self.project_name_lbl)

        # Metadata Labels (Using Rich Text to style the titles vs the data)
        self.created_lbl = QLabel()
        self.modified_lbl = QLabel()
        self.location_lbl = QLabel()
        self.location_lbl.setWordWrap(True) # Allows wrapping
        self.size_lbl = QLabel()

        for lbl in [self.created_lbl, self.modified_lbl, self.location_lbl, self.size_lbl]:
            lbl.setStyleSheet("font-size: 18px;")
            left_layout.addWidget(lbl)

        columns_layout.addWidget(left_col, 1)

        # --- RIGHT COLUMN (Status) ---
        right_col = QWidget()
        right_col.setMinimumWidth(1)
        right_col.setMaximumWidth(500) # 540  # Keeps the right column symmetrically locked
        right_layout = QVBoxLayout(right_col)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        right_layout.setSpacing(15)

        status_title = QLabel("Status")
        status_title.setStyleSheet("color: #333333; font-size: 32px; font-weight: bold;")
        status_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(status_title)

        self.voice_list = QListWidget()
        # ODSTRANĚNO: self.voice_list.setFixedWidth(500) 
        self.voice_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.voice_list.setStyleSheet("""
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
        
        # UPRAVENO: Přidáváme bez AlignHCenter, aby se seznam přirozeně roztáhl
        right_layout.addWidget(self.voice_list)

        columns_layout.addWidget(right_col, 1)
        content_layout.addLayout(columns_layout)
        content_layout.addSpacing(30)

        # --- BOTTOM BUTTONS ---
        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.setSpacing(20)

        # Button 1: Semiautomatic
        self.semi_btn = QPushButton("Resume semiautomatic transcription")
        self.semi_btn.setFixedHeight(60)
        self.semi_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.semi_btn.setStyleSheet("""
            QPushButton { 
                background-color: white; color: #026BBC; font-size: 20px; font-weight: bold; 
                border-radius: 12px; border: 2px solid #026BBC; 
            } 
            QPushButton:hover { background-color: #E6F0FA; }
        """)
        self.semi_btn.clicked.connect(lambda: self.semiauto_requested.emit(self.current_project))

        # Button 2: Resume 
        self.resume_btn = QPushButton("Resume automatic transcription")
        self.resume_btn.setFixedHeight(60)
        self.resume_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.resume_btn.setStyleSheet("""
            QPushButton { 
                background-color: #026BBC; color: white; font-size: 20px; font-weight: bold; border-radius: 12px; 
            } 
            QPushButton:hover { background-color: #005BB5; }
        """)
        self.resume_btn.clicked.connect(lambda: self.resume_requested.emit(self.current_project))

        # Button 3: Export (Only shows if 100% done)
        self.export_btn = QPushButton("Export copy")
        self.export_btn.setFixedHeight(60)
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.setStyleSheet("""
            QPushButton { 
                background-color: white; color: #026BBC; font-size: 20px; font-weight: bold; 
                border-radius: 12px; border: 2px solid #026BBC; 
            } 
            QPushButton:hover { background-color: #E6F0FA; }
        """)
        self.export_btn.clicked.connect(lambda: self.export_requested.emit(self.current_project))
        self.export_btn.setVisible(False)

        # Button 4: Validation (Only shows if 100% done)
        self.val_btn = QPushButton("Open validation results")
        self.val_btn.setFixedHeight(60)
        self.val_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.val_btn.setStyleSheet("""
            QPushButton { 
                background-color: #026BBC; color: white; font-size: 20px; font-weight: bold; border-radius: 12px; 
            } 
            QPushButton:hover { background-color: #005BB5; }
        """)
        self.val_btn.clicked.connect(lambda: self.validation_requested.emit(self.current_project))
        self.val_btn.setVisible(False) # Hidden by default

        self.buttons_layout.addWidget(self.semi_btn)
        self.buttons_layout.addWidget(self.resume_btn)
        self.buttons_layout.addWidget(self.export_btn)
        self.buttons_layout.addWidget(self.val_btn)

        self.semi_btn.setMinimumWidth(500)
        self.resume_btn.setMinimumWidth(500)
        self.export_btn.setMinimumWidth(500)
        self.val_btn.setMinimumWidth(500)

        content_layout.addLayout(self.buttons_layout)

        # Add the 1100px container to the centered layout
        scroll_constraint_layout.addWidget(self.content_container)
        scroll_constraint_layout.addStretch(1) # Pushes from right
        
        main_layout.addLayout(scroll_constraint_layout, 1)

    def load_project_from_name(self, project_name):
        self.current_project = project_name
        base_dir = Path("Projects") / project_name
        state_file = base_dir / "project_state.json"
        
        if not state_file.exists():
            return
            
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
            
        meta = state.get("project_metadata", {})
        global_state = state.get("global_state", {})
        voices_dict = state.get("voices", {})
        
        def format_date(iso_str):
            try:
                dt = datetime.datetime.fromisoformat(iso_str)
                return dt.strftime("%H:%M - %d.%m.%Y")
            except Exception:
                return iso_str
                
        created = format_date(meta.get("created_at", ""))
        modified = format_date(meta.get("last_modified", ""))
        
        voices_list = []
        num_voices = len(voices_dict)
        
        for v_folder, v_data in voices_dict.items():
            v_name = v_data.get("metadata", {}).get("voice_name", v_folder)
            pred_status = v_data.get("prediction_status", {})
            
            steps_done = 0
            if pred_status.get("staff_prediction") == 1:
                steps_done = 1
                if pred_status.get("notes_prediction") == 1:
                    steps_done = 2
                    if pred_status.get("position_classification") == 1:
                        steps_done = 3
                        if global_state.get("measure_duration_validation_finished") == 1 or \
                           (num_voices == 1 and global_state.get("combined_musicxml_saved") == 1):
                            steps_done = 4
                            
            voices_list.append({
                "name": v_name,
                "steps_done": steps_done
            })
            
        project_data = {
            "name": project_name,
            "created": created,
            "modified": modified,
            "path": str(base_dir.absolute()),
            "size_mb": "--",
            "voices": voices_list
        }
        self.load_project_data(project_data)
        
        # Calculate size in the background
        self.size_thread = SizeCalculatorWorker(base_dir)
        self.size_thread.size_calculated.connect(self._update_size_label)
        self.size_thread.start()

    def _update_size_label(self, size_mb):
        self.size_lbl.setText(f"<span style='color: #333333; font-weight: bold;'>Size on disk:</span> <span style='color: #026BBC;'>{size_mb} MB</span>")

    def load_project_data(self, project_data):
        """
        Expects a dictionary like:
        {
            "name": "Beethoven Opus 1",
            "created": "14:30 - 12.10.2024",
            "modified": "16:45 - 13.10.2024",
            "path": "C:/Users/Music/Documents/nanoScore/Projects/Beethoven_Opus_1",
            "size_mb": 14.5,
            "voices": [
                {"name": "Soprano", "steps_done": 4},
                {"name": "Alto", "steps_done": 2}
            ]
        }
        """
        self.current_project = project_data["name"]
        
        # Inject zero-width spaces after underscores and dashes so long unbroken names wrap properly
        breakable_name = project_data["name"].replace("_", "_\u200B").replace("-", "-\u200B")
        self.project_name_lbl.setText(breakable_name)

        # Format metadata with Rich Text
        def format_meta(label, value):
            return f"<span style='color: #333333; font-weight: bold;'>{label}</span> <span style='color: #026BBC;'>{value}</span>"

        self.created_lbl.setText(format_meta("Created:", project_data["created"]))
        self.modified_lbl.setText(format_meta("Last modified:", project_data["modified"]))
        self.size_lbl.setText(format_meta("Size on disk:", f"{project_data['size_mb']} MB"))

        # Zero-width space trick for the path!
        breakable_path = project_data["path"].replace("\\", "\\\u200B").replace("/", "/\u200B")
        self.location_lbl.setText(format_meta("Location:", breakable_path))

        # Populate the Status List
        self.voice_list.clear()
        all_finished = True
        
        for voice in project_data["voices"]:
            steps = voice["steps_done"]
            if steps < 4:
                all_finished = False
                
            row = VoiceStatusRowWidget(voice["name"], steps)
            item = QListWidgetItem(self.voice_list)
            item.setSizeHint(QSize(100, 95)) # Perfect height for the box
            self.voice_list.addItem(item)
            self.voice_list.setItemWidget(item, row)

        num_voices = len(project_data["voices"])

        # Dynamic Button Logic
        if all_finished:
            # Hide the resume buttons, show the validation button
            self.semi_btn.setVisible(False)
            self.resume_btn.setVisible(False)
            self.export_btn.setVisible(True)
            self.val_btn.setVisible(True)

            if num_voices <= 1:
                self.val_btn.setEnabled(False)
                self.val_btn.setStyleSheet("""
                    QPushButton { 
                        background-color: #CCCCCC; color: #777777; font-size: 20px; font-weight: bold; border-radius: 12px; 
                    }
                """)
            else:
                self.val_btn.setEnabled(True)
                self.val_btn.setStyleSheet("""
                    QPushButton { 
                        background-color: #026BBC; color: white; font-size: 20px; font-weight: bold; border-radius: 12px; 
                    } 
                    QPushButton:hover { background-color: #005BB5; }
                """)
        else:
            # Show the resume buttons, hide the validation button
            self.semi_btn.setVisible(True)
            self.resume_btn.setVisible(True)
            self.export_btn.setVisible(False)
            self.val_btn.setVisible(False)


# --- For standalone testing ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProjectInfoScreen()
    window.resize(1280, 720)
    
    # Try changing "steps_done" to 4 for all voices to see the button automatically swap!
    dummy_data = {
        "name": "Mozart_Symphony_40",
        "created": "09:15 - 04.11.2025",
        "modified": "11:30 - 05.11.2025",
        "path": "C:/Users/Production/Documents/Music_Projects/nanoScore/Projects/Mozart_Symphony_40",
        "size_mb": 24.8,
        "voices": [
            {"name": "Violin I", "steps_done": 4},
            {"name": "Violin II", "steps_done": 4},
            {"name": "Viola", "steps_done": 2},
            {"name": "Cello", "steps_done": 0}
        ]
    }
    
    window.load_project_data(dummy_data)
    window.show()
    sys.exit(app.exec())