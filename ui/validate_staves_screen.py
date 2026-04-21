import sys
import json
import copy
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFrame, QScrollArea, QSizePolicy, QDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRectF, QPointF, QEventLoop
from PyQt6.QtGui import QPainter, QFontMetrics, QColor, QFont, QPixmap, QImage, QPainterPath, QBrush, QPen, QShortcut, QKeySequence
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtCore import QThread


# --- HELPER CLASSES ---

class TopBarButton(QPushButton):
    """Custom button that supports an icon on either the left or right side."""
    def __init__(self, text, normal_svg, hover_svg, icon_size=24, icon_pos="left", width=250):
        super().__init__()
        self.normal_svg = normal_svg
        self.hover_svg = hover_svg
        self.icon_pos = icon_pos
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: transparent; border: none;")
        self.setFixedSize(width, icon_size + 16)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 2) 
        layout.setSpacing(8) 

        self.icon_widget = QSvgWidget(self.normal_svg)
        self.icon_widget.setFixedSize(icon_size, icon_size)
        self.icon_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.text_label = QLabel(text)
        self.text_label.setStyleSheet("color: white; font-size: 20px; font-weight: bold; background: transparent; border: none;")

        if self.icon_pos == "left":
            layout.addWidget(self.icon_widget)
            layout.addWidget(self.text_label)
            layout.addStretch()
        else:
            layout.addStretch()
            layout.addWidget(self.text_label)
            layout.addWidget(self.icon_widget)

    def enterEvent(self, event):
        self.icon_widget.load(self.hover_svg)
        self.text_label.setStyleSheet("color: #CCCCCC; font-size: 20px; font-weight: bold; background: transparent; border: none;")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.icon_widget.load(self.normal_svg)
        self.text_label.setStyleSheet("color: white; font-size: 20px; font-weight: bold; background: transparent; border: none;")
        super().leaveEvent(event)



class ToggleActionButton(QPushButton):
    """Custom button for Delete/Draw with a toggleable square icon state."""
    def __init__(self, text, is_selected=False, width=150):
        super().__init__()
        self.is_selected = is_selected
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(50)
        self.setMinimumWidth(width)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(13, 0, 13, 0) # Symmetric left/right margins
        self.layout.setSpacing(0)

        # The custom drawn square icon
        self.icon_widget = QWidget()
        self.icon_widget.setFixedSize(24, 24)
        self.icon_widget.paintEvent = self.paint_icon # Override paint event
        self.icon_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.text_label = QLabel(text)
        self.text_label.setStyleSheet("font-size: 20px; font-weight: bold; background: transparent; border: none;")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # Center the text internally

        self.layout.addWidget(self.icon_widget)
        self.layout.addWidget(self.text_label, 1) # '1' stretch forces text into the remaining center space
        self.layout.addSpacing(24) # Invisible spacing to perfectly balance the checkbox width

        self.update_style()

    def set_selected(self, selected):
        self.is_selected = selected
        self.update_style()

    def paint_icon(self, event):
        """Draws the empty square or the filled square depending on state."""
        painter = QPainter(self.icon_widget)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw outer rounded square
        pen = QPen(QColor("#026BBC"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(2, 2, 20, 20, 4, 4)

        # Draw inner filled square if selected
        if self.is_selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#026BBC")))
            painter.drawRoundedRect(6, 6, 12, 12, 2, 2)
            
        painter.end()

    def update_style(self):
        if self.is_selected:
            self.setStyleSheet("""
                QPushButton { background-color: white; border-radius: 12px; border: 2px solid #026BBC; }
                QPushButton:hover { background-color: #E6F0FA; }
            """)
            self.text_label.setStyleSheet("color: #026BBC; font-size: 20px; font-weight: bold; background: transparent; border: none;")
        else:
            self.setStyleSheet("""
                QPushButton { background-color: white; border-radius: 12px; border: 2px solid #026BBC; }
                QPushButton:hover { background-color: #E6F0FA; }
            """)
            self.text_label.setStyleSheet("color: #026BBC; font-size: 20px; font-weight: bold; background: transparent; border: none;")
        self.icon_widget.update() # Trigger a redraw of the icon



class AnimatedSvgWidget(QWidget):
    """Draws an SVG and optionally rotates it for a smooth loading animation."""
    def __init__(self, file_path="", parent=None):
        super().__init__(parent)
        self.renderer = QSvgRenderer(file_path) if file_path else QSvgRenderer()
        self.setStyleSheet("background: transparent; border: none;")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) 
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate_icon)
        self._is_rotating = False

    def load(self, file_path):
        self.renderer.load(file_path)
        self.update()

    def start_rotation(self):
        if not self._is_rotating:
            self.timer.start(16) 
            self._is_rotating = True

    def stop_rotation(self):
        self.timer.stop()
        self.angle = 0
        self._is_rotating = False
        self.update()

    def rotate_icon(self):
        self.angle = (self.angle + 3) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._is_rotating:
            painter.translate(self.width() / 2, self.height() / 2)
            painter.rotate(self.angle)
            painter.translate(-self.width() / 2, -self.height() / 2)
        self.renderer.render(painter, QRectF(self.rect()))


class VerticalLabel(QWidget):
    """Custom widget to draw text rotated 90 degrees upwards."""
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text
        self.text_color = QColor("#026BBC")
        self.setMinimumHeight(60)
        self.setFixedWidth(30)
        
    def set_color(self, color_hex):
        self.text_color = QColor(color_hex)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(self.text_color)
        
        font = QFont("Segoe UI", 14, QFont.Weight.Bold) # Increased text size
        painter.setFont(font)
        
        metrics = QFontMetrics(font)
        
        # Dynamically elide the text (add ...) if it exceeds available height
        available_height = self.height()
        elided_text = metrics.elidedText(self.text, Qt.TextElideMode.ElideRight, available_height)
        
        text_height = metrics.height()
        text_width = metrics.horizontalAdvance(elided_text)
        
        # Start drawing from the center
        start_y = (self.height() + text_width) / 2
        painter.translate(self.width() / 2 + text_height / 4, start_y)
        painter.rotate(-90)
        painter.drawText(0, 0, elided_text)
        painter.end()


class VoiceTab(QFrame):
    """A single voice tab in the left panel."""
    clicked = pyqtSignal(str) # Emits the voice name when clicked
    unselectable_clicked = pyqtSignal()

    def __init__(self, voice_name, state="finished"):
        super().__init__()
        self.voice_name = voice_name
        self.original_state = "finished" if state == "selected" else state # Store this to revert later
        self.state = state # states: 'selected', 'finished', 'in_progress', 'waiting'
        self.is_hovered = False
        
        self.setFixedWidth(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 10, 5, 10) # Uniform margins
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.setSpacing(5)

        # Status icon
        self.icon_widget = AnimatedSvgWidget()
        self.icon_widget.setFixedSize(24, 24)
        self.layout.addWidget(self.icon_widget, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Vertical text
        self.v_label = VerticalLabel(self.voice_name)
        self.layout.addWidget(self.v_label, 1, alignment=Qt.AlignmentFlag.AlignHCenter) # stretch=1 forces label to fill space

        self.update_style()

    def set_state(self, new_state):
        self.state = new_state
        self.update_style()

    def enterEvent(self, event):
        self.is_hovered = True
        self.update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update_style()
        super().leaveEvent(event)

    def update_style(self):
        if self.state == "selected":
            bg_color = "#005BB5" if self.is_hovered else "#026BBC"
            self.setStyleSheet(f"QFrame {{ background-color: {bg_color}; border-radius: 15px; border: none; }}")
            self.v_label.set_color("#FFFFFF")
            self.icon_widget.hide() # No icon when active
            self.icon_widget.stop_rotation()
            self.setFixedHeight(110) # Decrease height
        else:
            bg_color = "#E6F0FA" if self.is_hovered else "white"
            self.setStyleSheet(f"QFrame {{ background-color: {bg_color}; border-radius: 15px; border: 2px solid #026BBC; }}")
            self.v_label.set_color("#026BBC")
            
            if self.state == "in_progress":
                self.icon_widget.show()
                self.icon_widget.load("icons/Loader.svg")
                self.icon_widget.start_rotation()
                self.setFixedHeight(140)
            elif self.state == "waiting":
                self.icon_widget.show()
                self.icon_widget.load("icons/Hourglass.svg")
                self.icon_widget.stop_rotation()
                self.setFixedHeight(140)
            else: # "finished"
                self.icon_widget.hide()
                self.icon_widget.stop_rotation()
                self.setFixedHeight(110) # Decrease height

    def mousePressEvent(self, event):
        if self.state in ["in_progress", "waiting"]:
            self.unselectable_clicked.emit()
            return
        self.clicked.emit(self.voice_name)
        super().mousePressEvent(event)



class ExitDialog(QDialog):
    """A custom popup to confirm exiting the validation screen."""
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

        title = QLabel("Exit to menu")
        title.setStyleSheet("color: #D32F2F; font-size: 26px; font-weight: bold; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        desc = QLabel("Are you sure you want to exit?\nYou can resume this project later.")
        desc.setStyleSheet("color: #333333; font-size: 16px; border: none; margin-top: 10px;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)

        exit_btn = QPushButton("Yes, Exit")
        exit_btn.setFixedSize(140, 40)
        exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exit_btn.setStyleSheet("""
            QPushButton {
                background-color: white; color: #D32F2F; font-weight: bold; 
                border-radius: 8px; font-size: 16px; border: 2px solid #D32F2F;
            }
            QPushButton:hover { background-color: #FFF0F2; }
        """)
        exit_btn.clicked.connect(self.accept) 

        stay_btn = QPushButton("No, Stay")
        stay_btn.setFixedSize(140, 40)
        stay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        stay_btn.setStyleSheet("""
            QPushButton {
                background-color: #026BBC; color: white; font-weight: bold; border-radius: 8px; font-size: 16px;
            }
            QPushButton:hover { background-color: #005BB5; }
        """)
        stay_btn.clicked.connect(self.reject) 

        btn_layout.addStretch()
        btn_layout.addWidget(exit_btn)
        btn_layout.addWidget(stay_btn)
        btn_layout.addStretch()

        bg_layout.addWidget(title)
        bg_layout.addWidget(desc)
        bg_layout.addStretch()
        bg_layout.addLayout(btn_layout)

        layout.addWidget(bg_frame)


class UnsavedChangesDialog(QDialog):
    """A custom popup to warn about unsaved bounding boxes."""
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

        title = QLabel("Unsaved Changes")
        title.setStyleSheet("color: #D32F2F; font-size: 26px; font-weight: bold; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        desc = QLabel("You have unsubmitted changes on this page.\nAre you sure you want to leave?")
        desc.setStyleSheet("color: #333333; font-size: 16px; border: none; margin-top: 10px;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)

        leave_btn = QPushButton("Leave anyway")
        leave_btn.setFixedSize(140, 40)
        leave_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        leave_btn.setStyleSheet("""
            QPushButton {
                background-color: white; color: #D32F2F; font-weight: bold; 
                border-radius: 8px; font-size: 16px; border: 2px solid #D32F2F;
            }
            QPushButton:hover { background-color: #FFF0F2; }
        """)
        leave_btn.clicked.connect(self.accept) 

        stay_btn = QPushButton("Stay")
        stay_btn.setFixedSize(140, 40)
        stay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        stay_btn.setStyleSheet("""
            QPushButton {
                background-color: #026BBC; color: white; font-weight: bold; border-radius: 8px; font-size: 16px;
            }
            QPushButton:hover { background-color: #005BB5; }
        """)
        stay_btn.clicked.connect(self.reject) 

        btn_layout.addStretch()
        btn_layout.addWidget(leave_btn)
        btn_layout.addWidget(stay_btn)
        btn_layout.addStretch()

        bg_layout.addWidget(title)
        bg_layout.addWidget(desc)
        bg_layout.addStretch()
        bg_layout.addLayout(btn_layout)

        layout.addWidget(bg_frame)


class ProceedDialog(QDialog):
    """A custom popup to confirm proceeding to the next phase."""
    def __init__(self, parent=None, next_step_name="the next step"):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(500, 220)

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

        title = QLabel("Proceed to next step")
        title.setStyleSheet("color: #026BBC; font-size: 26px; font-weight: bold; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        desc = QLabel(f"Are you sure you want to proceed to {next_step_name}?\nMake sure you have saved all manual corrections.")
        desc.setStyleSheet("color: #333333; font-size: 16px; border: none; margin-top: 10px;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)

        stay_btn = QPushButton("Stay")
        stay_btn.setFixedSize(140, 40)
        stay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        stay_btn.setStyleSheet("""
            QPushButton {
                background-color: white; color: #026BBC; font-weight: bold; 
                border-radius: 8px; font-size: 16px; border: 2px solid #026BBC;
            }
            QPushButton:hover { background-color: #E6F0FA; }
        """)
        stay_btn.clicked.connect(self.reject) 

        proceed_btn = QPushButton("Proceed")
        proceed_btn.setFixedSize(140, 40)
        proceed_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        proceed_btn.setStyleSheet("""
            QPushButton {
                background-color: #026BBC; color: white; font-weight: bold; border-radius: 8px; font-size: 16px;
            }
            QPushButton:hover { background-color: #005BB5; }
        """)
        proceed_btn.clicked.connect(self.accept) 

        btn_layout.addStretch()
        btn_layout.addWidget(stay_btn)
        btn_layout.addWidget(proceed_btn)
        btn_layout.addStretch()

        bg_layout.addWidget(title)
        bg_layout.addWidget(desc)
        bg_layout.addStretch()
        bg_layout.addLayout(btn_layout)

        layout.addWidget(bg_frame)


class ShortcutsDialog(QDialog):
    """A popup displaying keyboard shortcuts."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(400, 520)

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
        bg_layout.setContentsMargins(25, 25, 30, 25)

        title = QLabel("Keyboard Shortcuts")
        title.setStyleSheet("color: #026BBC; font-size: 26px; font-weight: bold; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        shortcuts_layout = QVBoxLayout()
        shortcuts_layout.setSpacing(12)
        
        shortcuts = [
            ("F1", "Open/Close this info"),
            ("Ctrl + Z", "Undo last action"),
            ("X", "Activate/Deactivate delete mode"),
            ("A", "Activate/Deactivate draw mode"),
            ("Ctrl + S", "Submit page"),
            ("C", "Previous page"),
            ("V", "Next page"),
            ("Shift + C", "Previous voice"),
            ("Shift + V", "Next voice")
        ]
        
        for key, desc in shortcuts:
            lbl = QLabel(f"<span style='color: #026BBC; font-weight: 600;'>{key}</span> <span style='color: #262626;'>- {desc}</span>")
            lbl.setStyleSheet("font-size: 16px; border: none; background: transparent;")
            shortcuts_layout.addWidget(lbl)

        # F1 to close it from inside the dialog
        QShortcut(QKeySequence("F1"), self).activated.connect(self.accept)

        close_btn = QPushButton("Close")
        close_btn.setFixedSize(350, 40)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #026BBC; color: white; font-weight: bold; border-radius: 8px; font-size: 16px;
            }
            QPushButton:hover { background-color: #005BB5; }
        """)
        close_btn.clicked.connect(self.accept)

        bg_layout.addWidget(title)
        bg_layout.addSpacing(15)
        bg_layout.addLayout(shortcuts_layout)
        bg_layout.addStretch()
        bg_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(bg_frame)



class ToastPopup(QLabel):
    """A floating notification label that disappears after 3 seconds."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("Prediction process for this voice not finished")
        self.setStyleSheet("""
            background-color: #333333; color: white; padding: 12px 20px; 
            border-radius: 8px; font-size: 14px; font-weight: bold;
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.hide)

    def show_message(self):
        self.setText("Prediction process for this voice not finished")
        self.adjustSize()
        if self.parent():
            x = (self.parent().width() - self.width()) // 2
            y = self.parent().height() - self.height() - 100
            self.move(x, y)
        self.show()
        self.raise_()
        self.timer.start(3000)

    def show_custom_message(self, text):
        """Allows displaying a specific message temporarily."""
        self.setText(text)
        self.adjustSize()
        if self.parent():
            x = (self.parent().width() - self.width()) // 2
            y = self.parent().height() - self.height() - 100
            self.move(x, y)
        self.show()
        self.raise_()
        self.timer.start(3000)


class ThumbnailLoaderWorker(QThread):
    """Loads and scales thumbnail images in the background to prevent UI freezing."""
    thumbnail_loaded = pyqtSignal(int, QImage)

    def __init__(self, image_tasks):
        super().__init__()
        self.image_tasks = image_tasks # List of tuples: (page_id, image_path)
        self._is_cancelled = False

    def run(self):
        for page_id, img_path in self.image_tasks:
            if self._is_cancelled:
                break
            
            if Path(img_path).exists():
                image = QImage(img_path)
                if not image.isNull():
                    # Scale in the background to save main thread CPU
                    scaled_image = image.scaled(60, 45, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    # Create rounded corners completely in the background thread!
                    rounded_image = QImage(scaled_image.size(), QImage.Format.Format_ARGB32_Premultiplied)
                    rounded_image.fill(Qt.GlobalColor.transparent)
                    
                    painter = QPainter(rounded_image)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                    
                    path = QPainterPath()
                    path.addRoundedRect(QRectF(rounded_image.rect()), 5, 5)
                    painter.setClipPath(path)
                    painter.drawImage(0, 0, scaled_image)
                    painter.end()
                    
                    self.thumbnail_loaded.emit(page_id, rounded_image)
                    
    def cancel(self):
        self._is_cancelled = True



class ImageCanvas(QWidget):
    """Custom widget to display a scaled image with rounded corners."""
    undo_state_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: white; border-radius: 12px; border: 2px solid #026BBC;")
        self.pixmap = None
        self.staves = []
        self.undo_stack = []
        self.mode = None # "draw" or "delete"
        self.drawing_start_pos = None
        self.drawing_current_pos = None
        self.image_rect = None # Caches the drawn area for hit-detection
        self.radius = 12

    def set_mode(self, mode):
        self.mode = mode
        if self.mode == "draw":
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif self.mode == "delete":
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_image(self, image_path, staves=None):
        """Loads a new image from the given path."""
        self.staves = copy.deepcopy(staves) if staves else []
        self.undo_stack = []
        self.undo_state_changed.emit(False)
        if Path(image_path).exists():
            self.pixmap = QPixmap(image_path)
        else:
            self.pixmap = None
        self.update()

    def paintEvent(self, event):
        # First, let the default styling (background, border) draw
        super().paintEvent(event)
        
        if not self.pixmap or self.pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Create a rounded clipping path so the image respects the border radius
        path = QPainterPath()
        # We shrink the drawing area by 2 pixels to keep the border visible
        path.addRoundedRect(2, 2, self.width() - 4, self.height() - 4, self.radius, self.radius)
        painter.setClipPath(path)

        # Scale the image to fit the widget while keeping aspect ratio
        scaled_pixmap = self.pixmap.scaled(
            self.width() - 4, 
            self.height() - 4, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )

        # Calculate coordinates to center the image
        x = int((self.width() - scaled_pixmap.width()) / 2)
        y = int((self.height() - scaled_pixmap.height()) / 2)
        self.image_rect = QRectF(x, y, scaled_pixmap.width(), scaled_pixmap.height())

        painter.drawPixmap(x, y, scaled_pixmap)

        # Draw the bounding boxes
        if self.staves:
            # Setup a beautiful 2px blue border for the boxes
            pen = QPen(QColor(2, 107, 188)) # #026BBC
            pen.setWidth(3)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            for staff in self.staves:
                xywhn = staff.get("staff_box_relative_xywh")
                if xywhn and len(xywhn) == 4:
                    x_c_norm, y_c_norm, w_norm, h_norm = xywhn
                    
                    box_w = w_norm * scaled_pixmap.width()
                    box_h = h_norm * scaled_pixmap.height()
                    box_x = x + (x_c_norm * scaled_pixmap.width()) - (box_w / 2)
                    box_y = y + (y_c_norm * scaled_pixmap.height()) - (box_h / 2)
                    
                    painter.drawRect(QRectF(box_x, box_y, box_w, box_h))

        # Draw the temporary dashed rectangle when the user is drawing
        if self.mode == "draw" and self.drawing_start_pos and self.drawing_current_pos:
            pen = QPen(QColor(2, 107, 188))
            pen.setWidth(2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(2, 107, 188, 50))) # 50/255 transparency for fill
            painter.drawRect(QRectF(self.drawing_start_pos, self.drawing_current_pos).normalized())
        
        painter.end()

    def mousePressEvent(self, event):
        if not self.image_rect or not self.pixmap:
            return
            
        if self.mode == "draw":
            if self.image_rect.contains(event.position()):
                self.drawing_start_pos = event.position()
                self.drawing_current_pos = event.position()
        elif self.mode == "delete":
            # Check collisions from top to bottom (delete highest layer first)
            for i in reversed(range(len(self.staves))):
                staff = self.staves[i]
                xywhn = staff.get("staff_box_relative_xywh")
                if xywhn and len(xywhn) == 4:
                    x_c, y_c, w_n, h_n = xywhn
                    bw = w_n * self.image_rect.width()
                    bh = h_n * self.image_rect.height()
                    bx = self.image_rect.x() + (x_c * self.image_rect.width()) - (bw / 2)
                    by = self.image_rect.y() + (y_c * self.image_rect.height()) - (bh / 2)
                    if QRectF(bx, by, bw, bh).contains(event.position()):
                        deleted_box = self.staves.pop(i)
                        self.undo_stack.append({'type': 'delete', 'index': i, 'box': deleted_box})
                        self.undo_state_changed.emit(True)
                        self.update()
                        break

    def mouseMoveEvent(self, event):
        if self.mode == "draw" and self.drawing_start_pos:
            # Clamp coordinates so the user can't draw outside the scaled image
            pos = event.position()
            x = max(self.image_rect.left(), min(pos.x(), self.image_rect.right()))
            y = max(self.image_rect.top(), min(pos.y(), self.image_rect.bottom()))
            self.drawing_current_pos = QPointF(x, y)
            self.update()

    def mouseReleaseEvent(self, event):
        if self.mode == "draw" and self.drawing_start_pos:
            rect = QRectF(self.drawing_start_pos, self.drawing_current_pos).normalized()
            
            # Prevent accidental tiny clicks creating micro-boxes
            if rect.width() > 5 and rect.height() > 5:
                nx1 = (rect.left() - self.image_rect.left()) / self.image_rect.width()
                ny1 = (rect.top() - self.image_rect.top()) / self.image_rect.height()
                nx2 = (rect.right() - self.image_rect.left()) / self.image_rect.width()
                ny2 = (rect.bottom() - self.image_rect.top()) / self.image_rect.height()
                
                new_staff = {
                    "staff_confidence": 1.0,
                    "staff_box_relative_xywh": [
                        round((nx1 + nx2) / 2.0, 6), 
                        round((ny1 + ny2) / 2.0, 6), 
                        round(nx2 - nx1, 6), 
                        round(ny2 - ny1, 6)
                    ],
                    "symbols": []
                }
                self.staves.append(new_staff)
                self.undo_stack.append({'type': 'add'})
                self.undo_state_changed.emit(True)
            
            self.drawing_start_pos = None
            self.drawing_current_pos = None
            self.update()

    def undo(self):
        """Reverts the last drawn or deleted bounding box on the current page."""
        if not self.undo_stack:
            return
        action = self.undo_stack.pop()
        if action['type'] == 'add':
            if self.staves:
                self.staves.pop()
        elif action['type'] == 'delete':
            self.staves.insert(action['index'], action['box'])
            
        self.undo_state_changed.emit(len(self.undo_stack) > 0)
        self.update()



class PageListItem(QFrame):
    clicked = pyqtSignal(int) # Emits page_id when clicked

    def __init__(self, page_id, num_boxes=0, is_selected=False):
        super().__init__()
        self.page_id = page_id
        self.is_selected = is_selected
        self.is_hovered = False
        
        self.setFixedHeight(70)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 5, 10, 5)
        
        self.text_label = QLabel(f"Page {self.page_id}")
        self.text_label.setStyleSheet("font-size: 18px; font-weight: 600; background: transparent; border: none;")

        self.boxes_label = QLabel(str(num_boxes))
        self.boxes_label.setStyleSheet("font-size: 18px; font-weight: 400; background: transparent; border: none;")
        
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(60, 45)
        self.thumb_label.setStyleSheet("background: transparent; border: none;") 
        
        layout.addWidget(self.text_label)
        layout.addStretch()
        layout.addWidget(self.boxes_label)
        layout.addSpacing(10)
        layout.addWidget(self.thumb_label)

        self.update_style()

    def update_boxes_count(self, num_boxes):
        self.boxes_label.setText(str(num_boxes))

    def set_thumbnail(self, qimage):
        """Receives the loaded QImage from the background thread and displays it."""
        self.thumb_label.setPixmap(QPixmap.fromImage(qimage))
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_selected(self, selected):
        self.is_selected = selected
        self.update_style()

    def enterEvent(self, event):
        self.is_hovered = True
        self.update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update_style()
        super().leaveEvent(event)

    def update_style(self):
        if self.is_selected:
            bg_color = "#005BB5" if self.is_hovered else "#026BBC"
            self.setStyleSheet(f"QFrame {{ background-color: {bg_color}; border-radius: 15px; border: none; }}")
            self.text_label.setStyleSheet("color: white; font-size: 18px; font-weight: 600; background: transparent; border: none;")
            self.boxes_label.setStyleSheet("color: white; font-size: 18px; font-weight: 400; background: transparent; border: none;")
        else:
            bg_color = "#E6F0FA" if self.is_hovered else "white"
            self.setStyleSheet(f"QFrame {{ background-color: {bg_color}; border-radius: 15px; border: 2px solid #026BBC; }}")
            self.text_label.setStyleSheet("color: #026BBC; font-size: 18px; font-weight: 600; background: transparent; border: none;")
            self.boxes_label.setStyleSheet("color: #026BBC; font-size: 18px; font-weight: 400; background: transparent; border: none;")


    def mousePressEvent(self, event):
        self.clicked.emit(self.page_id)
        super().mousePressEvent(event)


# --- MAIN SCREEN ---

class ValidateStavesScreen(QWidget):
    exit_requested = pyqtSignal()
    forward_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: #FAFAFA;")
        
        self.voice_tabs = []

        self.project_data = {} # Maps voice_name to its list of pages
        self.voice_folders = {} # Maps voice_name to actual folder name (e.g., Voice_01)
        self.page_items = []   # Stores the current PageListItem widgets

        self.current_page_index = 0 # Tracks the currently displayed page
        self.current_voice = ""     # Tracks the current voice
        self.project_path = ""      # Stores absolute path to current project folder
        self.all_background_tasks_finished = False # Tracks if background prediction is done

        self.thumbnail_thread = None # Keeps track of our background worker

        self.toast = ToastPopup(self)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 1. Header Bar ---
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet("background-color: #026BBC;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        # Back Button
        self.back_btn = TopBarButton("Exit to menu", "icons/Back.svg", "icons/Back_gray.svg", icon_size=24, icon_pos="left", width=180)
        self.back_btn.clicked.connect(self.attempt_exit)

        # Title
        title_label = QLabel("Validate staves")
        title_label.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Forward Button
        self.forward_btn = TopBarButton("Go to symbols detection", "icons/Forward.svg", "icons/Forward_gray.svg", icon_size=24, icon_pos="right", width=280)
        self.forward_btn.clicked.connect(self.attempt_forward)

        # Absolute Centering Trick
        left_container = QWidget()
        left_container.setFixedWidth(300)
        left_layout = QHBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.back_btn, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        right_container = QWidget()
        right_container.setFixedWidth(300) # Must match the left side exactly!
        right_layout = QHBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.forward_btn, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        header_layout.addWidget(left_container)
        header_layout.addWidget(title_label, 1, alignment=Qt.AlignmentFlag.AlignCenter) 
        header_layout.addWidget(right_container)
        
        main_layout.addWidget(header)

        # --- 2. Body Area ---
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(10, 10, 10, 10)
        body_layout.setSpacing(10)

        # LEFT COLUMN: Voice Tabs
        self.voices_scroll = QScrollArea()
        self.voices_scroll.setFixedWidth(50) # Narrowed from 80px to safely hug the 50px buttons
        self.voices_scroll.setWidgetResizable(True)
        self.voices_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.voices_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.voices_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.voices_container = QWidget()
        self.voices_container.setStyleSheet("background: transparent;")
        self.voices_layout = QVBoxLayout(self.voices_container)
        self.voices_layout.setContentsMargins(0, 0, 0, 0)
        self.voices_layout.setSpacing(10)
        self.voices_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        
        self.voices_scroll.setWidget(self.voices_container)
        body_layout.addWidget(self.voices_scroll)

        # --- PAGES COLUMN ---
        self.pages_scroll = QScrollArea()
        self.pages_scroll.setFixedWidth(220) # Width matching the mockup
        self.pages_scroll.setWidgetResizable(True)
        self.pages_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.pages_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { border: none; background: transparent; width: 8px; margin: 0px 0px 0px 0px; }
            QScrollBar::handle:vertical { background: #CCCCCC; min-height: 30px; border-radius: 4px; }
            QScrollBar::handle:vertical:hover { background: #AAAAAA; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; background: none; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; } 
        """)

        self.pages_container = QWidget()
        self.pages_container.setStyleSheet("background: transparent;")
        self.pages_layout = QVBoxLayout(self.pages_container)
        self.pages_layout.setContentsMargins(0, 0, 5, 0) # 5px right margin to cleanly shrink items away from scrollbar
        self.pages_layout.setSpacing(10)
        self.pages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.pages_scroll.setWidget(self.pages_container)
        body_layout.addWidget(self.pages_scroll) 
        # -------------------------

        # --- MAIN CONTENT AREA (Vertical: [Prev | Canvas | Next] over [Action Buttons]) ---
        self.main_content_area = QWidget()
        main_content_layout = QVBoxLayout(self.main_content_area)
        main_content_layout.setContentsMargins(0, 0, 0, 0)
        main_content_layout.setSpacing(10)

        # ==========================================
        # --- TOP ROW: Image Viewer Container ---
        # ==========================================
        image_viewer_container = QWidget()
        image_viewer_layout = QHBoxLayout(image_viewer_container)
        image_viewer_layout.setContentsMargins(0, 0, 0, 0)
        image_viewer_layout.setSpacing(10)

        # Previous Button 
        self.prev_btn = QPushButton()
        self.prev_btn.setFixedWidth(50)
        self.prev_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setStyleSheet("""
            QPushButton { background-color: #026BBC; border-radius: 12px; border: none; }
            QPushButton:hover { background-color: #005BB5; }
            QPushButton:disabled { background-color: #CCCCCC; }
        """)
        prev_layout = QVBoxLayout(self.prev_btn)
        prev_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prev_layout.setContentsMargins(0, 0, 0, 0)
        prev_icon = QSvgWidget("icons/Back.svg")
        prev_icon.setFixedSize(30, 30)
        prev_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        prev_icon.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        prev_icon.setStyleSheet("background: transparent; border: none;")
        prev_layout.addWidget(prev_icon)
        self.prev_btn.clicked.connect(self.go_to_previous_page)

        # The Image Canvas 
        self.image_canvas = ImageCanvas()

        # Next Button 
        self.next_btn = QPushButton()
        self.next_btn.setFixedWidth(50)
        self.next_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setStyleSheet("""
            QPushButton { background-color: #026BBC; border-radius: 12px; border: none; }
            QPushButton:hover { background-color: #005BB5; }
            QPushButton:disabled { background-color: #CCCCCC; }
        """)
        next_layout = QVBoxLayout(self.next_btn)
        next_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        next_layout.setContentsMargins(0, 0, 0, 0)
        next_icon = QSvgWidget("icons/Forward.svg")
        next_icon.setFixedSize(30, 30)
        next_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        next_icon.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        next_icon.setStyleSheet("background: transparent; border: none;")
        next_layout.addWidget(next_icon)
        self.next_btn.clicked.connect(self.go_to_next_page)

        # Assemble Top Row
        image_viewer_layout.addWidget(self.prev_btn)
        image_viewer_layout.addWidget(self.image_canvas, 1) # Canvas stretches
        image_viewer_layout.addWidget(self.next_btn)

        # ==========================================
        # --- BOTTOM ROW: Action Buttons ---
        # ==========================================
        action_buttons_container = QWidget()
        action_buttons_layout = QHBoxLayout(action_buttons_container)
        action_buttons_layout.setContentsMargins(0, 0, 0, 0)
        action_buttons_layout.setSpacing(10)

        # 1. Info Button
        self.info_btn = QPushButton()
        self.info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.info_btn.setFixedSize(50, 50)
        self.info_btn.setStyleSheet("""
            QPushButton { background-color: white; border-radius: 12px; border: 2px solid #026BBC; }
            QPushButton:hover { background-color: #E6F0FA; }
        """)
        info_layout = QVBoxLayout(self.info_btn)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_icon = QSvgWidget("icons/Info.svg")
        info_icon.setFixedSize(30, 30)
        info_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        info_icon.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        info_icon.setStyleSheet("background: transparent; border: none;")
        info_layout.addWidget(info_icon)
        self.info_btn.clicked.connect(self.show_shortcuts_info)

        # 2. Undo Button
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_btn.setFixedHeight(50)
        self.undo_btn.setMinimumWidth(100)
        self.undo_btn.setEnabled(False) # Inactive by default
        self.undo_btn.setStyleSheet("""
            QPushButton { background-color: white; color: #026BBC; font-size: 20px; font-weight: bold; border-radius: 12px; border: 2px solid #026BBC; }
            QPushButton:hover:!disabled { background-color: #E6F0FA; }
            QPushButton:disabled { color: #CCCCCC; border: 2px solid #CCCCCC; }
        """)
        self.undo_btn.clicked.connect(self.on_undo_clicked)
        
        # Bind the canvas undo state to the undo button
        self.image_canvas.undo_state_changed.connect(self.undo_btn.setEnabled)

        # 3. Delete Toggle Button
        self.delete_btn = ToggleActionButton("Delete")
        self.delete_btn.clicked.connect(self.on_delete_clicked)

        # 4. Draw Toggle Button
        self.draw_btn = ToggleActionButton("Draw")
        self.draw_btn.clicked.connect(self.on_draw_clicked)

        # 5. Submit Page Button
        self.submit_btn = QPushButton("Submit page")
        self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_btn.setFixedHeight(50)
        self.submit_btn.setEnabled(False) # Inactive by default until changes are made
        self.submit_btn.setStyleSheet("""
            QPushButton { background-color: #026BBC; color: white; font-size: 20px; font-weight: bold; border-radius: 12px; border: none; }
            QPushButton:hover:!disabled { background-color: #005BB5; }
            QPushButton:disabled { background-color: #CCCCCC; color: #888888; }
        """)
        self.submit_btn.clicked.connect(self.on_submit_clicked)
        
        self.image_canvas.undo_state_changed.connect(self.submit_btn.setEnabled)

        # Assemble Bottom Row
        action_buttons_layout.addWidget(self.info_btn)
        action_buttons_layout.addWidget(self.undo_btn)
        action_buttons_layout.addWidget(self.delete_btn, 1) # Stretch evenly
        action_buttons_layout.addWidget(self.draw_btn, 1)   # Stretch evenly
        action_buttons_layout.addWidget(self.submit_btn, 1) # Stretch evenly

        # ==========================================
        # --- ASSEMBLE MAIN CONTENT AREA ---
        # ==========================================
        main_content_layout.addWidget(image_viewer_container, 1) # Viewer gets vertical expansion
        main_content_layout.addWidget(action_buttons_container)  # Buttons stay fixed at the bottom

        body_layout.addWidget(self.main_content_area, 1) 
        main_layout.addLayout(body_layout, 1)

        # --- Keyboard Shortcuts ---
        QShortcut(QKeySequence("F1"), self).activated.connect(self.info_btn.click)
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.undo_btn.click)
        QShortcut(QKeySequence("X"), self).activated.connect(self.delete_btn.click)
        QShortcut(QKeySequence("A"), self).activated.connect(self.draw_btn.click)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.submit_btn.click)
        QShortcut(QKeySequence("C"), self).activated.connect(self.prev_btn.click)
        QShortcut(QKeySequence("V"), self).activated.connect(self.next_btn.click)
        QShortcut(QKeySequence("Shift+C"), self).activated.connect(self.go_to_previous_voice)
        QShortcut(QKeySequence("Shift+V"), self).activated.connect(self.go_to_next_voice)

    def resizeEvent(self, event):
        """Keep the toast centered if the user resizes the window while it's showing."""
        super().resizeEvent(event)
        if self.toast.isVisible():
            x = (self.width() - self.toast.width()) // 2
            y = self.height() - self.toast.height() - 100
            self.toast.move(x, y)

    def show_shortcuts_info(self):
        dialog = ShortcutsDialog(self)
        dialog.exec()

    def check_unsaved_changes(self):
        """Returns True if it's safe to navigate away, False if navigation should be cancelled."""
        if self.submit_btn.isEnabled():
            dialog = UnsavedChangesDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # User wants to discard changes. Clear undo state so it doesn't block future nav
                self.image_canvas.undo_stack.clear()
                self.image_canvas.undo_state_changed.emit(False)
                return True
            else:
                return False
        return True

    def attempt_exit(self):
        if self.submit_btn.isEnabled():
            if not self.check_unsaved_changes():
                return
        else:
            dialog = ExitDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
                
        if hasattr(self, 'poll_timer') and self.poll_timer.isActive():
            self.poll_timer.stop()
        self.exit_requested.emit()

    def attempt_forward(self):
        if not self.all_background_tasks_finished:
            self.toast.show_custom_message("Background predictions are still running. Please wait.")
            return
            
        if not self.check_unsaved_changes():
            return
            
        dialog = ProceedDialog(self, "symbols detection")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        if hasattr(self, 'poll_timer') and self.poll_timer.isActive():
            self.poll_timer.stop()
        self.forward_requested.emit()

    def load_voices_from_disk(self, project_path):
        self.project_path = project_path
        self.project_state_path = Path(project_path) / "project_state.json"
        
        self.poll_project_state(initial_load=True)
        
        if not hasattr(self, 'poll_timer'):
            self.poll_timer = QTimer(self)
            self.poll_timer.timeout.connect(lambda: self.poll_project_state(initial_load=False))
        self.poll_timer.start(2000)

    def poll_project_state(self, initial_load=False):
        """Reads project_state.json to update voice states and automatically load new JSONs."""
        if not self.project_state_path.exists():
            return
            
        try:
            with open(self.project_state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            return # File might be locked by writer, skip this tick
            
        voices_dict = state.get("voices", {})
        voices_info = []
        in_progress_found = False
        all_done = True
        
        for v_folder in sorted(voices_dict.keys()):
            v_data = voices_dict[v_folder]
            v_name = v_data.get("metadata", {}).get("voice_name", v_folder)
            pred_status = v_data.get("prediction_status", {})
            
            has_error = pred_status.get("has_error") == 1
            is_done = (pred_status.get("staff_prediction") == 1 or pred_status.get("staff_images_saved") == 1) or has_error
            
            if is_done:
                v_state = "finished"
                # Load its data if we haven't yet
                if v_name not in self.project_data:
                    json_file = Path(self.project_path) / v_folder / f"{v_folder}_data.json"
                    if json_file.exists():
                        try:
                            with open(json_file, "r", encoding="utf-8") as f:
                                data = json.load(f)
                                for page in data.get("pages", []):
                                    if "page_image_path" in page:
                                        root_dir = Path(__file__).parent.parent
                                        full_path = root_dir / page["page_image_path"]
                                        page["absolute_image_path"] = str(full_path.resolve())
                                self.project_data[v_name] = data.get("pages", [])
                                self.voice_folders[v_name] = v_folder
                        except Exception:
                            pass
            else:
                all_done = False
                if not in_progress_found:
                    v_state = "in_progress"
                    in_progress_found = True
                else:
                    v_state = "waiting"
                    
            voices_info.append({"name": v_name, "state": v_state})
            
        if initial_load:
            self.populate_voice_tabs(voices_info)
        else:
            self.update_voice_tabs_state(voices_info)
            
        if all_done and hasattr(self, 'poll_timer') and self.poll_timer.isActive():
            self.poll_timer.stop()
            
        self.all_background_tasks_finished = all_done

    def populate_voice_tabs(self, voices_info):
        """Creates widgets for the found voices (Initial Load)."""
        # Clear old tabs
        for i in reversed(range(self.voices_layout.count())): 
            widget = self.voices_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self.voice_tabs.clear()

        # Create new tabs based on info
        for index, v_info in enumerate(voices_info):
            tab = VoiceTab(v_info["name"], state=v_info["state"])
            tab.clicked.connect(self.on_voice_tab_clicked)
            tab.unselectable_clicked.connect(self.toast.show_message)
            self.voices_layout.addWidget(tab)
            self.voice_tabs.append(tab)
            
        # Automatically select the first voice and load its pages
        if voices_info:
            self.voice_tabs[0].set_state("selected")
            self.populate_pages_list(voices_info[0]["name"])

    def update_voice_tabs_state(self, voices_info):
        """Updates states of existing tabs without rebuilding them to prevent flickering."""
        for tab in self.voice_tabs:
            info = next((v for v in voices_info if v["name"] == tab.voice_name), None)
            if info:
                if tab.state == "selected":
                    tab.original_state = info["state"]
                else:
                    if tab.original_state != info["state"]:
                        tab.original_state = info["state"]
                        tab.set_state(info["state"])

    def on_voice_tab_clicked(self, clicked_voice_name):
        """Handles click events on a voice tab."""
        if clicked_voice_name == self.current_voice:
            return
            
        if not self.check_unsaved_changes():
            return
        
        print(f"Switching to voice: {clicked_voice_name}")
        for tab in self.voice_tabs:
            if tab.voice_name == clicked_voice_name:
                tab.set_state("selected")
            else:
                # Revert others to their original state (fixes the bug!)
                tab.set_state(tab.original_state)
                
        # Load the pages for the newly selected voice
        self.populate_pages_list(clicked_voice_name)
    
    def populate_pages_list(self, voice_name):
        """Builds the list of pages for the selected voice."""

        self.current_voice = voice_name
        self.current_page_index = 0 # Reset to first page when changing voice

        # 1. Safely cancel any currently running thumbnail load if the user clicks fast
        if self.thumbnail_thread and self.thumbnail_thread.isRunning():
            self.thumbnail_thread.cancel()
            self.thumbnail_thread.wait()
            
        # 2. Clear old items
        for i in reversed(range(self.pages_layout.count())): 
            widget = self.pages_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self.page_items.clear()

        pages_data = self.project_data.get(voice_name, [])
        load_tasks = []
        
        for i, page in enumerate(pages_data):
            page_id = page.get("page_id", i + 1)
            img_path = page.get("absolute_image_path", "")
            load_tasks.append((page_id, img_path))
            
            # Create the list item instantly without loading the image yet
            num_boxes = len(page.get("staves", []))
            item = PageListItem(page_id, num_boxes=num_boxes, is_selected=(i == 0)) 
            item.clicked.connect(self.on_page_item_clicked)
            self.pages_layout.addWidget(item)
            self.page_items.append(item)
            
        # 3. Start the background thread to load all the images
        self.thumbnail_thread = ThumbnailLoaderWorker(load_tasks)
        self.thumbnail_thread.thumbnail_loaded.connect(self.on_thumbnail_loaded)
        self.thumbnail_thread.start()
        self.update_canvas_and_controls() # Draw the first page
        
    def on_thumbnail_loaded(self, page_id, qimage):
        """Slot that catches the signal from the worker and updates the specific UI element."""
        for item in self.page_items:
            if item.page_id == page_id:
                item.set_thumbnail(qimage)
                break
    
    def on_page_item_clicked(self, clicked_page_id):
        """Handles click events on a page thumbnail."""
        pages_data = self.project_data.get(self.current_voice, [])

        target_index = self.current_page_index
        for i, page in enumerate(pages_data):
            if page.get("page_id") == clicked_page_id:
                target_index = i
                break

        if target_index != self.current_page_index:
            if not self.check_unsaved_changes():
                return
            self.current_page_index = target_index
            self.update_canvas_and_controls()

    def update_canvas_and_controls(self):
        """Updates the image shown and enables/disables navigation buttons."""
        pages_data = self.project_data.get(self.current_voice, [])
        if not pages_data:
            self.image_canvas.set_image("")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return

        # Load the current image
        current_page_data = pages_data[self.current_page_index]
        staves_data = current_page_data.get("staves", [])
        self.image_canvas.set_image(current_page_data.get("absolute_image_path", ""), staves=staves_data)

        # Update button states
        self.prev_btn.setEnabled(self.current_page_index > 0)
        self.next_btn.setEnabled(self.current_page_index < len(pages_data) - 1)

        # Highlight the correct thumbnail in the list
        current_page_id = current_page_data.get("page_id")
        for item in self.page_items:
            is_active = (item.page_id == current_page_id)
            item.set_selected(is_active)
            if is_active:
                # Smoothly scrolls the list just enough to keep the active item visible (with a 10px margin)
                self.pages_scroll.ensureWidgetVisible(item, 0, 10)

    def go_to_previous_voice(self):
        """Action for the Shift+C shortcut."""
        if not self.voice_tabs:
            return
        current_idx = next((i for i, tab in enumerate(self.voice_tabs) if tab.voice_name == self.current_voice), -1)
        if current_idx > 0:
            target_tab = self.voice_tabs[current_idx - 1]
            if target_tab.original_state in ["in_progress", "waiting"]:
                self.toast.show_message()
                return
            self.on_voice_tab_clicked(target_tab.voice_name)

    def go_to_next_voice(self):
        """Action for the Shift+V shortcut."""
        if not self.voice_tabs:
            return
        current_idx = next((i for i, tab in enumerate(self.voice_tabs) if tab.voice_name == self.current_voice), -1)
        if 0 <= current_idx < len(self.voice_tabs) - 1:
            target_tab = self.voice_tabs[current_idx + 1]
            if target_tab.original_state in ["in_progress", "waiting"]:
                self.toast.show_message()
                return
            self.on_voice_tab_clicked(target_tab.voice_name)

    def go_to_previous_page(self):
        """Action for the Previous button."""
        if self.current_page_index > 0:
            if not self.check_unsaved_changes():
                return
            self.current_page_index -= 1
            self.update_canvas_and_controls()

    def go_to_next_page(self):
        """Action for the Next button."""
        pages_data = self.project_data.get(self.current_voice, [])
        if self.current_page_index < len(pages_data) - 1:
            if not self.check_unsaved_changes():
                return
            self.current_page_index += 1
            self.update_canvas_and_controls()

    def on_delete_clicked(self):
        """Toggle Delete mode on/off, ensuring Draw mode turns off."""
        new_state = not self.delete_btn.is_selected
        self.delete_btn.set_selected(new_state)
        if new_state:
            self.draw_btn.set_selected(False)
            self.image_canvas.set_mode("delete")
        else:
            self.image_canvas.set_mode(None)

    def on_draw_clicked(self):
        """Toggle Draw mode on/off, ensuring Delete mode turns off."""
        new_state = not self.draw_btn.is_selected
        self.draw_btn.set_selected(new_state)
        if new_state:
            self.delete_btn.set_selected(False)
            self.image_canvas.set_mode("draw")
        else:
            self.image_canvas.set_mode(None)

    def on_undo_clicked(self):
        """Triggers the canvas to undo the last action."""
        self.image_canvas.undo()

    def on_submit_clicked(self):
        """Saves current staff boxes to JSON mathematically converting them to absolute coordinates."""
        if not self.current_voice or not self.project_path:
            return
            
        pages_data = self.project_data.get(self.current_voice, [])
        if not pages_data:
            return
            
        current_page = pages_data[self.current_page_index]
        page_id = current_page.get("page_id")
        
        # Get current staves and sort them top-to-bottom (Y), then left-to-right (X)
        updated_staves = self.image_canvas.staves
        updated_staves.sort(key=lambda s: (s.get("staff_box_relative_xywh", [0, 0, 0, 0])[1], 
                                           s.get("staff_box_relative_xywh", [0, 0, 0, 0])[0]))
        
        # Calculate Absolute Coordinates based on Original Image Dimensions
        img_path = current_page.get("absolute_image_path", "")
        img_w, img_h = 0, 0
        if Path(img_path).exists():
            img = QImage(img_path)
            img_w, img_h = img.width(), img.height()
            
        ordered_staves = []
        for idx, staff in enumerate(updated_staves):
            xywhn = staff.get("staff_box_relative_xywh")
            xywhn_rounded = [round(val, 6) for val in xywhn] if xywhn else [0, 0, 0, 0]
            
            abs_xyxy = staff.get("staff_box_absolute_xyxy", [0, 0, 0, 0])
            if xywhn and len(xywhn) == 4 and img_w > 0 and img_h > 0:
                x_c, y_c, w_n, h_n = xywhn
                x1 = (x_c - w_n / 2) * img_w
                y1 = (y_c - h_n / 2) * img_h
                x2 = (x_c + w_n / 2) * img_w
                y2 = (y_c + h_n / 2) * img_h
                abs_xyxy = [round(x1), round(y1), round(x2), round(y2)]
                
            # Deepcopy to seamlessly preserve hidden meta-keys like staff_image_path 
            # if they were already created by a background pipeline thread!
            new_staff = copy.deepcopy(staff)
            new_staff.update({
                "staff_number": idx,
                "staff_confidence": staff.get("staff_confidence", 1.0),
                "staff_box_absolute_xyxy": abs_xyxy,
                "staff_box_relative_xywh": xywhn_rounded,
                "symbols": staff.get("symbols", [])
            })
            ordered_staves.append(new_staff)
            
        # Update in-memory data so it persists when navigating between pages!
        current_page["staves"] = ordered_staves
        self.image_canvas.staves = ordered_staves
        
        for item in self.page_items:
            if item.page_id == page_id:
                item.update_boxes_count(len(ordered_staves))
                break
                
        # Now safely write to the JSON file
        folder_name = self.voice_folders.get(self.current_voice, self.current_voice)
        json_file = Path(self.project_path) / folder_name / f"{folder_name}_data.json"
        if json_file.exists():
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                for p in data.get("pages", []):
                    if p.get("page_id") == page_id:
                        p["staves"] = ordered_staves
                        break
                        
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                    
                # --- RESET DOWNSTREAM PIPELINE STATE ---
                state_file = Path(self.project_path) / "project_state.json"
                if state_file.exists():
                    with open(state_file, "r", encoding="utf-8") as sf:
                        state_data = json.load(sf)
                        
                    if folder_name in state_data.get("voices", {}):
                        v_status = state_data["voices"][folder_name]["prediction_status"]
                        v_status["staff_images_saved"] = 0
                        v_status["notes_prediction"] = 0
                        v_status["notes_images_saved"] = 0
                        v_status["position_classification"] = 0
                        
                        s_recon = state_data["voices"][folder_name]["score_reconstruction"]
                        s_recon["agnostic_to_partially_semantic"] = 0
                        s_recon["partially_semantic_to_semantic"] = 0
                        s_recon["one_voice_musicxml_saved"] = 0
                        
                        state_data["global_state"]["measure_synchronization_finished"] = 0
                        state_data["global_state"]["combined_musicxml_saved"] = 0
                        state_data["global_state"]["measure_duration_validation_finished"] = 0
                        
                    with open(state_file, "w", encoding="utf-8") as sf:
                        json.dump(state_data, sf, indent=4)
                        
                self.toast.show_custom_message("Staff bounding boxes updated")
                
                # Clear undo stack so buttons disable again until new changes are made
                self.image_canvas.undo_stack.clear()
                self.image_canvas.undo_state_changed.emit(False)
            except Exception as e:
                self.toast.show_custom_message(f"Error saving: {e}")
        else:
            self.toast.show_custom_message("Error: JSON file not found!")


# --- TESTING BLOCK (Contains all hardcoded paths for standalone testing) ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ValidateStavesScreen()
    window.resize(1280, 720)
    
    # Define the path ONLY for testing this screen
    test_path = "C:/Files/Programming_projects/nanoScore/Projects/MANUAL_staff_corrections"
    
    # Attempt to load voices from the path
    window.load_voices_from_disk(test_path)
    
    # If the path was not found or is empty, inject dummy data for visual testing
    if not window.voice_tabs:
        print(f"Path {test_path} not found or empty. Using dummy data.")
        dummy_info = [
            {"name": "Dessus", "state": "selected"},
            {"name": "Haute-contre", "state": "in_progress"},
            {"name": "Taille", "state": "waiting"},
            {"name": "Basse", "state": "waiting"}
        ]
        window.populate_voice_tabs(dummy_info)

    window.show()
    sys.exit(app.exec())