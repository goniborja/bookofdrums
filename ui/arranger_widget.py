from __future__ import annotations

"""ui/arranger_widget.py

ArrangerWidget (Canvas) for Book of Drums.

Features:
- QGraphicsView canvas (uses QOpenGLWidget when available)
- Drag & drop from sidebar: mimeData.text() == pattern_id
- Ctrl + MouseWheel zoom
- Delete/Backspace removes selected clips
- Snap grid: Bar / 1/2 / 1/4 / 1/8 / 1/16

Step 10 update (UX):
- Clips display the human pattern name (from RhythmEngine/DatabaseManager if available)
- Clip width auto-expands to pattern bars if engine patterns contain >16 steps
"""

from dataclasses import dataclass
from typing import Optional, List, Any

from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QBrush
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsObject, QWidget

try:
    from PyQt6.QtOpenGLWidgets import QOpenGLWidget
    _HAS_GL = True
except Exception:
    _HAS_GL = False


# ----------------------------
# Data Models
# ----------------------------

@dataclass(frozen=True)
class ClipRef:
    pattern_id: str
    name_human: str = ""
    bars: int = 1


@dataclass(frozen=True)
class ClipPlacement:
    pattern_id: str
    start_step: int  # 1 step = 1/16 bar
    bars: int = 1

    @property
    def start_bar(self) -> int:
        return max(0, int(self.start_step) // 16)


# ----------------------------
# Clip Item
# ----------------------------

class PatternClipItem(QGraphicsObject):
    moved = pyqtSignal()

    def __init__(self, clip: ClipRef, bar_width_px: float, height_px: float = 64.0):
        super().__init__()
        self.clip = clip
        self._bar_width_px = float(bar_width_px)
        self._height_px = float(height_px)

        # step = 1/16 bar
        self._step_width_px = self._bar_width_px / 16.0 if self._bar_width_px > 0 else 1.0
        self._snap_interval_px = self._bar_width_px  # default: bar snap

        self.setFlags(
            self.GraphicsItemFlag.ItemIsMovable
            | self.GraphicsItemFlag.ItemIsSelectable
            | self.GraphicsItemFlag.ItemSendsGeometryChanges
        )

        # cache for smoother dragging
        self.setCacheMode(QGraphicsObject.CacheMode.DeviceCoordinateCache)

        self._font_header = QFont("Segoe UI", 9)
        self._font_body = QFont("Segoe UI", 8)

        # Tooltip (UX)
        title = (self.clip.name_human or "Pattern").strip()
        self.setToolTip(f"{title}\nID: {self.clip.pattern_id}\nBars: {self.clip.bars}")

    # --- Snap control (called by ArrangerWidget)

    def set_snap_divisor(self, divisor: int) -> None:
        """divisor: 1(bar),2(half),4,8,16"""
        try:
            div = max(1, min(16, int(divisor)))
        except Exception:
            div = 1
        self._snap_interval_px = self._bar_width_px / float(div)

    # --- QGraphicsObject API

    def boundingRect(self) -> QRectF:
        w = max(1, int(self.clip.bars)) * self._bar_width_px
        return QRectF(0, 0, w, self._height_px)

    def _color_by_name(self) -> tuple[QColor, QColor, QColor, QColor]:
        """Returns: base, border, header, text."""
        name = (self.clip.name_human or self.clip.pattern_id or "").lower()

        base = QColor("#2a2318")
        border = QColor("#4a3f30")
        header = QColor("#c9a227")
        text = QColor("#e8e0d0")

        # Style heuristics
        if "intro" in name:
            base = QColor("#1f2a1c")
            header = QColor("#7fb069")
        elif "outro" in name or "ending" in name:
            base = QColor("#1c1f2a")
            header = QColor("#6f86d6")
        elif "fill" in name or "break" in name:
            base = QColor("#2a1c1c")
            header = QColor("#d66f6f")
        elif "chorus" in name:
            base = QColor("#2a2318")
            header = QColor("#c9a227")

        if self.isSelected():
            border = QColor("#ffffff")

        return base, border, header, text

    def paint(self, painter: QPainter, option, widget: Optional[QWidget] = None) -> None:
        r = self.boundingRect()
        base, border, header, text = self._color_by_name()

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Background
        painter.setPen(QPen(border, 1.2))
        painter.setBrush(QBrush(base))
        painter.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)

        # Header band
        header_h = 18.0
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(header))
        painter.drawRoundedRect(QRectF(r.x(), r.y(), r.width(), header_h), 6, 6)

        # Header text (pattern name)
        painter.setFont(self._font_header)
        painter.setPen(QPen(QColor("#000000")))

        title = (self.clip.name_human or "Pattern").strip()
        if len(title) > 28:
            title = title[:27] + "…"

        painter.drawText(
            QRectF(8, 1, r.width() - 16, header_h - 2),
            Qt.AlignmentFlag.AlignVCenter,
            title,
        )

        # Body (pattern id + bars)
        painter.setFont(self._font_body)
        painter.setPen(QPen(text))
        body_txt = f"{self.clip.pattern_id}\n{self.clip.bars} bar(s)"
        painter.drawText(
            QRectF(8, header_h + 4, r.width() - 16, r.height() - header_h - 8),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            body_txt,
        )

    def itemChange(self, change, value):
        if change == self.GraphicsItemChange.ItemPositionChange:
            pos: QPointF = value
            x = max(0.0, float(pos.x()))
            y = 0.0

            # snap
            snap = float(self._snap_interval_px) if self._snap_interval_px > 0 else self._bar_width_px
            if snap > 0:
                x = round(x / snap) * snap

            # clamp to step grid (avoid rounding drift)
            if self._step_width_px > 0:
                x = round(x / self._step_width_px) * self._step_width_px

            return QPointF(float(x), float(y))

        if change == self.GraphicsItemChange.ItemPositionHasChanged:
            self.moved.emit()

        return super().itemChange(change, value)


# ----------------------------
# Arranger Widget
# ----------------------------

class ArrangerWidget(QGraphicsView):
    arrangementChanged = pyqtSignal()

    def __init__(self, parent_app=None, engine=None):
        super().__init__()
        self.parent_app = parent_app
        self.engine = engine

        self._bar_width_px = 220.0
        self._height_px = 72.0
        self._max_bars = 128

        # Snap divisor: 1(bar),2,4,8,16
        self._snap_divisor = 1

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        if _HAS_GL:
            try:
                self.setViewport(QOpenGLWidget())
            except Exception:
                pass

        self.setAcceptDrops(True)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        self.setBackgroundBrush(QBrush(QColor("#050505")))

        self._zoom = 1.0
        self._clips: List[PatternClipItem] = []

        self._rebuild_scene_rect()

    # ---- scene sizing

    def _rebuild_scene_rect(self) -> None:
        w = self._bar_width_px * self._max_bars
        self._scene.setSceneRect(0, 0, w, self._height_px)

    def _ensure_scene_width(self) -> None:
        if not self._clips:
            return
        last = max(self._clips, key=lambda it: it.pos().x() + it.boundingRect().width())
        needed = last.pos().x() + last.boundingRect().width() + self._bar_width_px * 8
        r = self._scene.sceneRect()
        if needed > r.width():
            self._scene.setSceneRect(0, 0, needed, r.height())

    # ---- engine helpers

    def _resolve_pattern_name_and_bars(self, pattern_id: str, fallback_bars: int) -> tuple[str, int]:
        """Tries to resolve name_human and bars from engine/db."""
        name_human = ""
        bars = max(1, int(fallback_bars))

        blk = None
        if self.engine is not None:
            try:
                blk = self.engine.get_pattern(pattern_id)
            except Exception:
                blk = None

        if blk is not None:
            # name
            name_human = getattr(blk, "name_human", "") or getattr(blk, "name", "") or ""

            # bars heuristic:
            # - explicit bars/compases if present
            for key in ("bars", "compases", "compases_total", "num_bars"):
                v = getattr(blk, key, None)
                if isinstance(v, (int, float)) and int(v) > 0:
                    bars = max(1, int(v))
                    break

            # - infer from step length if tracks are longer than 16
            try:
                max_len = 0
                for steps in (blk.tracks or {}).values():
                    max_len = max(max_len, len(steps) if steps else 0)
                if max_len > 16:
                    bars = max(bars, (max_len + 15) // 16)
            except Exception:
                pass

        name_human = (name_human or "").strip()
        return name_human, max(1, int(bars))

    # ---- snap API

    def set_snap_divisor(self, divisor: int) -> None:
        """Set snap grid. divisor: 1(bar),2(half),4,8,16."""
        try:
            div = max(1, min(16, int(divisor)))
        except Exception:
            div = 1
        self._snap_divisor = div
        for it in self._clips:
            it.set_snap_divisor(div)

        # Re-snap current selection to avoid half-grid drift
        for it in self._clips:
            it.setPos(it.pos())

    def get_snap_divisor(self) -> int:
        return int(self._snap_divisor)

    # ---- public API

    def add_clip(
        self,
        pattern_id: str,
        at_bar: Optional[int] = None,
        bars: int = 1,
        at_step: Optional[int] = None
    ) -> None:
        pid = (pattern_id or "").strip()
        if not pid:
            return

        # Validate against engine patterns
        if self.engine is not None:
            try:
                if not self.engine.get_pattern(pid):
                    return
            except Exception:
                pass

        # Resolve UX name + auto bars
        name_human, auto_bars = self._resolve_pattern_name_and_bars(pid, bars)
        clip = ClipRef(pattern_id=pid, name_human=name_human, bars=max(1, int(auto_bars)))

        item = PatternClipItem(clip, bar_width_px=self._bar_width_px, height_px=self._height_px)
        item.set_snap_divisor(self._snap_divisor)
        item.moved.connect(self.arrangementChanged.emit)

        if at_step is not None:
            step_w = self._bar_width_px / 16.0
            x = step_w * max(0, int(at_step))
        elif at_bar is None:
            x = self._bar_width_px * len(self._clips)
        else:
            x = self._bar_width_px * max(0, int(at_bar))

        item.setPos(QPointF(float(x), 0.0))

        self._scene.addItem(item)
        self._clips.append(item)

        self._ensure_scene_width()
        self.arrangementChanged.emit()

    def clear_all(self) -> None:
        self._scene.clear()
        self._clips.clear()
        self._rebuild_scene_rect()
        self.arrangementChanged.emit()

    def get_arrangement(self) -> List[str]:
        """Legacy: returns only pattern IDs ordered by X."""
        items = sorted(self._clips, key=lambda it: it.pos().x())
        return [it.clip.pattern_id for it in items]

    def get_arrangement_placements(self) -> List[ClipPlacement]:
        """Return placements with start_step (16th steps) ordered by position."""
        items = sorted(self._clips, key=lambda it: it.pos().x())
        step_w = self._bar_width_px / 16.0 if self._bar_width_px > 0 else 1.0

        out: List[ClipPlacement] = []
        for it in items:
            start_step = int(round(it.pos().x() / step_w)) if step_w > 0 else 0
            out.append(ClipPlacement(it.clip.pattern_id, max(0, start_step), max(1, int(it.clip.bars))))
        return out

    def set_arrangement_placements(self, placements: List[ClipPlacement] | List[dict]) -> None:
        """Restore from placements.

        Accepts dicts with:
          - pattern_id
          - start_step (preferred) OR start_bar
          - bars
        """
        self.clear_all()
        if not placements:
            return

        for pl in placements:
            try:
                if isinstance(pl, dict):
                    pid = str(pl.get("pattern_id", "")).strip()
                    bars = int(pl.get("bars", 1) or 1)
                    if "start_step" in pl:
                        start_step = int(pl.get("start_step", 0) or 0)
                    else:
                        start_bar = int(pl.get("start_bar", 0) or 0)
                        start_step = start_bar * 16
                else:
                    pid = str(getattr(pl, "pattern_id")).strip()
                    bars = int(getattr(pl, "bars", 1) or 1)
                    if hasattr(pl, "start_step"):
                        start_step = int(getattr(pl, "start_step"))
                    else:
                        start_step = int(getattr(pl, "start_bar")) * 16
            except Exception:
                continue

            if pid:
                self.add_clip(pid, at_step=max(0, start_step), bars=max(1, bars))

        self.arrangementChanged.emit()

    # ---- background grid

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawBackground(painter, rect)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        major = QPen(QColor("#2a2a2a"), 1)  # bar lines
        minor = QPen(QColor("#1a1a1a"), 1)  # beat lines

        left = rect.left()
        right = rect.right()

        bar_w = self._bar_width_px
        step_w = self._bar_width_px / 16.0

        start_bar = int(left // bar_w)
        end_bar = int(right // bar_w) + 2

        for b in range(start_bar, end_bar):
            x = b * bar_w
            painter.setPen(major)
            painter.drawLine(int(x), 0, int(x), int(self._height_px))

            painter.setPen(minor)
            for beat in (4, 8, 12):
                xb = x + beat * step_w
                painter.drawLine(int(xb), 0, int(xb), int(self._height_px))

    # ---- events

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.15 if delta > 0 else 1 / 1.15
            self._zoom = max(0.6, min(2.5, self._zoom * factor))
            self.resetTransform()
            self.scale(self._zoom, 1.0)
            event.accept()
            return
        super().wheelEvent(event)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasText():
            event.ignore()
            return
        pid = event.mimeData().text().strip()
        if not pid:
            event.ignore()
            return

        # Place at cursor position
        p = self.mapToScene(event.position().toPoint())
        x = max(0.0, float(p.x()))

        step_w = self._bar_width_px / 16.0
        start_step = int(round(x / step_w)) if step_w > 0 else 0

        self.add_clip(pid, at_step=start_step)
        event.acceptProposedAction()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            selected = [it for it in self._clips if it.isSelected()]
            if selected:
                for it in selected:
                    try:
                        self._scene.removeItem(it)
                    except Exception:
                        pass
                    try:
                        self._clips.remove(it)
                    except Exception:
                        pass
                self.arrangementChanged.emit()
                return
        super().keyPressEvent(event)
