import sys
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFrame, QListWidget, QListWidgetItem, 
                             QDialog, QAbstractItemView)
from PyQt6.QtCore import QThread, Qt, pyqtSignal, QSize, QTimer, QRectF
from PyQt6.QtGui import QPixmap
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QPainter

from engines.pipeline import TranscriptionPipeline



# --- BRAND NEW CUSTOM POPUP ---
class CancelDialog(QDialog):
    """A beautifully styled, custom popup mimicking the AboutDialog."""
    def __init__(self, parent=None):
        super().__init__(parent)
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
        title = QLabel("Cancel Transcription")
        title.setStyleSheet("color: #D32F2F; font-size: 26px; font-weight: bold; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        desc = QLabel("Are you sure you want to cancel?\nAll progress of current step will be lost.")
        desc.setStyleSheet("color: #333333; font-size: 16px; border: none; margin-top: 10px;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Buttons Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)

        cancel_btn = QPushButton("Yes, Cancel")
        cancel_btn.setFixedSize(140, 40)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: white; color: #D32F2F; font-weight: bold; 
                border-radius: 8px; font-size: 16px; border: 2px solid #D32F2F;
            }
            QPushButton:hover { background-color: #FFF0F2; }
        """)
        # accept() means the user clicked YES to canceling
        cancel_btn.clicked.connect(self.accept) 

        continue_btn = QPushButton("No, Continue")
        continue_btn.setFixedSize(140, 40)
        continue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        continue_btn.setStyleSheet("""
            QPushButton {
                background-color: #026BBC; color: white; font-weight: bold; border-radius: 8px; font-size: 16px;
            }
            QPushButton:hover { background-color: #005BB5; }
        """)
        # reject() means the user wants to close the popup and keep transcribing
        continue_btn.clicked.connect(self.reject) 

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(continue_btn)
        btn_layout.addStretch()

        bg_layout.addWidget(title)
        bg_layout.addWidget(desc)
        bg_layout.addStretch()
        bg_layout.addLayout(btn_layout)

        layout.addWidget(bg_frame)



class AnimatedSvgWidget(QWidget):
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.renderer = QSvgRenderer(file_path)
        
        # --- THE TRANSPARENCY FIX ---
        # Explicitly strip all background colors and borders from this widget
        self.setStyleSheet("background: transparent; border: none;")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) 
        
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate_icon)
        self._is_rotating = False

    def load(self, file_path):
        """Loads a new SVG file into the renderer."""
        self.renderer.load(file_path)
        self.update()

    def start_rotation(self):
        """Starts spinning at 60 FPS (16ms) for buttery smooth animation."""
        if not self._is_rotating:
            self.timer.start(16) 
            self._is_rotating = True

    def stop_rotation(self):
        """Stops spinning and resets the angle perfectly to top-dead-center."""
        self.timer.stop()
        self.angle = 0
        self._is_rotating = False
        self.update()

    def rotate_icon(self):
        """Advances the angle by a smaller amount (3 degrees) for smoother visuals."""
        self.angle = (self.angle + 3) % 360
        self.update() # Triggers a repaint

    def paintEvent(self, event):
        """This mathematically draws the SVG, applying rotation if active."""
        painter = QPainter(self)
        
        # High-Quality Anti-Aliasing ensures the edges don't look jagged while spinning
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        if self._is_rotating:
            # Move the painter to the center, rotate it, and move it back
            painter.translate(self.width() / 2, self.height() / 2)
            painter.rotate(self.angle)
            painter.translate(-self.width() / 2, -self.height() / 2)

        # Draw the SVG sharply using the current painter rotation
        self.renderer.render(painter, QRectF(self.rect()))



class DynamicListWidget(QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.needed_height = 90 
        
    def sizeHint(self):
        return QSize(500, self.needed_height)



class VoiceProgressRowWidget(QWidget):
    def __init__(self, voice_num, voice_name, total_pages):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        
        self.box = QFrame()
        self.box.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 2px solid #026BBC; 
                border-radius: 8px;
            }
        """)
        box_layout = QHBoxLayout(self.box)
        box_layout.setContentsMargins(15, 8, 15, 8)
        
        # --- THE FIX IS HERE ---
        # Create the SVG Widget and load the file directly! No scaling needed.
        self.icon_label = AnimatedSvgWidget("icons/Hourglass.svg")
        self.icon_label.setFixedSize(30, 30)
        
        if voice_num == -1:
            self.name_label = QLabel(voice_name)
        else:
            self.name_label = QLabel(f"Voice {voice_num}: {voice_name}")
        self.name_label.setStyleSheet("color: #026BBC; font-size: 16px; font-weight: bold; border: none;")
        
        self.progress_label = QLabel(f"0/{total_pages}" if total_pages else "")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.progress_label.setStyleSheet("color: #026BBC; font-size: 16px; font-weight: bold; border: none;")
        self.progress_label.setVisible(bool(total_pages))
        
        box_layout.addWidget(self.icon_label)
        box_layout.addWidget(self.name_label)
        box_layout.addStretch() 
        box_layout.addWidget(self.progress_label)
        
        layout.addWidget(self.box, 1)

    def set_status(self, status, current_page=None, total_pages=None):
        if current_page is not None and total_pages is not None:
            self.progress_label.setText(f"{current_page}/{total_pages}")
            self.progress_label.setVisible(True)

        if status == "waiting":
            self.icon_label.load("icons/Hourglass.svg")
            self.icon_label.stop_rotation() # Ensure it stops spinning
            self.name_label.setStyleSheet("color: #026BBC; font-size: 16px; font-weight: bold; border: none;")
            self.progress_label.setStyleSheet("color: #026BBC; font-size: 16px; font-weight: bold; border: none;")
            self.box.setStyleSheet("QFrame { background-color: white; border: 2px solid #026BBC; border-radius: 8px; }")
            
        elif status == "processing":
            self.icon_label.load("icons/Loader.svg")
            self.icon_label.start_rotation() # Spinning
            self.name_label.setStyleSheet("color: #026BBC; font-size: 16px; font-weight: bold; border: none;")
            self.progress_label.setStyleSheet("color: #026BBC; font-size: 16px; font-weight: bold; border: none;")
            self.box.setStyleSheet("QFrame { background-color: white; border: 2px solid #026BBC; border-radius: 8px; }")
            
        elif status == "done":
            self.icon_label.load("icons/Check.svg")
            self.icon_label.stop_rotation() # Ensure it stops spinning
            self.name_label.setStyleSheet("color: #026BBC; font-size: 16px; font-weight: bold; border: none;")
            self.progress_label.setStyleSheet("color: #026BBC; font-size: 16px; font-weight: bold; border: none;")
            self.box.setStyleSheet("QFrame { background-color: white; border: 2px solid #026BBC; border-radius: 8px; }")
            
        elif status == "error":
            self.icon_label.load("icons/Alert triangle.svg")
            self.icon_label.stop_rotation() # Ensure it stops spinning
            self.name_label.setStyleSheet("color: #D32F2F; font-size: 16px; font-weight: bold; border: none;")
            self.progress_label.setStyleSheet("color: #D32F2F; font-size: 16px; font-weight: bold; border: none;") 
            self.box.setStyleSheet("QFrame { background-color: #FFF0F2; border: 2px solid #D32F2F; border-radius: 8px; }")



class TranscriptionProgressScreen(QWidget):
    cancel_transcription_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #FAFAFA;")
        self.worker = None
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 1. Header Bar ---
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet("background-color: #026BBC;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        self.cancel_btn = QPushButton("✕ Cancel")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet("""
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
        self.cancel_btn.clicked.connect(self.attempt_cancel)

        title_label = QLabel("Transcription is in process...")
        title_label.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        right_spacer = QLabel()
        right_spacer.setFixedWidth(self.cancel_btn.sizeHint().width())

        header_layout.addWidget(self.cancel_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(title_label, 1, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(right_spacer, 0, Qt.AlignmentFlag.AlignVCenter)
        main_layout.addWidget(header)

        # --- 2. Content Area ---
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(150, 20, 150, 40) 
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # --- Step Indicator Visual ---
        self.steps_container = QWidget()
        steps_layout = QHBoxLayout(self.steps_container)
        steps_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        steps_layout.setSpacing(0) 
        
        self.step_labels = []
        self.step_lines = []
        
        for i in range(1, 5):
            step_lbl = QLabel()
            step_lbl.setFixedSize(80, 80)
            step_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.step_labels.append(step_lbl)
            steps_layout.addWidget(step_lbl)
            
            if i < 4:
                line = QFrame()
                # ADJUST LINE WIDTH AND THICKNESS HERE: (width, height)
                line.setFixedSize(60, 1) 
                self.step_lines.append(line)
                steps_layout.addWidget(line)
                
        content_layout.addWidget(self.steps_container)
        content_layout.addSpacing(10) 

        # Current Phase Title
        self.phase_title = QLabel()
        self.phase_title.setStyleSheet("font-size: 26px; font-weight: bold; color: #026BBC;")
        self.phase_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.phase_title)
        content_layout.addSpacing(20) 

        # --- The Dynamic Voice List ---
        self.voice_list = DynamicListWidget()
        self.voice_list.setFixedWidth(500) 
        self.voice_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # ADDED padding-right: 12px; to prevent scrollbar overlap
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
        
        content_layout.addWidget(self.voice_list, 0, Qt.AlignmentFlag.AlignHCenter)
        content_layout.addStretch(1) 
        main_layout.addWidget(content_widget, 1)
        self.set_current_step(2)

    def start_transcription(self, project_name, voices_data):
        self.populate_voices(voices_data)
        
        self.worker = TranscriptionWorker(project_name, voices_data)
        self.worker.step_changed.connect(self.on_step_changed)
        self.worker.voice_progress.connect(self.on_voice_progress)
        self.worker.general_progress.connect(self.on_general_progress)
        self.worker.finished_success.connect(self.on_finished)
        self.worker.start()

    def on_voice_progress(self, voice_idx, status, current, total):
        if voice_idx < self.voice_list.count():
            item = self.voice_list.item(voice_idx)
            self.voice_list.itemWidget(item).set_status(status, current_page=current, total_pages=total)
            
    def on_general_progress(self, text, status, current, total):
        if self.voice_list.count() > 0:
            item = self.voice_list.item(0)
            self.voice_list.itemWidget(item).set_status(status, current_page=current, total_pages=total)

    def set_current_step(self, step_number):
        titles = {
            1: "Staves detection",
            2: "Symbols detection",
            3: "Symbols position classification",
            4: "Score reconstruction"
        }
        self.phase_title.setText(titles.get(step_number, ""))

        done_style = "background-color: #026BBC; color: white; font-weight: bold; font-size: 40px; border-radius: 40px;"
        active_style = "background-color: white; color: #026BBC; border: 3px solid #026BBC; font-weight: bold; font-size: 20px; border-radius: 40px;"
        future_style = "background-color: white; color: #777777; border: 1px solid #777777; font-weight: normal; font-size: 18px; border-radius: 40px;"
        
        for i, lbl in enumerate(self.step_labels):
            idx = i + 1
            if idx < step_number:
                lbl.setStyleSheet(done_style)
                lbl.setText("✓")
            elif idx == step_number:
                lbl.setStyleSheet(active_style)
                lbl.setText(f"Step {idx}")
            else:
                lbl.setStyleSheet(future_style)
                lbl.setText(f"Step {idx}")

        for i, line in enumerate(self.step_lines):
            idx = i + 1
            if idx < step_number:
                # Blue lines get 3px thickness
                line.setFixedSize(60, 3) 
                line.setStyleSheet("background-color: #026BBC;")
            else:
                # Gray lines get 1px thickness
                line.setFixedSize(60, 1) 
                line.setStyleSheet("background-color: #777777;")
                
        # Handle UI clearing for Step 4
        if step_number < 4:
            for i in range(self.voice_list.count()):
                item = self.voice_list.item(i)
                self.voice_list.itemWidget(item).set_status("waiting", current_page=0, total_pages="?")
        else:
            self.voice_list.clear()
            row_widget = VoiceProgressRowWidget(-1, "Processing and saving MusicXML files", "")
            item = QListWidgetItem(self.voice_list)
            item.setSizeHint(QSize(100, 60))
            self.voice_list.addItem(item)
            self.voice_list.setItemWidget(item, row_widget)
            self.voice_list.setMaximumHeight(60)
            self.voice_list.needed_height = 60

    def populate_voices(self, voice_data_list):
        self.voice_list.clear()
        total_height = 0
        
        for i, voice in enumerate(voice_data_list):
            row_widget = VoiceProgressRowWidget(i + 1, voice['name'], "?")
            
            item = QListWidgetItem(self.voice_list)
            item.setSizeHint(QSize(100, 60)) 
            
            self.voice_list.addItem(item)
            self.voice_list.setItemWidget(item, row_widget)
            total_height += 60
            
        self.voice_list.needed_height = total_height
        self.voice_list.setMaximumHeight(total_height)
        self.voice_list.setMinimumHeight(min(total_height, 60 * 6)) 

    def attempt_cancel(self):
        # Open our new beautifully styled dialog
        dialog = CancelDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if self.worker and self.worker.isRunning():
                # Brutally terminate thread (will drop progress on the current voice loop)
                self.worker.terminate()
                self.worker.wait()
            # Emits the signal if the user clicks "Yes, Cancel"
            self.cancel_transcription_requested.emit()
            
    def on_step_changed(self, step_num):
        self.set_current_step(step_num)

    def on_finished(self):
        pass

    def simulate_mock_state_for_testing(self):
        if self.voice_list.count() >= 4:
            self.voice_list.itemWidget(self.voice_list.item(0)).set_status("done", current_page=12)
            self.voice_list.itemWidget(self.voice_list.item(1)).set_status("done", current_page=12)
            self.voice_list.itemWidget(self.voice_list.item(2)).set_status("processing", current_page=4)
            self.voice_list.itemWidget(self.voice_list.item(3)).set_status("error")


class TranscriptionWorker(QThread):
    """Thread worker handling heavy YOLO models so the UI doesn't freeze."""
    step_changed = pyqtSignal(int)
    voice_progress = pyqtSignal(int, str, object, object) 
    general_progress = pyqtSignal(str, str, int, int)
    finished_success = pyqtSignal()

    def __init__(self, project_name, voices_data):
        super().__init__()
        self.project_name = project_name
        self.voices_data = voices_data

    def run(self):
        pipeline = TranscriptionPipeline()
        pipeline.run_automatic_pipeline(
            self.project_name, 
            self.voices_data,
            step_callback=self.step_changed.emit,
            voice_progress_callback=self.voice_progress.emit,
            general_progress_callback=self.general_progress.emit
        )
        self.finished_success.emit()



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TranscriptionProgressScreen()
    window.resize(1280, 720)
    
    window.show()
    sys.exit(app.exec())
