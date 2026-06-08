"""
Background preview renderer and zoomable DXF preview widget.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QObject, QRectF, QThread, QTimer, Signal
from PySide6.QtGui import QPixmap, QWheelEvent
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from i18n import tr

# ---------------------------------------------------------------------------
# Optional heavy dependencies – imported once at module load so every
# subsequent preview render avoids the import-lookup overhead.
# ---------------------------------------------------------------------------
try:
    import io as _io
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    _RENDER_AVAILABLE = True
except ImportError:
    _RENDER_AVAILABLE = False


# ---------------------------------------------------------------------------
# Background preview renderer
# ---------------------------------------------------------------------------

class PreviewWorker(QObject):
    """Renders a DXF template to PNG bytes in a background thread.

    Emits ``finished(template_name, png_bytes, dpi_factor, generation)`` when done.
    An empty bytes value signals failure or cancellation.
    """

    # extra four floats carry the matplotlib axis bounds in DXF coordinates:
    # x_min, x_max, y_min, y_max  (all 0.0 on failure)
    finished = Signal(str, bytes, float, int, float, float, float, float)

    def __init__(self, template_name: str, template_mgr, dpi_factor: float = 1.0, generation: int = 0):
        super().__init__()
        self._name = template_name
        self._mgr = template_mgr
        self._dpi_factor = dpi_factor
        self._generation = generation
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        if self._cancelled:
            return
        if not _RENDER_AVAILABLE:
            self.finished.emit(self._name, b"", self._dpi_factor, self._generation, 0.0, 1.0, 0.0, 1.0)
            return
        try:
            dpi = min(384, max(96, int(96 * self._dpi_factor)))

            # --- PNG cache hit: skip the full matplotlib render ---
            cached = self._mgr.get_png_cache(self._name, dpi)
            if cached is not None and not self._cancelled:
                png_bytes, x_min, x_max, y_min, y_max = cached
                self.finished.emit(self._name, png_bytes, self._dpi_factor, self._generation,
                                   x_min, x_max, y_min, y_max)
                return

            doc = self._mgr.load_template(self._name)
            if doc is None or self._cancelled:
                self.finished.emit(self._name, b"", self._dpi_factor, self._generation, 0.0, 1.0, 0.0, 1.0)
                return

            fig = Figure(figsize=(5, 3.5), facecolor="white")
            FigureCanvasAgg(fig)
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_axis_off()
            ctx = RenderContext(doc)
            backend = MatplotlibBackend(ax)
            Frontend(ctx, backend).draw_layout(doc.modelspace(), finalize=True)

            # ezdxf auto-sets axis limits from geometric entities, but
            # attribute-only blocks (WD_WNH, WD_M, etc.) contain no geometry
            # so matplotlib never expands the limits to include them.
            # Expand xlim/ylim to cover every INSERT position so that all
            # blocks are visible and zoom-to-block works correctly.
            x_min, x_max = ax.get_xlim()
            y_min, y_max = ax.get_ylim()
            for ent in doc.modelspace():
                if ent.dxftype() == "INSERT":
                    pt = ent.dxf.get("insert", None)
                    if pt is not None:
                        x_min = min(x_min, float(pt.x))
                        x_max = max(x_max, float(pt.x))
                        y_min = min(y_min, float(pt.y))
                        y_max = max(y_max, float(pt.y))
            # Add a small padding (3 % of the larger span) so insert points
            # are not clipped right at the edge.
            pad = max(x_max - x_min, y_max - y_min) * 0.03
            ax.set_xlim(x_min - pad, x_max + pad)
            ax.set_ylim(y_min - pad, y_max + pad)
            x_min, x_max = ax.get_xlim()
            y_min, y_max = ax.get_ylim()

            if self._cancelled:
                return

            buf = _io.BytesIO()
            fig.savefig(buf, format="png", dpi=dpi, facecolor="white")
            buf.seek(0)
            png_bytes = buf.read()

            # Store in cache so zoom re-renders at the same DPI are instant.
            self._mgr.set_png_cache(self._name, dpi, png_bytes, x_min, x_max, y_min, y_max)

            self.finished.emit(self._name, png_bytes, self._dpi_factor, self._generation,
                               x_min, x_max, y_min, y_max)
        except Exception as exc:
            import traceback
            print(f"[preview] render failed for {self._name!r}: {exc}")
            traceback.print_exc()
            self.finished.emit(self._name, b"", self._dpi_factor, self._generation, 0.0, 1.0, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Zoomable DXF preview widget
# ---------------------------------------------------------------------------

class ZoomablePreview(QGraphicsView):
    """QGraphicsView with mouse-wheel zoom and drag-to-pan."""

    _ZOOM_FACTOR = 1.25
    _MIN_ZOOM = 0.05
    _MAX_ZOOM = 50.0

    zoom_changed = Signal(float)   # emitted after wheel stops (debounced)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = None
        self._zoom_level = 1.0
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setStyleSheet("background-color: white; border: 1px solid lightgray;")
        self.setMinimumHeight(180)

        # Debounce zoom so we only re-render after the user pauses
        self._zoom_timer = QTimer(self)
        self._zoom_timer.setSingleShot(True)
        self._zoom_timer.setInterval(350)
        self._zoom_timer.timeout.connect(lambda: self.zoom_changed.emit(self._zoom_level))

    # -- public helpers -------------------------------------------------------

    def set_pixmap(self, pixmap: QPixmap):
        self._scene.clear()
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self.resetTransform()
        self._zoom_level = 1.0
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def update_pixmap_at_scale(self, pixmap: QPixmap, dpi_factor: float):
        """Replace the pixmap (rendered at dpi_factor × base DPI) while
        preserving the current visual zoom level.

        Because the new pixmap is dpi_factor times larger in pixels, fitInView
        compensates by scaling down by the same factor, so the net visual zoom
        (fitInView × user zoom) remains unchanged.
        """
        self._scene.clear()
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        current_zoom = self._zoom_level
        self.resetTransform()
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        if current_zoom != 1.0:
            # Multiply the fit transform by the user's zoom without anchor distortion
            t = self.transform()
            t.scale(current_zoom, current_zoom)
            self.setTransform(t)
        # _zoom_level stays the same

    def set_text(self, text: str):
        self._scene.clear()
        self._pixmap_item = None
        self._scene.addText(text)
        self._scene.setSceneRect(self._scene.itemsBoundingRect())
        self.resetTransform()
        self._zoom_level = 1.0

    def clear(self):
        self._scene.clear()
        self._pixmap_item = None

    # -- zoom -----------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = self._ZOOM_FACTOR if delta > 0 else 1 / self._ZOOM_FACTOR
        new_zoom = self._zoom_level * factor
        if new_zoom < self._MIN_ZOOM or new_zoom > self._MAX_ZOOM:
            return
        self._zoom_level = new_zoom
        self.scale(factor, factor)
        # Start (or restart) the debounce timer – fires zoom_changed after 350 ms of inactivity
        self._zoom_timer.start()

    def zoom_to_rect(self, scene_rect: QRectF):
        """Zoom in on *scene_rect* (in pixmap/scene pixel coordinates).

        Updates ``_zoom_level`` so the debounce re-render fires at the right DPI.
        """
        if self._pixmap_item is None:
            return
        self.fitInView(scene_rect, Qt.KeepAspectRatio)
        # Compute new _zoom_level relative to the full-image fit
        sr = self._scene.sceneRect()
        vw = self.viewport().width()
        vh = self.viewport().height()
        if sr.width() > 0 and sr.height() > 0 and scene_rect.width() > 0 and scene_rect.height() > 0:
            full_scale = min(vw / sr.width(), vh / sr.height())
            block_scale = min(vw / scene_rect.width(), vh / scene_rect.height())
            if full_scale > 0:
                self._zoom_level = block_scale / full_scale
        self._zoom_timer.start()
