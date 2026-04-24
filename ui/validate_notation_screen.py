import sys
import json
import copy
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFrame, QScrollArea, QSizePolicy, QDialog,
                             QGraphicsView, QGraphicsScene, QGraphicsItem)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRectF, QPointF, QEventLoop, QThread, QMimeData, QPoint
from PyQt6.QtGui import QPainter, QFontMetrics, QColor, QFont, QPixmap, QImage, QPainterPath, QBrush, QPen, QShortcut, QKeySequence, QTransform, QDrag
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtSvgWidgets import QSvgWidget, QGraphicsSvgItem


# --- HELPER CLASSES ---

ID_TO_SVG = {
    0: "flat", 1: "natural", 2: "sharp",
    3: "barline", 4: "barline_double", 
    5: "note_breve", 6: "cadence_point", 7: "clef_c", 8: "clef_f", 9: "clef_g",
    11: "time_2", 12: "time_3", 13: "dot", 14: "fermata",
    15: "note_longa", 16: "note_maxima", 17: "note_eighth", 18: "note_half", 19: "note_quarter",
    20: "note_16th", 21: "note_whole", 22: "note_whole_colored",
    23: "repeat", 24: "rest_breve", 25: "rest_eighth", 26: "rest_half",
    27: "rest_longa", 28: "rest_quarter", 29: "rest_16th", 30: "rest_whole",
    31: "slur", 32: "time_c", 33: "time_cut", 34: "rest_maxima"
}

SVG_TO_ID = {v: k for k, v in ID_TO_SVG.items()}

# Height of the symbol relative to the line spacing (1.0 = exactly the distance between two staff lines)
SYMBOL_HEIGHTS = {
    13: 1.15,   # dot 
    2: 1.5,    # sharp 
    0: 2.5,    # flat
    1: 2,    # natural
    21: 1.4,   # whole note
    22: 1.4,   # colored whole note
    5: 1.2,    # breve
    15: 3.0,   # longa
    16: 3.0,   # maxima
    17: 3.0,   # eighth
    18: 3.0,   # half
    19: 3.0,   # quarter
    20: 3.0,   # 16th
    24: 1,   # rest_breve
    25: 1.25,   # rest_eighth
    26: 1,   # rest_half
    27: 2,   # rest_longa
    28: 1.25,   # rest_quarter
    29: 1.25,   # rest_16th
    30: 1,   # rest_whole
    34: 3.0, # rest_maxima
    3: 5.0,    # barline
    4: 5.0,    # barline_double
    23: 4.0,   # repeat
    7: 4.0,    # clef_c
    8: 5.0,    # clef_f
    9: 3.5,    # clef_g
    11: 1.5,   # time_2
    12: 1.5,   # time_3
    32: 1.5,   # time_c
    33: 4.0,   # time_cut
    6: 2.0,    # cadence_point
    14: 1.5,   # fermata
}

class InteractiveSymbolItem(QGraphicsSvgItem):
    """A draggable SVG symbol for the notation editor."""
    def __init__(self, sym_data, scene_w, scene_h, staff_top_y, line_spacing):
        class_id = sym_data.get("class_id", 0)
        icon_name = ID_TO_SVG.get(class_id, "note_quarter") # fallback to quarter note
        svg_path = f"icons/symbol_icons/{icon_name}.svg"
        super().__init__(svg_path)
        
        self.sym_data = sym_data
        self.scene_w = scene_w
        self.scene_h = scene_h
        self.staff_top_y = staff_top_y
        self.line_spacing = line_spacing
        
        self.scaled_w = 0
        self.scaled_h = 0
        
        self.setup_grid_map()
        self.setup_anchor()
            
        # Make the SVG interactive
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.is_resizing = False
        self.resize_edge = None
        if class_id == 31:
            self.setAcceptHoverEvents(True)
        
        # Calculate its position based on the JSON YOLO coordinates
        xywhn = sym_data.get("symbol_box_relative_xywh")
        if xywhn and len(xywhn) == 4:
            x_c_norm, y_c_norm, w_norm, h_norm = xywhn
            
            rect = self.boundingRect()
            if rect.width() > 0 and rect.height() > 0:
                # 1. Run visuals with a dummy L3 anchor just to establish scaled dimensions
                self.update_visuals(self.get_y_from_pos("L", 3))
                
                # 2. Compute raw anchor Y. We must account for the fact that YOLO's center 
                # shifts depending on whether the symbol is upright or upside down!
                yolo_center_y = y_c_norm * scene_h
                
                needs_flip = False
                if class_id in [6, 14, 31]:
                    needs_flip = yolo_center_y > self.get_y_from_pos("L", 3)
                elif class_id in [15, 16, 17, 18, 19, 20]:
                    needs_flip = yolo_center_y <= self.get_y_from_pos("L", 3)
                    
                if needs_flip:
                    raw_anchor_y = yolo_center_y - self.scaled_h * (self.anchor_y_ratio - 0.5)
                else:
                    raw_anchor_y = yolo_center_y + self.scaled_h * (self.anchor_y_ratio - 0.5)
                
                # 3. Compute initial mathematically snapped anchor Y
                snapped_anchor_y = self.calculate_y(raw_anchor_y, is_dragging=False)
                
                # 4. Now run visuals again with the TRUE snapped Y so rotation is accurate!
                self.update_visuals(snapped_anchor_y)
                
                # Immediately fix any sloppy YOLO relative coordinates so JSON saves cleanly later
                visual_center_y = self.get_visual_center_y(snapped_anchor_y)
                self.sym_data["symbol_box_relative_xywh"][1] = round(visual_center_y / scene_h, 6)
                self.update_position_data(snapped_anchor_y)
                
                # Position the item (origin is top left, so we offset by anchor)
                unscaled_anchor_x = rect.x() + rect.width() / 2
                unscaled_anchor_y = rect.y() + rect.height() * self.anchor_y_ratio
                self.setPos((x_c_norm * scene_w) - unscaled_anchor_x, snapped_anchor_y - unscaled_anchor_y)

        # Enable tracking position changes AFTER initial setup
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

    def setup_grid_map(self):
        """Pre-calculates the exact absolute Y pixel coordinates for all standard lines and spaces."""
        self.grid_map = {}
        # Pre-calculate a generous range from 5 ledger lines below to 15 ledger lines above
        for pos_num in range(-5, 16):
            self.grid_map[("L", pos_num)] = self.staff_top_y + (5 - pos_num) * self.line_spacing
            self.grid_map[("S", pos_num)] = self.staff_top_y + (5 - pos_num) * self.line_spacing - (self.line_spacing / 2)

    def setup_anchor(self):
        class_id = self.sym_data.get("class_id", 0)
        self.anchor_y_ratio = 0.5 # Default center
        if class_id == 0: # flat (bulb aligned with grid)
            self.anchor_y_ratio = 0.82
        elif class_id == 8: # clef_f (curl on L4)
            self.anchor_y_ratio = 0.333
        elif class_id == 9: # clef_g (curl on L2)
            self.anchor_y_ratio = 0.75
        elif class_id in [17, 18, 19, 20]: # Stemmed notes (stem UP by default, head at bottom)
            self.anchor_y_ratio = 0.767
        elif class_id in [15, 16]: # Longa, maxima (stem DOWN by default, head at top)
            self.anchor_y_ratio = 0.8

    def get_visual_center_y(self, anchor_y):
        """Calculates the true center of the visual bounding box, accounting for 180-degree rotations and vertical flips."""
        original_center_y = anchor_y - self.scaled_h * self.anchor_y_ratio + self.scaled_h / 2
        if self.rotation() == 180 or self.transform().m22() < 0:
            return anchor_y + (anchor_y - original_center_y)
        return original_center_y
            
    def update_visuals(self, anchor_y):
        """Re-evaluates scaling, rotation, vertical flipping, and tinting."""
        class_id = self.sym_data.get("class_id", 0)
        rect = self.boundingRect()
        if rect.width() == 0 or rect.height() == 0: return

        origin_x = rect.x() + rect.width() / 2
        origin_y = rect.y() + rect.height() * self.anchor_y_ratio

        # Update transform origin to perfectly wrap around the mathematical anchor
        self.setTransformOriginPoint(origin_x, origin_y)

        transform = QTransform()
        # Scale around the anchor point manually to prevent global shifting!
        transform.translate(origin_x, origin_y)
        
        if class_id == 31: # Slur
            xywhn = self.sym_data.get("symbol_box_relative_xywh")
            target_w = xywhn[2] * self.scene_w if xywhn else rect.width()
            target_h = xywhn[3] * self.scene_h if xywhn else rect.height()
            scale_x = target_w / rect.width()
            scale_y = target_h / rect.height()
            transform.scale(scale_x, scale_y)
            self.scaled_w, self.scaled_h = target_w, target_h
        else:
            height_multiplier = SYMBOL_HEIGHTS.get(class_id, 3.0)
            fixed_h = self.line_spacing * height_multiplier
            scale_factor = fixed_h / rect.height()
            transform.scale(scale_factor, scale_factor)
            self.scaled_w = rect.width() * scale_factor
            self.scaled_h = fixed_h

        # Apply conditional transforms (rotation, flipping) relative to L3
        is_upper_half = anchor_y <= self.get_y_from_pos("L", 3)
        is_lower_half = anchor_y > self.get_y_from_pos("L", 3)
        
        self.setRotation(0) # Reset base rotation
        
        if class_id in [6, 14, 31]: # Cadence, Fermata, Slur
            if is_lower_half:
                self.setRotation(180)
        elif class_id in [17, 18, 19, 20]: # Stemmed notes
            if is_upper_half:
                self.setRotation(180)
        elif class_id in [15, 16]: # Longa, Maxima
            if is_upper_half:
                transform.scale(1, -1) # Flip vertically mathematically
                
        # Complete the transform origin sandwich
        transform.translate(-origin_x, -origin_y)
        
        self.setTransform(transform)

    def get_y_from_pos(self, p_type, p_num):
        """Retrieves absolute pixel heights from the pre-calculated grid map."""
        # Fallback to the middle line (L3) if position is totally invalid
        return self.grid_map.get((p_type, p_num), self.grid_map[("L", 3)])

    def snap_to_closest_position(self, raw_y, space_only=False, line_only=False, min_line=None, max_line=None):
        """Finds the absolute closest valid music staff height from the grid map."""
        valid_keys = [
            ("S", -1), ("L", 0), ("S", 0), 
            ("L", 1), ("S", 1), ("L", 2), ("S", 2), 
            ("L", 3), ("S", 3), ("L", 4), ("S", 4), 
            ("L", 5), ("S", 5), ("L", 6), ("S", 6)
        ]
        if space_only:
            valid_keys = [k for k in valid_keys if k[0] == "S"]
        elif line_only:
            valid_keys = [k for k in valid_keys if k[0] == "L"]
            if min_line is not None:
                valid_keys = [k for k in valid_keys if k[1] >= min_line]
            if max_line is not None:
                valid_keys = [k for k in valid_keys if k[1] <= max_line]
            
        valid_ys = [self.grid_map[k] for k in valid_keys]
        return min(valid_ys, key=lambda y: abs(y - raw_y))

    def calculate_y(self, raw_y, is_dragging=False):
        """Forces items to their correct theoretical heights."""
        class_id = self.sym_data.get("class_id", 0)
        pos_type = self.sym_data.get("position_type")
        pos_num = self.sym_data.get("position_number")
        
        if class_id == 9: # clef_g ALWAYS locked to L2
            return self.get_y_from_pos("L", 2)
            
        if class_id in [3, 4, 23]: # Barlines
            return self.get_y_from_pos("L", 3)
                
        if class_id in [11, 12, 32, 33]: # Time Signatures
            return self.get_y_from_pos("L", 3)
            
        if class_id == 13: # Dot
            if not is_dragging and pos_type == "S" and pos_num is not None:
                try: return self.get_y_from_pos(pos_type, int(pos_num))
                except ValueError: pass
            return self.snap_to_closest_position(raw_y, space_only=True)
            
        if class_id in [7, 8]: # Clef C and Clef F
            if not is_dragging and pos_type == "L" and pos_num is not None:
                try: 
                    pn = int(pos_num)
                    if class_id == 7: pn = max(1, min(5, pn))
                    if class_id == 8: pn = max(3, min(5, pn))
                    return self.get_y_from_pos("L", pn)
                except ValueError: pass
                
            if class_id == 7:
                return self.snap_to_closest_position(raw_y, line_only=True, min_line=1, max_line=5)
            else:
                return self.snap_to_closest_position(raw_y, line_only=True, min_line=3, max_line=5)
                
        if class_id in [0, 1, 2, 5, 15, 16, 17, 18, 19, 20, 21, 22] or class_id in range(24, 31) or class_id == 34:
            if not is_dragging and pos_type in ["L", "S"] and pos_num is not None:
                try: return self.get_y_from_pos(pos_type, int(pos_num))
                except ValueError: pass
                    
            if not is_dragging and (class_id in range(24, 31) or class_id == 34):
                return self.get_y_from_pos("S", 3) # Force rests to 3rd space by default if no semantic pos
                    
            return self.snap_to_closest_position(raw_y)
                
        if class_id in [6, 14]: # Fermata / Cadence Point
            if raw_y < self.staff_top_y + (self.line_spacing * 2):
                return self.staff_top_y - (self.line_spacing * 2) # Above 1
            else:
                return self.staff_top_y + (self.line_spacing * 6) # Below 1
                
        if class_id == 31: # Slur
            if raw_y < self.staff_top_y + (self.line_spacing * 2):
                return self.staff_top_y - (self.line_spacing * 3) # Above 2
            else:
                return self.staff_top_y + (self.line_spacing * 7) # Below 2
                
        return self.staff_top_y + (self.line_spacing * 2) # Center of staff

    def update_position_data(self, snapped_anchor_y):
        """Reverse-calculates the Semantic position class based on physical Y drop."""
        class_id = self.sym_data.get("class_id", 0)
        
        if class_id == 9: # clef_g ALWAYS locked to L2
            self.sym_data["position_type"] = "L"
            self.sym_data["position_number"] = 2
            return
            
        if class_id in [0, 1, 2, 5, 7, 8, 13, 15, 16, 17, 18, 19, 20, 21, 22, 24, 25, 26, 27, 28, 29, 30, 34]:
            valid_keys = [
                ("S", -1), ("L", 0), ("S", 0), 
                ("L", 1), ("S", 1), ("L", 2), ("S", 2), 
                ("L", 3), ("S", 3), ("L", 4), ("S", 4), 
                ("L", 5), ("S", 5), ("L", 6), ("S", 6)
            ]
            if class_id == 13:
                valid_keys = [k for k in valid_keys if k[0] == "S"]
            elif class_id == 7:
                valid_keys = [k for k in valid_keys if k[0] == "L" and 1 <= k[1] <= 5]
            elif class_id == 8:
                valid_keys = [k for k in valid_keys if k[0] == "L" and 3 <= k[1] <= 5]
                
            for pt, pn in valid_keys:
                # Direct dictionary lookup
                if abs(self.grid_map[(pt, pn)] - snapped_anchor_y) < 1.0:
                    self.sym_data["position_type"] = pt
                    self.sym_data["position_number"] = pn
                    break

    def itemChange(self, change, value):
        """Intercepts dragging to keep movement horizontally free but vertically snapped."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            new_pos = value
            rect = self.boundingRect()
            unscaled_anchor_x = rect.x() + rect.width() / 2
            unscaled_anchor_y = rect.y() + rect.height() * self.anchor_y_ratio
            
            proposed_anchor_y = new_pos.y() + unscaled_anchor_y
            
            snapped_anchor_y = self.calculate_y(proposed_anchor_y, is_dragging=True)
            
            # Trigger rotation and flip updates automatically!
            self.update_visuals(snapped_anchor_y)
            
            new_x_c_norm = (new_pos.x() + unscaled_anchor_x) / self.scene_w
            visual_center_y = self.get_visual_center_y(snapped_anchor_y)
            
            self.sym_data["symbol_box_relative_xywh"][0] = round(new_x_c_norm, 6)
            self.sym_data["symbol_box_relative_xywh"][1] = round(visual_center_y / self.scene_h, 6)
            self.update_position_data(snapped_anchor_y)
            
            return QPointF(new_pos.x(), snapped_anchor_y - unscaled_anchor_y)
            
        return super().itemChange(change, value)
        
    def hoverMoveEvent(self, event):
        if self.sym_data.get("class_id") == 31:
            scene_pos = event.scenePos()
            scene_rect = self.sceneBoundingRect()
            margin = 15.0 # visual pixels on screen margin
            
            if scene_pos.x() <= scene_rect.left() + margin:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                self.resize_edge = 'left'
            elif scene_pos.x() >= scene_rect.right() - margin:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                self.resize_edge = 'right'
            else:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self.resize_edge = None
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        if getattr(self, 'resize_edge', None):
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.resize_edge = None
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
            
        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        if view and getattr(view, 'mode', None) == "delete":
            # Search by object identity to completely bypass dictionary value equality bugs
            idx = next((i for i, sym in enumerate(view.symbols) if sym is self.sym_data), -1)
            if idx != -1:
                view.symbols.pop(idx)
                self.scene().removeItem(self)
                
                view.undo_stack.append({"type": "delete", "index": idx, "symbol": self.sym_data})
                view.undo_state_changed.emit(True)
            event.accept()
            return
            
        # Capture the original state before any movement or resizing begins
        self.undo_pre_state = copy.deepcopy(self.sym_data)
            
        if getattr(self, 'resize_edge', None):
            self.is_resizing = True
            self.resize_start_pos = event.scenePos()
            self.resize_start_xywhn = list(self.sym_data.get("symbol_box_relative_xywh"))
            event.accept() # Consume the click to prevent the default movement drag
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if getattr(self, 'is_resizing', False):
            delta_x = event.scenePos().x() - self.resize_start_pos.x()
            delta_x_norm = delta_x / self.scene_w
            
            xywhn = list(self.resize_start_xywhn)
            
            if self.resize_edge == 'right':
                new_w = max(0.005, xywhn[2] + delta_x_norm)
                new_x = xywhn[0] + (new_w - xywhn[2]) / 2.0
            elif self.resize_edge == 'left':
                new_w = max(0.005, xywhn[2] - delta_x_norm)
                new_x = xywhn[0] - (new_w - xywhn[2]) / 2.0
                
            self.sym_data["symbol_box_relative_xywh"][2] = round(new_w, 6)
            self.sym_data["symbol_box_relative_xywh"][0] = round(new_x, 6)
            
            # Prevent setPos from triggering itemChange tracking while we manually adjust
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, False)
            
            rect = super().boundingRect()
            current_anchor_y = self.y() + rect.y() + rect.height() * self.anchor_y_ratio
            
            self.update_visuals(current_anchor_y)
            
            unscaled_anchor_x = rect.x() + rect.width() / 2
            new_x_pos = (self.sym_data["symbol_box_relative_xywh"][0] * self.scene_w) - unscaled_anchor_x
            self.setPos(new_x_pos, self.y())
            
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        else:
            super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Toggles between Barline/Double and Whole Note/Colored."""
        class_id = self.sym_data.get("class_id", 0)
        new_id = None
        if class_id == 3: new_id = 4
        elif class_id == 4: new_id = 3
        elif class_id == 21: new_id = 22
        elif class_id == 22: new_id = 21
        
        if new_id is not None:
            pre_state = copy.deepcopy(self.sym_data)
            
            old_rect = self.boundingRect()
            current_anchor_x = self.x() + old_rect.x() + old_rect.width() / 2
            current_anchor_y = self.y() + old_rect.y() + old_rect.height() * self.anchor_y_ratio
            
            self.sym_data["class_id"] = new_id
            icon_name = ID_TO_SVG.get(new_id, "note_quarter")
            self.setSharedRenderer(QSvgRenderer(f"icons/symbol_icons/{icon_name}.svg"))
            
            self.setup_anchor()
            new_rect = self.boundingRect()
            self.update_visuals(current_anchor_y)
            
            new_unscaled_anchor_x = new_rect.x() + new_rect.width() / 2
            new_unscaled_anchor_y = new_rect.y() + new_rect.height() * self.anchor_y_ratio
            self.setPos(current_anchor_x - new_unscaled_anchor_x, current_anchor_y - new_unscaled_anchor_y)
            
            visual_center_y = self.get_visual_center_y(current_anchor_y)
            self.sym_data["symbol_box_relative_xywh"][1] = round(visual_center_y / self.scene_h, 6)
            
            for view in self.scene().views():
                if hasattr(view, 'undo_state_changed'):
                    view.undo_stack.append({
                        "type": "edit",
                        "symbol": self.sym_data,
                        "previous_state": pre_state
                    })
                    view.undo_state_changed.emit(True)

    def mouseReleaseEvent(self, event):
        if getattr(self, 'is_resizing', False):
            self.is_resizing = False
            self.resize_edge = None
        else:
            super().mouseReleaseEvent(event)
            
        # If the state actually changed, record it in the undo stack
        if hasattr(self, 'undo_pre_state') and self.undo_pre_state != self.sym_data:
            for view in self.scene().views():
                if hasattr(view, 'undo_state_changed'):
                    view.undo_stack.append({
                        "type": "edit", 
                        "symbol": self.sym_data, 
                        "previous_state": self.undo_pre_state
                    })
                    view.undo_state_changed.emit(True)

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



class SymbolToolButton(QPushButton):
    """A square draggable button for the notation editor toolbar."""
    def __init__(self, icon_filename, parent=None):
        super().__init__(parent)
        self.icon_filename = icon_filename
        self.setFixedSize(55, 65)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setStyleSheet("""
            QPushButton { background-color: white; border-radius: 10px; border: 2px solid #026BBC; }
            QPushButton:hover { background-color: #E6F0FA; }
            QToolTip { 
                color: #888888; 
                background-color: white; 
                border: 1px solid #CCCCCC; 
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.icon_widget = QSvgWidget(f"icons/symbol_icons/{icon_filename}.svg")
        self.icon_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.icon_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.icon_widget.setStyleSheet("background: transparent; border: none;")
        
        if icon_filename == "time_cut":
            self.icon_widget.setFixedSize(20, 49) # -25% width
        elif icon_filename == "clef_g":
            self.icon_widget.setFixedSize(25, 49) # -20% width
        elif icon_filename == "clef_c":
            self.icon_widget.setFixedSize(15, 49) # -20% width
            
        layout.addWidget(self.icon_widget)
        self.setToolTip(icon_filename.replace('_', ' ').title())
        
        self.drag_start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton): return
        if not self.drag_start_pos: return
        if (event.pos() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance(): return
        
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.icon_filename) # Sends the SVG key name to the canvas
        drag.setMimeData(mime_data)
        
        # Extract a visual ghost of the button to drag with the mouse
        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())
        
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)



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
            self.setStyleSheet(f"QFrame {{ background-color: {bg_color}; border-radius: 12px; border: none; }}")
            self.v_label.set_color("#FFFFFF")
            self.icon_widget.hide() # No icon when active
            self.icon_widget.stop_rotation()
            self.setFixedHeight(110) # Decrease height
        else:
            bg_color = "#E6F0FA" if self.is_hovered else "white"
            self.setStyleSheet(f"QFrame {{ background-color: {bg_color}; border-radius: 12px; border: 2px solid #026BBC; }}")
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

        desc = QLabel("You have unsubmitted changes on this staff.\nAre you sure you want to leave?")
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
        self.setFixedSize(460, 580)

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

        title = QLabel("Help & Shortcuts")
        title.setStyleSheet("color: #026BBC; font-size: 26px; font-weight: bold; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        instructions_title = QLabel("How to use:")
        instructions_title.setStyleSheet("color: #333333; font-size: 18px; font-weight: bold; border: none;")
        
        instructions_text = QLabel(
            "• <b>Drag & Drop:</b> Drag symbols from the toolbar to the canvas.<br>"
            "• <b>Move:</b> Drag any symbol on the canvas to snap it to a new line.<br>"
            "• <b>Double-Click:</b> Toggle barlines (single/double) & whole notes (colored).<br>"
            "• <b>Resize Slurs:</b> Hover over the left or right edge of a slur and drag.<br>"
            "• <b>Delete:</b> Enable delete mode (X) and click a symbol to remove it."
        )
        instructions_text.setStyleSheet("color: #262626; font-size: 15px; border: none; background: transparent;")
        instructions_text.setWordWrap(True)

        shortcuts_title = QLabel("Keyboard Shortcuts:")
        shortcuts_title.setStyleSheet("color: #333333; font-size: 18px; font-weight: bold; border: none;")

        shortcuts_layout = QVBoxLayout()
        shortcuts_layout.setSpacing(10)
        
        shortcuts = [
            ("F1", "Open/Close this info"),
            ("Ctrl + Z", "Undo last action"),
            ("X", "Toggle delete mode"),
            ("Ctrl + S", "Submit staff"),
            ("C / V", "Previous / Next staff"),
            ("Shift + C / V", "Previous / Next voice")
        ]
        
        for key, desc in shortcuts:
            lbl = QLabel(f"<span style='color: #026BBC; font-weight: 600;'>{key}</span> <span style='color: #262626;'>- {desc}</span>")
            lbl.setStyleSheet("font-size: 15px; border: none; background: transparent;")
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
        bg_layout.addWidget(instructions_title)
        bg_layout.addSpacing(5)
        bg_layout.addWidget(instructions_text)
        bg_layout.addSpacing(15)
        bg_layout.addWidget(shortcuts_title)
        bg_layout.addSpacing(5)
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
        self.image_tasks = image_tasks # List of tuples: (item_id, image_path)
        self._is_cancelled = False

    def run(self):
        for item_id, img_path in self.image_tasks:
            if self._is_cancelled:
                break
            
            if Path(img_path).exists():
                image = QImage(img_path)
                if not image.isNull():
                    # Scale in the background to save main thread CPU
                    scaled_image = image.scaled(180, 45, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    
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
                    
                    self.thumbnail_loaded.emit(item_id, rounded_image)
                    
    def cancel(self):
        self._is_cancelled = True



class TopImageCanvas(QWidget):
    """A clean, lightweight canvas that only displays the raw staff image reference."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: white; border-radius: 12px; border: 2px solid #026BBC;")
        self.pixmap = None
        self.radius = 12

    def set_image(self, image_path):
        """Loads a new image from the given path."""
        if Path(image_path).exists():
            self.pixmap = QPixmap(image_path)
        else:
            self.pixmap = None
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        
        if not self.pixmap or self.pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        path = QPainterPath()
        path.addRoundedRect(2, 2, self.width() - 4, self.height() - 4, self.radius, self.radius)
        painter.setClipPath(path)

        scaled_pixmap = self.pixmap.scaled(
            self.width() - 4, 
            self.height() - 4, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )

        x = int((self.width() - scaled_pixmap.width()) / 2)
        y = int((self.height() - scaled_pixmap.height()) / 2)

        painter.drawPixmap(x, y, scaled_pixmap)
        
        painter.end()

class NotationEditorCanvas(QGraphicsView):
    """A vector-based canvas that renders dynamic SVGs mapped to relative JSON coordinates."""
    undo_state_changed = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("QGraphicsView { background-color: white; border-radius: 12px; border: 2px solid #026BBC; }")
        self.viewport().setStyleSheet("background: transparent;")
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setAcceptDrops(True) # Enable Drag & Drop
        
        self.symbols = []
        self.undo_stack = []
        self.mode = None 
        
        # Setup a fixed logical scene size. This makes relative X/Y coordinate math effortless!
        self.scene_w = 2000 
        self.scene_h = 300
        self.scene.setSceneRect(0, 0, self.scene_w, self.scene_h)
        
        # Define the exact layout of the 5 staff lines
        self.line_spacing = 40
        self.staff_top_y = (self.scene_h - (4 * self.line_spacing)) / 2

    def set_data(self, symbols):
        self.symbols = copy.deepcopy(symbols) if symbols else []
        self.undo_stack = []
        self.undo_state_changed.emit(False)
        self.update_scene()

    def update_scene(self):
        self.scene.clear()
        
        # 1. Draw the 5 main staff lines
        pen = QPen(QColor("#cccccc"))  # 333333
        pen.setWidth(4)
        
        margin = 20
        for i in range(5):
            y = self.staff_top_y + (i * self.line_spacing)
            self.scene.addLine(margin, y, self.scene_w - margin, y, pen)
            
        # 2. Iterate through self.symbols and place QGraphicsSvgItems!
        for sym in self.symbols:
            if sym.get("class_id") == 10:  # Skip custos as it is not used in score reconstruction
                continue
            item = InteractiveSymbolItem(sym, self.scene_w, self.scene_h, self.staff_top_y, self.line_spacing)
            self.scene.addItem(item)
            
        self.fit_view()
        
    def drawBackground(self, painter, rect):
        """Draws ledger lines on the background canvas independent of the SVG bounds."""
        super().drawBackground(painter, rect)
        
        pen = QPen(QColor("#cccccc"))
        pen.setWidth(4)
        pen.setCosmetic(True)
        painter.setPen(pen)
        
        for item in self.scene.items():
            if isinstance(item, InteractiveSymbolItem):
                class_id = item.sym_data.get("class_id", 0)
                if class_id in [0, 1, 2, 5, 7, 8, 9, 15, 16, 17, 18, 19, 20, 21, 22]:
                    pos_type = item.sym_data.get("position_type")
                    pos_num = item.sym_data.get("position_number")
                    if pos_num is not None:
                        try: pos_num = int(pos_num)
                        except ValueError: continue
                            
                        local_rect = item.boundingRect()
                        local_center_x = local_rect.x() + local_rect.width() / 2
                        scene_x = item.mapToScene(QPointF(local_center_x, 0)).x()
                        
                        if (pos_type == "L" and pos_num >= 6) or (pos_type == "S" and pos_num >= 6):
                            y = item.get_y_from_pos("L", 6)
                            painter.drawLine(QPointF(scene_x - 40, y), QPointF(scene_x + 40, y))
                            
                        if (pos_type == "L" and pos_num <= 0) or (pos_type == "S" and pos_num <= -1):
                            y = item.get_y_from_pos("L", 0)
                            painter.drawLine(QPointF(scene_x - 40, y), QPointF(scene_x + 40, y))
                            
    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text() in SVG_TO_ID:
            event.acceptProposedAction()
            
    def dragMoveEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text() in SVG_TO_ID:
            event.acceptProposedAction()
            
    def dropEvent(self, event):
        icon_filename = event.mimeData().text()
        class_id = SVG_TO_ID.get(icon_filename)
        if class_id is None:
            return
            
        scene_pos = self.mapToScene(event.position().toPoint())
        x_c_norm = max(0.0, min(1.0, scene_pos.x() / self.scene_w))
        y_c_norm = max(0.0, min(1.0, scene_pos.y() / self.scene_h))
        
        new_sym = {
            "class_id": class_id,
            "class_name": icon_filename,
            "class_confidence": 1.0,
            "symbol_box_absolute_xyxy": [0, 0, 0, 0], 
            "symbol_box_relative_xywh": [round(x_c_norm, 6), round(y_c_norm, 6), 0.02, 0.1], # Dummy w/h to initialize
            "position_type": None,
            "position_number": None,
            "position_confidence": 1.0
        }
        
        # Because InteractiveSymbolItem natively reads relative coords and mathematically snaps 
        # itself to the canvas, instantiating it triggers the placement and updating perfectly!
        item = InteractiveSymbolItem(new_sym, self.scene_w, self.scene_h, self.staff_top_y, self.line_spacing)
        
        # Now that we've instantiated it, extract the true width/height the SVG requested from the engine
        new_sym["symbol_box_relative_xywh"][2] = round(item.scaled_w / self.scene_w, 6)
        new_sym["symbol_box_relative_xywh"][3] = round(item.scaled_h / self.scene_h, 6)
        
        self.scene.addItem(item)
        self.symbols.append(new_sym)
        
        self.undo_stack.append({"type": "add", "symbol": new_sym})
        self.undo_state_changed.emit(True)
        
        event.acceptProposedAction()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_view()
        
    def fit_view(self):
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def set_mode(self, mode):
        self.mode = mode
        if self.mode == "delete":
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            
    def undo(self):
        if not self.undo_stack:
            return
            
        action = self.undo_stack.pop()
        action_type = action.get("type")
        
        if action_type == "add":
            sym = action.get("symbol")
            if sym in self.symbols:
                self.symbols.remove(sym)
                for item in self.scene.items():
                    if isinstance(item, InteractiveSymbolItem) and item.sym_data is sym:
                        self.scene.removeItem(item)
                        break
                        
        elif action_type == "delete":
            sym = action.get("symbol")
            idx = action.get("index", len(self.symbols))
            self.symbols.insert(idx, sym)
            item = InteractiveSymbolItem(sym, self.scene_w, self.scene_h, self.staff_top_y, self.line_spacing)
            self.scene.addItem(item)
            
        elif action_type == "edit":
            sym = action.get("symbol")
            prev_state = action.get("previous_state")
            
            # Find the old visual item and remove it
            for item in self.scene.items():
                if isinstance(item, InteractiveSymbolItem) and item.sym_data is sym:
                    self.scene.removeItem(item)
                    break
                    
            # Safely update the dictionary in-place to preserve object identity throughout the stack
            sym.clear()
            sym.update(prev_state)
            
            # Recreate the visual item with restored data
            new_item = InteractiveSymbolItem(sym, self.scene_w, self.scene_h, self.staff_top_y, self.line_spacing)
            self.scene.addItem(new_item)
            
        self.undo_state_changed.emit(len(self.undo_stack) > 0)


class StaffListItem(QFrame):
    clicked = pyqtSignal(int) # Emits staff_id when clicked

    def __init__(self, staff_id, page_id, display_num, num_boxes=0, is_selected=False):
        super().__init__()
        self.staff_id = staff_id
        self.is_selected = is_selected
        self.is_hovered = False
        
        self.setFixedHeight(85)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)
        
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        self.text_label = QLabel(f"Page {page_id}  Staff {display_num}")
        self.text_label.setStyleSheet("font-size: 15px; font-weight: 600; background: transparent; border: none;")

        self.boxes_label = QLabel(str(num_boxes))
        self.boxes_label.setStyleSheet("font-size: 15px; font-weight: 400; background: transparent; border: none;")
        
        top_layout.addWidget(self.text_label)
        top_layout.addStretch()
        top_layout.addWidget(self.boxes_label)
        
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(185, 45)
        self.thumb_label.setStyleSheet("background: transparent; border: none;") 
        
        layout.addLayout(top_layout)
        layout.addWidget(self.thumb_label, alignment=Qt.AlignmentFlag.AlignCenter)

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
            self.setStyleSheet(f"QFrame {{ background-color: {bg_color}; border-radius: 12px; border: none; }}")
            self.text_label.setStyleSheet("color: white; font-size: 15px; font-weight: 600; background: transparent; border: none;")
            self.boxes_label.setStyleSheet("color: white; font-size: 15px; font-weight: 400; background: transparent; border: none;")
        else:
            bg_color = "#E6F0FA" if self.is_hovered else "white"
            self.setStyleSheet(f"QFrame {{ background-color: {bg_color}; border-radius: 12px; border: 2px solid #026BBC; }}")
            self.text_label.setStyleSheet("color: #026BBC; font-size: 15px; font-weight: 600; background: transparent; border: none;")
            self.boxes_label.setStyleSheet("color: #026BBC; font-size: 15px; font-weight: 400; background: transparent; border: none;")


    def mousePressEvent(self, event):
        self.clicked.emit(self.staff_id)
        super().mousePressEvent(event)


# --- MAIN SCREEN ---

class ValidateNotationScreen(QWidget):
    exit_requested = pyqtSignal()
    forward_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: #FAFAFA;")
        
        self.voice_tabs = []

        self.project_data = {} # Maps voice_name to the complete original data dict
        self.voice_folders = {} # Maps voice_name to actual folder name (e.g., Voice_01)
        self.staff_items = []   # Stores the current StaffListItem widgets
        self.flat_staves = []   # Flat list of dictionary references to the staves for easy iteration
        self.staff_page_ids = [] # Stores corresponding page_ids for the flat_staves list

        self.current_staff_index = 0 # Tracks the currently displayed staff
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
        title_label = QLabel("Validate notation")
        title_label.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Forward Button
        self.forward_btn = TopBarButton("Go to score reconstruction", "icons/Forward.svg", "icons/Forward_gray.svg", icon_size=24, icon_pos="right", width=280)
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

        # --- STAVES COLUMN ---
        self.staves_scroll = QScrollArea()
        self.staves_scroll.setFixedWidth(220) # Width matching the mockup
        self.staves_scroll.setWidgetResizable(True)
        self.staves_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.staves_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        
        self.staves_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { border: none; background: transparent; width: 8px; margin: 0px 0px 0px 0px; }
            QScrollBar::handle:vertical { background: #CCCCCC; min-height: 30px; border-radius: 4px; }
            QScrollBar::handle:vertical:hover { background: #AAAAAA; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; background: none; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; } 
        """)

        self.staves_container = QWidget()
        self.staves_container.setStyleSheet("background: transparent;")
        self.staves_layout = QVBoxLayout(self.staves_container)
        self.staves_layout.setContentsMargins(0, 0, 10, 0) # 10px right margin to cleanly shrink items away from scrollbar
        self.staves_layout.setSpacing(10)
        self.staves_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.staves_scroll.setWidget(self.staves_container)
        body_layout.addWidget(self.staves_scroll) 
        # -------------------------

        # --- MAIN CONTENT AREA ---
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
        self.prev_btn.clicked.connect(self.go_to_previous_staff)

        # The Image Canvases 
        self.canvases_container = QWidget()
        self.canvases_layout = QVBoxLayout(self.canvases_container)
        self.canvases_layout.setContentsMargins(0, 0, 0, 0)
        self.canvases_layout.setSpacing(10)

        self.image_canvas = TopImageCanvas()
        self.notation_canvas = NotationEditorCanvas()
        
        self.canvases_layout.addWidget(self.image_canvas, 1)
        self.canvases_layout.addWidget(self.notation_canvas, 1)

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
        self.next_btn.clicked.connect(self.go_to_next_staff)

        # Assemble Top Row
        image_viewer_layout.addWidget(self.prev_btn)
        image_viewer_layout.addWidget(self.canvases_container, 1) # Canvas stretches
        image_viewer_layout.addWidget(self.next_btn)

        # ==========================================
        # --- MIDDLE ROW: Symbol Toolbar ---
        # ==========================================
        self.symbol_toolbar_container = QWidget()
        toolbar_layout = QVBoxLayout(self.symbol_toolbar_container)
        toolbar_layout.setContentsMargins(0, 5, 0, 5)
        toolbar_layout.setSpacing(8)
        
        top_row_layout = QHBoxLayout()
        top_row_layout.setSpacing(6)
        top_row_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        bottom_row_layout = QHBoxLayout()
        bottom_row_layout.setSpacing(6)
        bottom_row_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        top_icons = [
            "clef_c", "clef_f", "clef_g", "time_c", "time_cut", "time_2", "time_3",
            "barline", "repeat", "slur", "cadence_point", "fermata", "dot", "flat", "sharp", "natural"
        ]
        bottom_icons = [
            "note_maxima", "note_longa", "note_breve", "note_whole", "note_half", "note_quarter", 
            "note_eighth", "note_16th", "rest_maxima", "rest_longa", "rest_breve", "rest_whole", 
            "rest_half", "rest_quarter", "rest_eighth", "rest_16th"
        ]
        
        for icon in top_icons:
            btn = SymbolToolButton(icon)
            top_row_layout.addWidget(btn)
            
        for icon in bottom_icons:
            btn = SymbolToolButton(icon)
            bottom_row_layout.addWidget(btn)
            
        toolbar_layout.addLayout(top_row_layout)
        toolbar_layout.addLayout(bottom_row_layout)

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
        self.notation_canvas.undo_state_changed.connect(self.undo_btn.setEnabled)

        # 3. Delete Toggle Button
        self.delete_btn = ToggleActionButton("Delete")
        self.delete_btn.clicked.connect(self.on_delete_clicked)

        # 4. Submit Page Button
        self.submit_btn = QPushButton("Submit staff")
        self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_btn.setFixedHeight(50)
        self.submit_btn.setEnabled(False) # Inactive by default until changes are made
        self.submit_btn.setStyleSheet("""
            QPushButton { background-color: #026BBC; color: white; font-size: 20px; font-weight: bold; border-radius: 12px; border: none; }
            QPushButton:hover:!disabled { background-color: #005BB5; }
            QPushButton:disabled { background-color: #CCCCCC; color: #888888; }
        """)
        self.submit_btn.clicked.connect(self.on_submit_clicked)
        
        self.notation_canvas.undo_state_changed.connect(self.submit_btn.setEnabled)

        # Assemble Bottom Row
        action_buttons_layout.addWidget(self.info_btn)
        action_buttons_layout.addWidget(self.undo_btn, 1) # Stretch evenly
        action_buttons_layout.addWidget(self.delete_btn, 1) # Stretch evenly
        action_buttons_layout.addWidget(self.submit_btn, 1) # Stretch evenly

        # ==========================================
        # --- ASSEMBLE MAIN CONTENT AREA ---
        # ==========================================
        main_content_layout.addWidget(image_viewer_container, 1) # Viewer gets vertical expansion
        main_content_layout.addWidget(self.symbol_toolbar_container) 
        main_content_layout.addWidget(action_buttons_container)  # Buttons stay fixed at the bottom

        body_layout.addWidget(self.main_content_area, 1) 
        main_layout.addLayout(body_layout, 1)

        # --- Keyboard Shortcuts ---
        QShortcut(QKeySequence("F1"), self).activated.connect(self.info_btn.click)
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.undo_btn.click)
        QShortcut(QKeySequence("X"), self).activated.connect(self.delete_btn.click)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.submit_btn.click)
        QShortcut(QKeySequence("C"), self).activated.connect(self.go_to_previous_staff)
        QShortcut(QKeySequence("V"), self).activated.connect(self.go_to_next_staff)
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
                self.notation_canvas.undo_stack.clear()
                self.notation_canvas.undo_state_changed.emit(False)
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
            
        dialog = ProceedDialog(self, "score reconstruction")
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
            is_done = (pred_status.get("position_classification") == 1 and pred_status.get("notes_prediction") == 1) or has_error
            
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
                                    for staff in page.get("staves", []):
                                        if "staff_image_path" in staff:
                                            root_dir = Path(__file__).parent.parent
                                            full_path = root_dir / staff["staff_image_path"]
                                            staff["absolute_image_path"] = str(full_path.resolve())
                                self.project_data[v_name] = data
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
            
        # Automatically select the first voice and load its staves
        if voices_info:
            self.voice_tabs[0].set_state("selected")
            self.populate_staves_list(voices_info[0]["name"])

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
        self.populate_staves_list(clicked_voice_name)
    
    def populate_staves_list(self, voice_name):
        """Builds the list of staves for the selected voice."""

        self.current_voice = voice_name
        self.current_staff_index = 0 # Reset to first staff when changing voice

        # 1. Safely cancel any currently running thumbnail load if the user clicks fast
        if self.thumbnail_thread and self.thumbnail_thread.isRunning():
            self.thumbnail_thread.cancel()
            self.thumbnail_thread.wait()
            
        # 2. Clear old items
        for i in reversed(range(self.staves_layout.count())): 
            widget = self.staves_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self.staff_items.clear()
        self.flat_staves.clear()
        self.staff_page_ids.clear()

        # Gather all staves from the raw tree into a flat iterable list
        for page in self.project_data[voice_name].get("pages", []):
            page_id = page.get("page_id", "?")
            for staff in page.get("staves", []):
                self.flat_staves.append(staff)
                self.staff_page_ids.append(page_id)

        load_tasks = []
        
        for i, staff in enumerate(self.flat_staves):
            staff_id = i
            p_id = self.staff_page_ids[i]
            display_num = staff.get("staff_number", i) + 1 # +1 for human reading index
            img_path = staff.get("absolute_image_path", "")
            load_tasks.append((staff_id, img_path))
            
            # Create the list item instantly without loading the image yet
            num_boxes = len(staff.get("symbols", []))
            item = StaffListItem(staff_id, p_id, display_num, num_boxes=num_boxes, is_selected=(i == 0)) 
            item.clicked.connect(self.on_staff_item_clicked)
            self.staves_layout.addWidget(item)
            self.staff_items.append(item)

            
        # 3. Start the background thread to load all the images
        self.thumbnail_thread = ThumbnailLoaderWorker(load_tasks)
        self.thumbnail_thread.thumbnail_loaded.connect(self.on_thumbnail_loaded)
        self.thumbnail_thread.start()
        self.update_canvas_and_controls() # Draw the first page
        
    def on_thumbnail_loaded(self, staff_id, qimage):
        """Slot that catches the signal from the worker and updates the specific UI element."""
        for item in self.staff_items:
            if item.staff_id == staff_id:
                item.set_thumbnail(qimage)
                break
    
    def on_staff_item_clicked(self, clicked_staff_id):
        """Handles click events on a staff thumbnail."""
        if clicked_staff_id != self.current_staff_index:
            if not self.check_unsaved_changes():
                return
            self.current_staff_index = clicked_staff_id
            self.update_canvas_and_controls()

    def update_canvas_and_controls(self):
        """Updates the image shown and enables/disables navigation buttons."""
        if not self.flat_staves:
            self.image_canvas.set_image("")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return

        # Load the current staff image
        current_staff = self.flat_staves[self.current_staff_index]
        symbols_data = current_staff.get("symbols", [])
        self.image_canvas.set_image(current_staff.get("absolute_image_path", ""))
        self.notation_canvas.set_data(symbols_data)

        # Update button states
        self.prev_btn.setEnabled(self.current_staff_index > 0)
        self.next_btn.setEnabled(self.current_staff_index < len(self.flat_staves) - 1)

        # Highlight the correct thumbnail in the list
        for item in self.staff_items:
            is_active = (item.staff_id == self.current_staff_index)
            item.set_selected(is_active)
            if is_active:
                # Smoothly scrolls the list just enough to keep the active item visible (with a 10px margin)
                self.staves_scroll.ensureWidgetVisible(item, 0, 10)
                self.staves_scroll.horizontalScrollBar().setValue(0) # Force X-axis to stay perfectly flush

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

    def go_to_previous_staff(self):
        """Action for the Previous button or 'C' hotkey."""
        if self.current_staff_index > 0:
            if not self.check_unsaved_changes():
                return
            self.current_staff_index -= 1
            self.update_canvas_and_controls()

    def go_to_next_staff(self):
        """Action for the Next button or 'V' hotkey."""
        if self.current_staff_index < len(self.flat_staves) - 1:
            if not self.check_unsaved_changes():
                return
            self.current_staff_index += 1
            self.update_canvas_and_controls()

    def on_delete_clicked(self):
        """Toggle Delete mode on/off, ensuring Draw mode turns off."""
        new_state = not self.delete_btn.is_selected
        self.delete_btn.set_selected(new_state)
        if new_state:
            self.notation_canvas.set_mode("delete")
        else:
            self.notation_canvas.set_mode(None)

    def on_undo_clicked(self):
        """Triggers the canvas to undo the last action."""
        self.notation_canvas.undo()

    def on_submit_clicked(self):
        """Saves current symbol boxes to JSON mathematically converting them to absolute coordinates."""
        if not self.current_voice or not self.project_path:
            return
            
        if not self.flat_staves:
            return
            
        current_staff = self.flat_staves[self.current_staff_index]
        
        # Get current symbols and sort them left-to-right (X), then top-to-bottom (Y)
        updated_symbols = self.notation_canvas.symbols
        updated_symbols.sort(key=lambda s: (s.get("symbol_box_relative_xywh", [0, 0, 0, 0])[0], 
                                            s.get("symbol_box_relative_xywh", [0, 0, 0, 0])[1]))
        
        # Calculate Absolute Coordinates based on Original Image Dimensions
        img_path = current_staff.get("absolute_image_path", "")
        img_w, img_h = 0, 0
        if Path(img_path).exists():
            img = QImage(img_path)
            img_w, img_h = img.width(), img.height()
            
        ordered_symbols = []
        for idx, sym in enumerate(updated_symbols):
            xywhn = sym.get("symbol_box_relative_xywh")
            xywhn_rounded = [round(val, 6) for val in xywhn] if xywhn else [0, 0, 0, 0]
            
            abs_xyxy = sym.get("symbol_box_absolute_xyxy", [0, 0, 0, 0])
            if xywhn and len(xywhn) == 4 and img_w > 0 and img_h > 0:
                x_c, y_c, w_n, h_n = xywhn
                x1 = (x_c - w_n / 2) * img_w
                y1 = (y_c - h_n / 2) * img_h
                x2 = (x_c + w_n / 2) * img_w
                y2 = (y_c + h_n / 2) * img_h
                abs_xyxy = [round(x1), round(y1), round(x2), round(y2)]
                
            # Deepcopy to gracefully preserve any internal YOLO meta keys
            new_sym = copy.deepcopy(sym)
            new_sym.update({
                "symbol_number": idx,
                "class_id": sym.get("class_id", 0),
                "class_name": sym.get("class_name", "unknown"),
                "class_confidence": sym.get("class_confidence", 1.0),
                "symbol_box_absolute_xyxy": abs_xyxy,
                "symbol_box_relative_xywh": xywhn_rounded,
                "position_type": sym.get("position_type", None),
                "position_number": sym.get("position_number", None),
                "position_confidence": sym.get("position_confidence", None)
            })
            ordered_symbols.append(new_sym)
            
        # Update in-memory data! Because we hold references to the real dictionaries, 
        # editing this updates self.project_data organically.
        current_staff["symbols"] = ordered_symbols
        self.notation_canvas.symbols = ordered_symbols
        
        for item in self.staff_items:
            if item.staff_id == self.current_staff_index:
                item.update_boxes_count(len(ordered_symbols))
                break
                
        # Now safely write to the JSON file
        folder_name = self.voice_folders.get(self.current_voice, self.current_voice)
        json_file = Path(self.project_path) / folder_name / f"{folder_name}_data.json"
        if json_file.exists():
            try:
                # Clean out the temporary UI absolute paths so we don't bloat the JSON on disk
                data_to_save = copy.deepcopy(self.project_data[self.current_voice])
                for page in data_to_save.get("pages", []):
                    for staff in page.get("staves", []):
                        staff.pop("absolute_image_path", None)
                        
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(data_to_save, f, indent=4)
                    
                # --- RESET DOWNSTREAM PIPELINE STATE ---
                state_file = Path(self.project_path) / "project_state.json"
                if state_file.exists():
                    with open(state_file, "r", encoding="utf-8") as sf:
                        state_data = json.load(sf)
                        
                    if folder_name in state_data.get("voices", {}):
                        s_recon = state_data["voices"][folder_name]["score_reconstruction"]
                        s_recon["agnostic_to_partially_semantic"] = 0
                        s_recon["partially_semantic_to_semantic"] = 0
                        s_recon["one_voice_musicxml_saved"] = 0
                        
                        state_data["global_state"]["measure_synchronization_finished"] = 0
                        state_data["global_state"]["combined_musicxml_saved"] = 0
                        state_data["global_state"]["measure_duration_validation_finished"] = 0
                        
                    with open(state_file, "w", encoding="utf-8") as sf:
                        json.dump(state_data, sf, indent=4)
                        
                self.toast.show_custom_message("Symbol bounding boxes updated")
                
                # Clear undo stack so buttons disable again until new changes are made
                self.notation_canvas.undo_stack.clear()
                self.notation_canvas.undo_state_changed.emit(False)
            except Exception as e:
                self.toast.show_custom_message(f"Error saving: {e}")
        else:
            self.toast.show_custom_message("Error: JSON file not found!")


# --- TESTING BLOCK (Contains all hardcoded paths for standalone testing) ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ValidateNotationScreen()
    window.resize(1280, 720)
    
    # Define the path ONLY for testing this screen
    test_path = Path("C:/Files/Programming_projects/nanoScore/Projects/SEMIAUTOMATIC_test_notation_9 - Copy")
    
    window.project_path = str(test_path)
    voices_info = []
    
    # Custom testing loader to entirely bypass background polling & project_state.json
    if test_path.exists():
        for voice_dir in sorted(test_path.glob("Voice_*")):
            if voice_dir.is_dir():
                json_file = voice_dir / f"{voice_dir.name}_data.json"
                if json_file.exists():
                    try:
                        with open(json_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            
                        v_name = data.get("voice", voice_dir.name)
                        
                        for page in data.get("pages", []):
                            for staff in page.get("staves", []):
                                if "staff_image_path" in staff:
                                    full_path = Path(__file__).parent.parent / staff["staff_image_path"]
                                    staff["absolute_image_path"] = str(full_path.resolve())
                                    
                        window.project_data[v_name] = data
                        window.voice_folders[v_name] = voice_dir.name
                        voices_info.append({"name": v_name, "state": "finished"})
                    except Exception as e:
                        print(f"Error loading {json_file}: {e}")
                        
    if voices_info:
        voices_info[0]["state"] = "selected"
        window.populate_voice_tabs(voices_info)
    else:
        print(f"Path {test_path} not found or empty. Using dummy data.")
        dummy_info = [
            {"name": "Dessus", "state": "selected"},
            {"name": "Haute-contre", "state": "finished"},
            {"name": "Taille", "state": "finished"},
            {"name": "Basse", "state": "finished"}
        ]
        window.populate_voice_tabs(dummy_info)

    window.show()
    sys.exit(app.exec())