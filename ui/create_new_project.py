import sys
import os
import re
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                             QListWidget, QListWidgetItem, QAbstractItemView, 
                             QFileDialog, QFrame, QGridLayout)
from PyQt6.QtCore import Qt, pyqtSignal, QSize

class DynamicListWidget(QListWidget):
    """A custom list widget that tells the window exactly how much space it needs."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.needed_height = 90 
        
    def sizeHint(self):
        return QSize(700, self.needed_height)

class VoiceRowWidget(QWidget):
    delete_requested = pyqtSignal(QWidget)
    error_state_changed = pyqtSignal()

    def __init__(self, number):
        super().__init__()
        self.file_path = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8) 
        
        self.box = QFrame()
        self.box.setStyleSheet(
            """
            QFrame {
                background-color: white;
                border: 2px solid #333333;
                border-radius: 12px;
            }
        """)
        # --- GRID LAYOUT ---
        box_layout = QGridLayout(self.box)
        box_layout.setContentsMargins(15, 10, 15, 10)
        box_layout.setHorizontalSpacing(10)
        box_layout.setVerticalSpacing(2) # Tight space between input and error

        self.num_label = QLabel(f"Voice {number}:")
        self.num_label.setStyleSheet("""
            QLabel {
                color: #333333; 
                border: none; 
                font-size: 18px; 
                font-weight: bold; 
                background: transparent;
            }
        """)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Write voice name...")
        self.name_input.setStyleSheet("""
            QLineEdit {
                color: #026BBC; 
                font-weight: bold; 
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                background: #FAFAFA;
                font-size: 16px;
                padding: 4px 8px;
            }
            QLineEdit:focus {
                border: 1px solid #026BBC;
                background: white;
            }
        """)
        
        self.name_error = QLabel("")
        self.name_error.setStyleSheet("color: #D32F2F; font-size: 13px; font-weight: bold; border: none;")
        self.name_error.setVisible(False)

        self.file_btn = QPushButton("upload PDF file")
        self.file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.file_btn.setFixedWidth(180) 
        self.file_btn.setStyleSheet(
            """
            QPushButton {
                border: 1px solid #CCCCCC; 
                border-radius: 6px;
                background: #F0F0F0; 
                padding: 5px 10px;
                font-size: 16px; 
                color: #555555;
            }
            QPushButton:hover { 
                background: #E0E0E0; 
            }
        """)
        self.file_btn.clicked.connect(self.upload_file)

        self.delete_btn = QPushButton("✕")
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                border: none; 
                background: transparent;
                font-size: 22px; 
                color: #777777; 
                padding-bottom: 4px;
            }
            QPushButton:hover { 
                color: red; 
            }
        """)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self))

        # --- ASSEMBLE THE GRID ---
        # Row 0: All main elements (Locked to vertically center with each other)
        box_layout.addWidget(self.num_label, 0, 0, alignment=Qt.AlignmentFlag.AlignVCenter)
        box_layout.addWidget(self.name_input, 0, 1, alignment=Qt.AlignmentFlag.AlignVCenter)
        box_layout.addWidget(self.file_btn, 0, 2, alignment=Qt.AlignmentFlag.AlignVCenter)
        box_layout.addWidget(self.delete_btn, 0, 3, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Row 1: The error message (Placed exactly under the input field in Column 1)
        box_layout.addWidget(self.name_error, 1, 1, alignment=Qt.AlignmentFlag.AlignTop)

        # Tell Column 1 (the input field) to stretch and fill extra space
        box_layout.setColumnStretch(1, 1)

        layout.addWidget(self.box)

    def upload_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if file_name:
            self.file_path = file_name 
            short_name = os.path.basename(file_name)
            
            font_metrics = self.file_btn.fontMetrics()
            elided_name = font_metrics.elidedText(short_name, Qt.TextElideMode.ElideRight, 160)
            
            self.file_btn.setText(elided_name)
            self.file_btn.setToolTip(short_name) 
            self.file_btn.setStyleSheet(self.file_btn.styleSheet() + """
                QPushButton { 
                    color: #333333; 
                }
            """)

    def show_error(self, message):
        self.name_input.setStyleSheet("""
            QLineEdit {
                color: #D32F2F; 
                font-weight: bold; 
                border: 2px solid #D32F2F;
                border-radius: 6px;
                background: #FFEBEE;
                font-size: 16px;
                padding: 4px 8px;
            }
            QLineEdit:focus {
                border: 2px solid #D32F2F;
                background: white;
            }
        """)
        self.name_error.setText(message)
        if not self.name_error.isVisible():
            self.name_error.setVisible(True)
            self.error_state_changed.emit()

    def clear_error(self):
        self.name_input.setStyleSheet("""
            QLineEdit {
                color: #026BBC; 
                font-weight: bold; 
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                background: #FAFAFA;
                font-size: 16px;
                padding: 4px 8px;
            }
            QLineEdit:focus {
                border: 1px solid #026BBC;
                background: white;
            }
        """)
        if self.name_error.isVisible():
            self.name_error.setVisible(False)
            self.error_state_changed.emit()

    def set_number(self, num):
        self.num_label.setText(f"Voice {num}:")


class CreateProjectScreen(QWidget):
    # This signal tells the Master Window to go back
    go_back_requested = pyqtSignal()
    start_transcription_requested = pyqtSignal(str, list)

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #FAFAFA;")

        # Apply layout directly to self
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 1. Header Bar ---
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet("background-color: #026BBC;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        back_btn = QPushButton("< Go back")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet("""
            QPushButton { 
                color: white; 
                font-size: 20px; 
                font-weight: bold; 
                border: none; 
                background: transparent; 
                padding-bottom: 2px; 
            } 
            QPushButton:hover { 
                color: #CCCCCC; 
            }
        """)

        back_btn.clicked.connect(self.go_back_requested.emit)

        title_label = QLabel("Create new project")
        title_label.setStyleSheet("""
            QLabel {
                color: white; 
                font-size: 32px; 
                font-weight: bold;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        right_spacer = QLabel()
        right_spacer.setFixedWidth(back_btn.sizeHint().width())

        header_layout.addWidget(back_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(title_label, 1, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(right_spacer, 0, Qt.AlignmentFlag.AlignVCenter)
        main_layout.addWidget(header)

        # --- 2. Content Area ---
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(150, 15, 150, 40) 
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        content_layout.addSpacing(10)

        # --- Project Name Section ---
        project_name_container = QWidget()
        project_name_container.setFixedWidth(700) # Locks the total width to 700px
        
        pn_layout = QHBoxLayout(project_name_container)
        pn_layout.setContentsMargins(0, 0, 0, 0)
        pn_layout.setSpacing(15) # Space between the label and the input box
        
        project_name_lbl = QLabel("Project name:")
        project_name_lbl.setStyleSheet("""
            QLabel {
                font-size: 22px; 
                font-weight: bold; 
                color: #333333;
                padding-top: 4px;
            }
        """)
        
        # Saved as self so you can easily extract the text later for saving!
        self.project_name_input = QLineEdit()
        self.project_name_input.setPlaceholderText("Write project name...")
        self.project_name_input.setFixedHeight(38) # Matches the visual height of your voice inputs
        self.project_name_input.setStyleSheet(
            """
            QLineEdit {
                color: #026BBC; 
                font-weight: bold; 
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                background: #FAFAFA;
                font-size: 16px;
                padding: 4px 10px;
            }
            QLineEdit:focus {
                border: 2px solid #026BBC;
                background: white;
            }
        """)
        
        pn_layout.addWidget(project_name_lbl, alignment=Qt.AlignmentFlag.AlignTop)
        
        # Wrap the input and a hidden error label in a vertical layout
        input_vbox = QVBoxLayout()
        input_vbox.setContentsMargins(0, 0, 0, 0)
        input_vbox.setSpacing(4)
        input_vbox.addWidget(self.project_name_input)
        
        self.project_name_error = QLabel("")
        self.project_name_error.setStyleSheet("color: #D32F2F; font-size: 13px; font-weight: bold;")
        self.project_name_error.setVisible(False)
        input_vbox.addWidget(self.project_name_error)

        pn_layout.addLayout(input_vbox, 1) # '1' forces the layout to stretch and fill the remaining 700px
        
        content_layout.addWidget(project_name_container, alignment=Qt.AlignmentFlag.AlignHCenter)
        content_layout.addSpacing(10) # Gap between the project name and the "Add voices" section

        # --- Add Voices ---
        add_voices_lbl = QLabel("Add voices:")
        add_voices_lbl.setStyleSheet("""
            QLabel {
                font-size: 22px; 
                font-weight: bold; 
                color: #333333;
            }
        """)
        add_voices_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(add_voices_lbl)
        content_layout.addSpacing(10)

        # --- The Dynamic List ---
        self.voice_list = DynamicListWidget()
        self.voice_list.setFixedWidth(700) 
        self.voice_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.voice_list.setStyleSheet("""
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
        
        self.voice_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.voice_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.voice_list.setDropIndicatorShown(True) 
        self.voice_list.model().rowsMoved.connect(self.update_voice_numbers)
        
        content_layout.addWidget(self.voice_list, 0, Qt.AlignmentFlag.AlignHCenter)

        self.add_voice_btn = QPushButton("+ Add voice")
        self.add_voice_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_voice_btn.setStyleSheet(
            """
            QPushButton { 
                color: #026BBC; 
                font-size: 20px; 
                border: none; 
                background: transparent; 
            } 
            QPushButton:hover { 
                color: #005BB5; 
                text-decoration: underline; 
            }
            QPushButton:disabled {
                color: #A0A0A0; /* The inactive grey color */
            }
        """)
        self.add_voice_btn.clicked.connect(self.add_voice_row)
        content_layout.addWidget(self.add_voice_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        content_layout.addStretch(1) 
        content_layout.addSpacing(10)

        # --- Bottom Buttons ---
        auto_btn = QPushButton("Start automatic transcription")
        # FIX: Lock to exactly 700px wide
        auto_btn.setFixedSize(700, 60)
        auto_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        auto_btn.setStyleSheet("""
            QPushButton { 
                background-color: #026BBC; 
                color: white; 
                font-size: 24px; 
                font-weight: bold; 
                border-radius: 12px; 
                padding-bottom: 4px; 
            } 
            QPushButton:hover { 
                background-color: #005BB5; 
            }
        """)
        auto_btn.clicked.connect(self.start_automatic_transcription)

        semi_btn = QPushButton("Start semiautomatic transcription")
        semi_btn.setFixedSize(700, 40)
        semi_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        semi_btn.setStyleSheet("""
            QPushButton { 
                background-color: white; 
                color: #026BBC; 
                font-size: 18px; 
                font-weight: bold; 
                border-radius: 12px; 
                border: 2px solid #026BBC; 
                padding-bottom: 2px; 
            } 
            QPushButton:hover { 
                background-color: #E6F0FA; 
            }
        """)

        content_layout.addWidget(auto_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        content_layout.addSpacing(10)
        content_layout.addWidget(semi_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(content_widget, 1)

        self.add_voice_row()

    def add_voice_row(self):
        # Prevent adding more than 20
        if self.voice_list.count() >= 20:
            return

        current_count = self.voice_list.count()
        row_widget = VoiceRowWidget(current_count + 1)
        row_widget.delete_requested.connect(self.remove_voice_row)

        row_widget.error_state_changed.connect(self.adjust_list_height)

        item = QListWidgetItem(self.voice_list)
        item.setSizeHint(QSize(100, 70)) 
        
        self.voice_list.addItem(item)
        self.voice_list.setItemWidget(item, row_widget)
        self.adjust_list_height()

        # Disable the button and turn it grey if we hit the limit
        if self.voice_list.count() >= 20:
            self.add_voice_btn.setEnabled(False)

    def remove_voice_row(self, widget):
        for i in range(self.voice_list.count()):
            item = self.voice_list.item(i)
            if self.voice_list.itemWidget(item) == widget:
                self.voice_list.takeItem(i)
                break
        self.update_voice_numbers()
        self.adjust_list_height()

        # Show the button again if we dropped below 20
        if self.voice_list.count() < 20:
            self.add_voice_btn.setEnabled(True)
            #self.add_voice_btn.setVisible(True)

    def update_voice_numbers(self):
        for i in range(self.voice_list.count()):
            item = self.voice_list.item(i)
            widget = self.voice_list.itemWidget(item)
            if widget:
                widget.set_number(i + 1)

    def adjust_list_height(self):
        """Calculates exact list height row-by-row based on if errors are visible."""
        total_needed_height = 0
        
        for i in range(self.voice_list.count()):
            item = self.voice_list.item(i)
            widget = self.voice_list.itemWidget(item)
            if widget:
                # If error is showing, this row needs 90px. If not, it needs 70px.
                row_height = 90 if widget.name_error.isVisible() else 70
                
                # Dynamically resize the specific list item
                item.setSizeHint(QSize(100, row_height))
                total_needed_height += row_height
        
        self.voice_list.needed_height = total_needed_height
        self.voice_list.updateGeometry() 
        
        self.voice_list.setMaximumHeight(total_needed_height)
        self.voice_list.setMinimumHeight(min(total_needed_height, 70 * 2)) 
        
    def start_automatic_transcription(self):
        project_name = self.project_name_input.text().strip()
        project_name = project_name.rstrip(' .')
        
        # Clear all previous voice errors
        for i in range(self.voice_list.count()):
            item = self.voice_list.item(i)
            widget = self.voice_list.itemWidget(item)
            if widget:
                widget.clear_error()

        # Reset UI to normal before checking for errors
        self.project_name_input.setStyleSheet(
            """
            QLineEdit {
                color: #026BBC; 
                font-weight: bold; 
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                background: #FAFAFA;
                font-size: 16px;
                padding: 4px 10px;
            }
            QLineEdit:focus {
                border: 1px solid #026BBC;
                background: white;
            }
        """)
        self.project_name_error.setVisible(False)

        reserved_names = {"CON", "PRN", "AUX", "NUL", 
                          "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
                          "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
        invalid_chars = r'[<>:"/\\|?*]'

        # Validate user input
        if project_name:
            # 1. Check for Windows reserved names
            if project_name.upper() in reserved_names:
                self.show_project_name_error("Project name cannot be a system reserved name.")
                return

            # 2. Check for forbidden file system characters
            if re.search(invalid_chars, project_name):
                self.show_project_name_error("Project name contains restricted symbols (< > : \" / \\ | ? *).")
                return
                
            # 3. Check if a project with this name already exists
            if (Path("Projects") / project_name).exists():
                self.show_project_name_error("A project with this name already exists. Please choose another.")
                return

        if self.voice_list.count() == 0:
            self.show_project_name_error("Please add at least one voice before starting.")
            return

        voices_data = []
        
        # Gather data from every voice row in the list
        for i in range(self.voice_list.count()):
            item = self.voice_list.item(i)
            widget = self.voice_list.itemWidget(item)
            if widget:
                v_name = widget.name_input.text().strip()
                v_name = v_name.rstrip(' .')

                # Validate voice name if user provided one
                if v_name:
                    if v_name.upper() in reserved_names:
                        widget.show_error("Voice name cannot be a system reserved name.")
                        return
                    if re.search(invalid_chars, v_name):
                        widget.show_error("Voice name contains restricted symbols (< > : \" / \\ | ? *).")
                        return

                if not widget.file_path:
                    widget.show_error("Please upload a PDF file for this voice.")
                    return

                voices_data.append({
                    "name": v_name if v_name else f"Voice_{i+1:02d}", # Fallback to default name if empty
                    "pdf_path": widget.file_path
                })
                
        self.start_transcription_requested.emit(project_name, voices_data)

    def show_project_name_error(self, message):
        # Change input styling to a red alert state
        self.project_name_input.setStyleSheet("""
            QLineEdit {
                color: #D32F2F; 
                font-weight: bold; 
                border: 2px solid #D32F2F;
                border-radius: 6px;
                background: #FFEBEE;
                font-size: 16px;
                padding: 4px 10px;
            }
            QLineEdit:focus {
                border: 2px solid #D32F2F;
                background: white;
            }
        """)
        self.project_name_error.setText(message)
        self.project_name_error.setVisible(True)

"""
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CreateProjectWindow()
    window.show()
    sys.exit(app.exec())
"""