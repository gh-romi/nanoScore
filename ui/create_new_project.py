import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                             QListWidget, QListWidgetItem, QAbstractItemView, 
                             QFileDialog, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from engines.pipeline import TranscriptionPipeline

class DynamicListWidget(QListWidget):
    """A custom list widget that tells the window exactly how much space it needs."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.needed_height = 75 
        
    def sizeHint(self):
        return QSize(700, self.needed_height)

class VoiceRowWidget(QWidget):
    delete_requested = pyqtSignal(QWidget)

    def __init__(self, number):
        super().__init__()
        self.file_path = None

        layout = QHBoxLayout(self)
        # Removed the right margin so the box aligns perfectly with the buttons below
        layout.setContentsMargins(0, 0, 0, 8) 
        
        self.box = QFrame()
        self.box.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 2px solid #333333;
                border-radius: 12px;
            }
        """)
        box_layout = QHBoxLayout(self.box)
        box_layout.setContentsMargins(15, 10, 15, 10)

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

        self.file_btn = QPushButton("upload PDF file")
        self.file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.file_btn.setFixedWidth(180) 
        self.file_btn.setStyleSheet("""
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

        box_layout.addWidget(self.num_label)
        box_layout.addWidget(self.name_input, 1) 
        box_layout.addWidget(self.file_btn)
        box_layout.addWidget(self.delete_btn)

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

    def set_number(self, num):
        self.num_label.setText(f"Voice {num}:")


class CreateProjectScreen(QWidget):
    # This signal tells the Master Window to go back
    go_back_requested = pyqtSignal()

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
                border: 1px solid #026BBC;
                background: white;
            }
        """)
        
        pn_layout.addWidget(project_name_lbl)
        pn_layout.addWidget(self.project_name_input, 1) # '1' forces the input to stretch and fill the remaining 700px

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

        item = QListWidgetItem(self.voice_list)
        # Width is set to a tiny number (100). 
        # to fill the 700px list perfectly, without overflowing when the scrollbar appears.
        item.setSizeHint(QSize(100, 75)) 
        
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
        row_height = 75 
        current_count = self.voice_list.count()
        needed_height = current_count * row_height
        
        self.voice_list.needed_height = needed_height
        self.voice_list.updateGeometry() 
        
        self.voice_list.setMaximumHeight(needed_height)
        self.voice_list.setMinimumHeight(min(needed_height, row_height * 2)) 
        
    def start_automatic_transcription(self):
        project_name = self.project_name_input.text().strip()
        voices_data = []
        
        # Gather data from every voice row in the list
        for i in range(self.voice_list.count()):
            item = self.voice_list.item(i)
            widget = self.voice_list.itemWidget(item)
            if widget:
                v_name = widget.name_input.text().strip()
                voices_data.append({
                    "name": v_name if v_name else f"Voice_{i+1:02d}", # Fallback to default name if empty
                    "pdf_path": widget.file_path
                })
                
        # Instantiate our engine orchestration and execute it
        pipeline = TranscriptionPipeline()
        pipeline.run_automatic_pipeline(project_name, voices_data)


"""
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CreateProjectWindow()
    window.show()
    sys.exit(app.exec())
"""