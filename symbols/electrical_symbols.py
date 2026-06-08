"""
AutoCAD Electrical symbol definitions using ezdxf.
Each function draws a symbol at a given insertion point and returns the bounding box width/height.
All symbols are drawn as blocks that can be inserted into a drawing.
"""
import ezdxf
from ezdxf.math import Vec2


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _add_block(doc, name: str) -> ezdxf.document.Drawing:
    """Create or overwrite a named block in doc and return the block layout."""
    if name in doc.blocks:
        del doc.blocks[name]
    return doc.blocks.new(name)


# ─────────────────────────────────────────────────────────────────────────────
# Individual symbols
# ─────────────────────────────────────────────────────────────────────────────

def define_no_contact(doc):
    """Normally-Open contact (IEC style)."""
    blk = _add_block(doc, "SYM_NO_CONTACT")
    # Horizontal line left
    blk.add_line((-1, 0), (-0.4, 0))
    # Two vertical ticks
    blk.add_line((-0.4, -0.3), (-0.4, 0.3))
    blk.add_line((0.4, -0.3), (0.4, 0.3))
    # Horizontal line right
    blk.add_line((0.4, 0), (1, 0))
    return "SYM_NO_CONTACT"


def define_nc_contact(doc):
    """Normally-Closed contact (IEC style)."""
    blk = _add_block(doc, "SYM_NC_CONTACT")
    blk.add_line((-1, 0), (-0.4, 0))
    blk.add_line((-0.4, -0.3), (-0.4, 0.3))
    blk.add_line((0.4, -0.3), (0.4, 0.3))
    blk.add_line((0.4, 0), (1, 0))
    # Diagonal slash indicating NC
    blk.add_line((-0.4, 0.3), (0.4, -0.3))
    return "SYM_NC_CONTACT"


def define_coil(doc):
    """Relay/contactor coil."""
    blk = _add_block(doc, "SYM_COIL")
    blk.add_line((-1, 0), (-0.5, 0))
    blk.add_lwpolyline(
        [(-0.5, -0.3), (0.5, -0.3), (0.5, 0.3), (-0.5, 0.3)],
        close=True,
    )
    blk.add_line((0.5, 0), (1, 0))
    return "SYM_COIL"


def define_motor(doc):
    """Motor symbol (circle with M)."""
    blk = _add_block(doc, "SYM_MOTOR")
    blk.add_circle((0, 0), 0.5)
    blk.add_text("M", dxfattribs={"height": 0.4, "insert": (-0.15, -0.2)})
    # Connection stubs top
    blk.add_line((0, 0.5), (0, 1))
    return "SYM_MOTOR"


def define_terminal(doc):
    """Terminal block symbol."""
    blk = _add_block(doc, "SYM_TERMINAL")
    blk.add_circle((0, 0), 0.2)
    blk.add_line((-1, 0), (-0.2, 0))
    blk.add_line((0.2, 0), (1, 0))
    return "SYM_TERMINAL"


def define_push_button_no(doc):
    """Push button Normally-Open."""
    blk = _add_block(doc, "SYM_PB_NO")
    blk.add_line((-1, 0), (-0.4, 0))
    blk.add_line((-0.4, -0.3), (-0.4, 0.3))
    blk.add_line((0.4, -0.3), (0.4, 0.3))
    blk.add_line((0.4, 0), (1, 0))
    # Push button actuator
    blk.add_line((-0.2, 0.3), (0.2, 0.3))
    blk.add_line((0, 0.3), (0, 0.6))
    blk.add_line((-0.15, 0.6), (0.15, 0.6))
    return "SYM_PB_NO"


def define_fuse(doc):
    """Fuse symbol."""
    blk = _add_block(doc, "SYM_FUSE")
    blk.add_line((-1, 0), (-0.5, 0))
    blk.add_lwpolyline(
        [(-0.5, -0.15), (0.5, -0.15), (0.5, 0.15), (-0.5, 0.15)],
        close=True,
    )
    blk.add_line((0.5, 0), (1, 0))
    return "SYM_FUSE"


def define_circuit_breaker(doc):
    """Circuit breaker symbol."""
    blk = _add_block(doc, "SYM_CB")
    blk.add_line((-1, 0), (-0.4, 0))
    blk.add_circle((0, 0), 0.4)
    blk.add_line((-0.28, -0.28), (0.28, 0.28))   # diagonal slash
    blk.add_line((0.4, 0), (1, 0))
    return "SYM_CB"


def define_ground(doc):
    """Ground / earth symbol."""
    blk = _add_block(doc, "SYM_GROUND")
    blk.add_line((0, 0), (0, -0.5))
    blk.add_line((-0.5, -0.5), (0.5, -0.5))
    blk.add_line((-0.3, -0.7), (0.3, -0.7))
    blk.add_line((-0.1, -0.9), (0.1, -0.9))
    return "SYM_GROUND"


def define_transformer(doc):
    """Transformer symbol (two coupled coils)."""
    blk = _add_block(doc, "SYM_TRANSFORMER")
    # Primary coil arcs
    import math
    for i in range(3):
        cx = -0.5 + i * 0.3
        blk.add_arc((cx, 0), 0.15, 0, 180)
    # Secondary coil arcs
    for i in range(3):
        cx = 0.5 + i * 0.3
        blk.add_arc((cx, 0), 0.15, 0, 180)
    # Center dividing line
    blk.add_line((0, -0.5), (0, 0.5))
    # Connection stubs
    blk.add_line((-1.1, 0), (-0.5, 0))
    blk.add_line((1.4, 0), (1.9, 0))
    return "SYM_TRANSFORMER"


# ─────────────────────────────────────────────────────────────────────────────
# Register all symbols into a document
# ─────────────────────────────────────────────────────────────────────────────

SYMBOL_REGISTRY: dict[str, callable] = {
    "NO Contact": define_no_contact,
    "NC Contact": define_nc_contact,
    "Coil": define_coil,
    "Motor": define_motor,
    "Terminal": define_terminal,
    "Push Button (NO)": define_push_button_no,
    "Fuse": define_fuse,
    "Circuit Breaker": define_circuit_breaker,
    "Ground": define_ground,
    "Transformer": define_transformer,
}


def register_all_symbols(doc) -> dict[str, str]:
    """Define all symbols as blocks in *doc*.  Returns {display_name: block_name}."""
    mapping = {}
    for display_name, fn in SYMBOL_REGISTRY.items():
        block_name = fn(doc)
        mapping[display_name] = block_name
    return mapping
