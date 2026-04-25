import sys
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFrame, QListWidget, QListWidgetItem, 
                             QDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtSvgWidgets import QSvgWidget
import json
from pathlib import Path
from collections import Counter



def parse_validation_results(json_data):
    """
    Analyzes the duration validation JSON report.
    Calculates total and consistent measures, and extracts detailed string comments and locations for any mismatches.
    """
    total_measures = len(json_data["measures"])
    consistent_measures = sum(1 for m in json_data["measures"] if m["is_equal"])
    
    # Grab the divisions (default to 1 just in case it's missing so we don't divide by zero!)
    divisions = json_data.get("divisions", 1) 
    voices = json_data.get("voices", [])
    
    def get_voice_name(idx):
        if idx < len(voices):
            return f"{voices[idx]} ({idx + 1})"
        return f"Voice {idx + 1}"

    mismatches = []

    for measure in json_data["measures"]:
        if not measure["is_equal"]:
            measure_num = measure["measure_number"]
            durations = measure["durations"]
            locations = measure["locations"]

            duration_counts = Counter(durations).most_common()

            # --- CASE 1: Every single voice is completely different ---
            if len(duration_counts) == len(durations):
                comment = "No majority detected (all voices have different lengths)"
                loc = locations[0]
                location_str = f"p{loc['page_id']}, s{loc['staff_number']} (and others)"

            # --- CASE 2: There is a dead tie ---
            elif duration_counts[0][1] == duration_counts[1][1]:
                # DIVIDE BY DIVISIONS HERE
                val1_beats = duration_counts[0][0] / divisions
                val2_beats = duration_counts[1][0] / divisions
                
                # The :g formatter drops unnecessary .0 decimals!
                comment = f"Conflicting lengths detected (Tie between {val1_beats:g} and {val2_beats:g} beats)"
                loc = locations[0]
                location_str = f"p{loc['page_id']}, s{loc['staff_number']} (and others)"

            # --- CASE 3: There is a clear majority ---
            else:
                majority_duration = duration_counts[0][0]
                outlier_indices = [i for i, d in enumerate(durations) if d != majority_duration]

                if len(outlier_indices) == 1:
                    # Exactly one voice is wrong
                    bad_idx = outlier_indices[0]
                    voice_name = get_voice_name(bad_idx)
                    
                    # DIVIDE BY DIVISIONS HERE
                    bad_beats = durations[bad_idx] / divisions
                    majority_beats = majority_duration / divisions
                    
                    comment = f"{voice_name} has {bad_beats:g} beats (Majority has {majority_beats:g} beats)"
                    loc = locations[bad_idx]
                    location_str = f"p{loc['page_id']}, s{loc['staff_number']}"
                    
                else:
                    majority_beats = majority_duration / divisions
                    comment = f"Multiple voices differ from the majority length ({majority_beats:g} beats)"
                    loc = locations[outlier_indices[0]]
                    location_str = f"p{loc['page_id']}, s{loc['staff_number']} (and others)"

            mismatches.append({
                "measure": measure_num,
                "comment": comment,
                "location": location_str
            })

    return total_measures, consistent_measures, mismatches



class FileSavedPopup(QDialog):
    """A beautiful, non-intrusive popup to reassure the user their file is safe."""
    def __init__(self, file_name, project_path, parent=None):
        """Constructs a frameless, modal dialog displaying the exported file's name and absolute path."""
        super().__init__(parent)
        # Make the window frameless and transparent to allow rounded corners
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True) 
        self.setFixedSize(550, 360) # Increased height to allow path wrapping

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- The White Container Box ---
        bg_frame = QFrame()
        bg_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 16px;
                border: 2px solid #026BBC;
            }
        """)
        bg_layout = QVBoxLayout(bg_frame)
        bg_layout.setContentsMargins(30, 30, 30, 20)

        # 1. File Name Header
        title = QLabel(file_name)
        title.setStyleSheet("color: #026BBC; font-size: 26px; font-weight: bold; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 2. Saved Path Text
        # Insert zero-width spaces so Qt can cleanly word-wrap long paths without breaking words awkwardly
        breakable_path = str(project_path).replace("\\", "\\\u200B").replace("/", "/\u200B")
        path_text = QLabel(f"was automatically saved to project directory:\n{breakable_path}")
        path_text.setStyleSheet("color: #026BBC; font-size: 16px; font-weight: bold; border: none;")
        path_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        path_text.setWordWrap(True)

        # 3. Instruction Text
        instruction = QLabel("To save a copy to a custom path, press \"Export copy\" in the\ntop right corner.")
        instruction.setStyleSheet("color: #026BBC; font-size: 16px; border: none; margin-top: 20px;")
        instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 4. The Close Button (With inner layout for the SVG Cross)
        self.close_btn = QPushButton()
        self.close_btn.setFixedHeight(50)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #026BBC; border-radius: 12px; border: none;
            }
            QPushButton:hover { background-color: #005BB5; }
        """)
        self.close_btn.clicked.connect(self.accept)

        # Put layout inside button to hold icon and text
        btn_layout = QHBoxLayout(self.close_btn)
        btn_layout.setContentsMargins(7, 0, 0, 0)
        btn_layout.setSpacing(0)

        icon_widget = QSvgWidget("icons/Cross_white.svg") # Make sure you have a white X icon!
        icon_widget.setFixedSize(45, 45)
        icon_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        icon_widget.setStyleSheet("background: transparent; border: none;")

        btn_text = QLabel("Close")
        btn_text.setStyleSheet("color: white; font-size: 20px; font-weight: bold; background: transparent; border: none;")
        btn_text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_layout.addWidget(icon_widget)
        btn_layout.addWidget(btn_text, 1) # '1' stretches the text to center it perfectly
        btn_layout.addSpacing(50) # Balances the left margin so text stays dead center

        # Assemble the UI
        bg_layout.addWidget(title)
        bg_layout.addSpacing(10)
        bg_layout.addWidget(path_text)
        bg_layout.addStretch()
        bg_layout.addWidget(instruction)
        bg_layout.addSpacing(15)
        bg_layout.addWidget(self.close_btn)

        layout.addWidget(bg_frame)


class SvgTextHoverButton(QPushButton):
    """A custom button that swaps an SVG and changes text color on hover."""
    def __init__(self, text, normal_svg_path, hover_svg_path, icon_size=24, width=150):
        """Initializes the button with a fixed size, an SVG icon, and text layout."""
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


class MismatchRowWidget(QWidget):
    """The custom row for the list of inconsistent measures."""
    def __init__(self, measure_num, comment, location):
        """Builds a UI row displaying the measure number, the error description, and the physical page/staff location."""
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        
        self.box = QFrame()
        self.box.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 2px solid #026BBC; 
                border-radius: 12px;
            }
        """)
        box_layout = QHBoxLayout(self.box)
        box_layout.setContentsMargins(20, 10, 20, 10)
        
        # Measure Number
        measure_label = QLabel(f"Measure {measure_num}:")
        measure_label.setStyleSheet("color: #026BBC; font-size: 20px; font-weight: bold; border: none;")
        
        # The specific error comment
        comment_label = QLabel(comment)
        comment_label.setStyleSheet("color: #262626; font-size: 18px; border: none;")
        comment_label.setWordWrap(True)
        
        # Location Coordinates (Page, Staff)
        loc_label = QLabel(location)
        loc_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        loc_label.setStyleSheet("color: #026BBC; font-size: 18px; border: none;")
        
        box_layout.addWidget(measure_label)
        box_layout.addSpacing(15)
        box_layout.addWidget(comment_label, 1)
        #box_layout.addStretch() 
        box_layout.addWidget(loc_label)
        
        layout.addWidget(self.box)



class ValidationResultsScreen(QWidget):
    exit_requested = pyqtSignal()
    export_requested = pyqtSignal()

    def __init__(self):
        """Constructs the Validation Results screen, including the header, summary statistics, and the scrollable mismatch list."""
        super().__init__()
        self.setStyleSheet("background-color: #FAFAFA;")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 1. Header Bar ---
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet("background-color: #026BBC;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        # Left: Exit Button
        self.exit_btn = SvgTextHoverButton("Exit to menu", "icons/Back.svg", "icons/Back_gray.svg", icon_size=24, width=170)
        self.exit_btn.clicked.connect(self.exit_requested.emit)

        # Center: Title
        title_label = QLabel("Transcription finished")
        title_label.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Right: Export Button
        self.export_btn = SvgTextHoverButton("Export copy", "icons/Save.svg", "icons/Save_gray.svg", icon_size=24, width=150)
        self.export_btn.clicked.connect(self.export_requested.emit)

        # --- CENTERING ---
        # 1. Create a 200px invisible box for the left button
        left_container = QWidget()
        left_container.setFixedWidth(200)
        left_layout = QHBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.exit_btn, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # 2. Create a 200px invisible box for the right button
        right_container = QWidget()
        right_container.setFixedWidth(200)
        right_layout = QHBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.export_btn, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # 3. Add them to the header. Because the left and right boxes are mathematically identical,
        # the title is forced into the absolute dead-center of the screen!
        header_layout.addWidget(left_container)
        header_layout.addWidget(title_label, 1, Qt.AlignmentFlag.AlignCenter) 
        header_layout.addWidget(right_container)
        
        main_layout.addWidget(header)

        # --- 2. Content Area ---
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(150, 30, 150, 40)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Summary Statistic
        self.summary_label = QLabel("Synchronized measures: --/-- (--%)")
        self.summary_label.setStyleSheet("color: #026BBC; font-size: 18px; font-weight: bold;")
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.summary_label)
        content_layout.addSpacing(20)

        # Subtitle
        mismatches_title = QLabel("Duration mismatches:")
        mismatches_title.setStyleSheet("color: #333333; font-size: 26px; font-weight: bold;")
        mismatches_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(mismatches_title)
        content_layout.addSpacing(15)

        # --- The Scrollable List ---
        self.mismatch_list = QListWidget()
        self.mismatch_list.setFixedWidth(750)
        self.mismatch_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Transparent background and styled scrollbar
        self.mismatch_list.setStyleSheet("""
            QListWidget {
                border: none; 
                background: transparent; 
                outline: none; 
            }
            QListWidget:focus { 
                outline: none; 
                border: none; 
            }
            QListWidget::item { 
                background: transparent; 
                border: none; 
                outline: none; 
            }
            QListWidget::item:selected { 
                background: transparent; 
            }
            
            QScrollBar:vertical {
                border: none; 
                background: transparent; 
                width: 8px; 
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #CCCCCC; 
                min-height: 30px; 
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover { 
                background: #AAAAAA; 
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { 
                height: 0px; 
                background: none; 
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { 
                background: transparent; 
            } 
        """)
        
        content_layout.addWidget(self.mismatch_list, 1, Qt.AlignmentFlag.AlignHCenter)
        main_layout.addWidget(content_widget, 1)

    def load_validation_data(self, total_measures, consistent_measures, mismatches):
        """
        Updates the summary labels and populates the scrollable list with mismatch rows.
        
        Populates the screen with data.
        mismatches should be a list of dicts: 
        [{"measure": 1, "comment": "<comment>", "location": "pX, sY"}, ...]
        """
        # Update summary math
        if total_measures > 0:
            percentage = (consistent_measures / total_measures) * 100
        else:
            percentage = 0.0
            
        summary_text = f"Synchronized measures: {consistent_measures}/{total_measures} ({percentage:.1f}%)"
        self.summary_label.setText(summary_text)

        # Populate the list
        self.mismatch_list.clear()
        for item_data in mismatches:
            row_widget = MismatchRowWidget(
                measure_num=item_data["measure"],
                comment=item_data["comment"],
                location=item_data["location"]
            )
            
            # Setup the container item
            list_item = QListWidgetItem(self.mismatch_list)
            
            # Dynamically calculate list item height based on wrapped comment length (approx 55 chars per line)
            chars = len(item_data["comment"])
            lines = max(1, chars // 55 + (1 if chars % 55 > 0 else 0))
            row_height = 50 + (lines * 24) 
            list_item.setSizeHint(QSize(700, row_height)) 
            
            self.mismatch_list.addItem(list_item)
            self.mismatch_list.setItemWidget(list_item, row_widget)

    def load_project_results(self, project_name, show_popup=True):
        """Reads the validation JSON from disk, parses it, and optionally shows the success popup if MusicXML exists."""
        base_dir = Path("Projects") / project_name
        val_path = base_dir / f"{project_name}_validation.json"
        xml_path = base_dir / f"{project_name}.musicxml"

        if val_path.exists():
            with open(val_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            tot, cons, mismatches = parse_validation_results(data)
            self.load_validation_data(tot, cons, mismatches)
        else:
            self.load_validation_data(0, 0, [])

        if show_popup and xml_path.exists():
            popup = FileSavedPopup(file_name=xml_path.name, project_path=str(base_dir.absolute()), parent=self)
            popup.exec()


# --- For standalone testing ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ValidationResultsScreen()
    window.resize(1280, 720)
    
    # Generate some dummy data to test the visuals
    dummy_mismatches = [
        {"measure": 1, "comment": "Voice 1 (4/4) differs from Voice 2 (3/4); Voice 1 (4/4) differs from Voice 2 (3/4)", "location": "p1, s1"},
        {"measure": 2, "comment": "Missing beat in Bass voice", "location": "p1, s2"},
        {"measure": 5, "comment": "Extra quarter note detected", "location": "p2, s1"},
        {"measure": 9, "comment": "Soprano length mismatch", "location": "p3, s4"},
        {"measure": 12, "comment": "Voice 3 (2/4) differs from Voice 1 (4/4)", "location": "p4, s2"},
    ]
    
    # Load the data into the UI
    window.load_validation_data(total_measures=142, consistent_measures=137, mismatches=dummy_mismatches)
    
    # 1. SHOW THE MAIN WINDOW FIRST
    window.show()
    
    # 2. TRIGGER THE POPUP OVER THE MAIN WINDOW
    # We pass 'window' as the parent so it centers perfectly over the main screen!
    popup = FileSavedPopup(
        file_name="Beethoven_Opus_18.musicxml", 
        project_path="C:/Users/Music/nanoScore/Projects/Beethoven_Opus_18", 
        parent=window
    )
    popup.exec() # .exec() pauses the code here until the user clicks "Close"
    
    sys.exit(app.exec())