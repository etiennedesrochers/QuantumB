"""
Drawing generator for AutoCAD Electrical diagrams.
Produces ladder diagrams with rungs of electrical components.
"""
from __future__ import annotations

import io
import ezdxf
from ezdxf import colors
from ezdxf.document import Drawing
from ezdxf.layouts import Modelspace
from pathlib import Path
from dataclasses import dataclass, field

from symbols.electrical_symbols import register_all_symbols
from io_manager import IOItem


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Component:
    symbol: str                         # display name from SYMBOL_REGISTRY
    tag: str = ""                       # manual tag / component reference
    description: str = ""
    io_tag: str = ""                    # linked I/O item tag (empty = no link)
    tag_source: str = "manual"          # "manual" or an IOItem field name
    description_source: str = "manual"  # "manual" or an IOItem field name


@dataclass
class Rung:
    components: list[Component] = field(default_factory=list)
    rung_number: int = 0
    description: str = ""


@dataclass
class LadderConfig:
    title: str = "ELECTRICAL DRAWING"
    project: str = ""
    drawing_number: str = "001"
    revision: str = "A"
    drawn_by: str = ""
    # Ladder geometry
    left_rail_x: float = 10.0
    right_rail_x: float = 210.0
    first_rung_y: float = 270.0
    rung_spacing: float = 20.0
    component_spacing: float = 20.0
    # Paper: A3 landscape default
    paper_width: float = 420.0
    paper_height: float = 297.0


# ─────────────────────────────────────────────────────────────────────────────
# Generator
# ─────────────────────────────────────────────────────────────────────────────

class DrawingGenerator:
    # Class-level variables shared across all instances
    _biggest_fuse_number: int = 0
    _count_link_page: int =0
    
    def __init__(self, config: LadderConfig | None = None):
        self.config = config or LadderConfig()
        self.biggest_fuse_number = DrawingGenerator._biggest_fuse_number


    def reset_static(self):
        self.fuse_counter = 0
    # ── Public API ──────────────────────────────────────────────────────────

    def generate(
        self,
        rungs: list[Rung],
        output_path: str,
        template_doc: Drawing | None = None,
        io_items: list[IOItem] | None = None,
        io_template_placements: list[tuple[Drawing, float, float, IOItem]] | None = None,
        controller_number: int = 1,
        progress_callback: callable | None = None,
    ) -> tuple[bool, str]:
        """
        Build a ladder diagram and save to *output_path*.
        If *template_doc* is supplied it is used as the base (full copy:
        blocks, layers, styles, layouts, etc. are all preserved).
        If *io_template_placements* is supplied, each ``(doc, dx, dy, io_item)`` entry
        is copied (via :meth:`_prepare_io_doc`) and merged into the generated document
        translated by ``(dx, dy)``.
        This is used to place per-IO-point wiring diagrams at their module
        slot positions on controller pages.
        """
        try:
            
            io_lookup = {item.tag: item for item in (io_items or [])}
            doc = self._create_doc(template_doc)
            if io_template_placements:
                for entry in io_template_placements:
                    if len(entry) == 4:
                        tmpl_doc, dx, dy, io_item = entry
                        prepared = self._prepare_io_doc(tmpl_doc, io_item, controller_number)
                    else:
                        tmpl_doc, dx, dy = entry
                        prepared = tmpl_doc
                    self._place_io_template(doc, prepared, dx, dy)
            msp = doc.modelspace()
            sym_map = register_all_symbols(doc)

            self._setup_layers(doc)
            #if the controller number i =0 then not a controller
            #we need to replace some text in it
            if controller_number ==0:
                self.replace_value_dwg(doc,io_items)
            # Only draw our own border/title block when no template is used;
            # templates already contain their own title block and border.
            if template_doc is None:
                self._draw_border(msp)
                self._draw_title_block(msp)
            self._draw_ladder_rails(msp, len(rungs))
            self._draw_rungs(msp, rungs, sym_map, io_lookup)

            # Audit fixes invalid APPID/RegApp entries that cause ODA to reject the file.
            doc.audit()
            doc.saveas(output_path)
            return True, f"Drawing saved to {output_path}"
        except Exception as exc:
            return False, f"Error generating drawing: {exc}"

    def replace_value_dwg(self,doc,item_list: list[IOItem],controller_number:int=0):
        """
        Replace placeholder values, to find them we need to look for the old name.
        Fuse numbers continue sequentially across documents.
        Multiple FU! in same document share the same base number.
        FU!+x are offsets from that base.
        
        Returns the highest fuse number used, to pass to the next document.
        """
        # Ensure we have the latest persisted value from the class variable
        self.biggest_fuse_number = DrawingGenerator._biggest_fuse_number
        doc_base = None  # Will be set on first FU! encountered
        as_replace_link_page= False
        for item in item_list:
            if item.old_name:
                for entity in doc.modelspace():
                    if entity.dxftype() == "INSERT":
                        for attrib in entity.attribs:
                            self.replace_name(attrib, item)
                            doc_base = self.replace_fuse(attrib, doc_base)
                            self.replace_tagstrip(item,entity,attrib)
                            as_replace_link_page = self.replace_link_page( attrib,as_replace_link_page)
                             
        
        # Sync to class variable so next instance picks it up
        DrawingGenerator._biggest_fuse_number = self.biggest_fuse_number
        return self.biggest_fuse_number

    def replace_link_page(self,attrib,replace):
        #Check the attribute to see if it contains LX-$ 
        #X is a value that is the field and we wont change it 
        #$ is a value that we will change
        #We can also have LX-$+x where x is a number that we will add

        #The static variable _count_link_page is use to count
        #Check if the attribute contains LX-$ or LX-$+x

        #We also have the format GND-$+x

        if attrib.dxf.get("text", "").startswith("L") and attrib.dxf.get("text", "").find("-$") != -1:
            if not replace:
                replace = True
                #Increment the count
                DrawingGenerator._count_link_page += 1
            #Replace the $ with the count
            text = attrib.dxf.get("text", "")
            additional_offset = 0
            if text.find("+") != -1:
                additional_offset = int(text.split("+")[1])
            text = text.replace("$", str(DrawingGenerator._count_link_page+additional_offset))
            if text.find("+") != -1:
                text = text.split("+")[0]
            attrib.dxf.text = text

        elif attrib.dxf.get("text", "").startswith("GND") and attrib.dxf.get("text", "").find("-$") != -1:
            if not replace:
                replace = True
                #Increment the count
                DrawingGenerator._count_link_page += 1
            #Replace the $ with the count
            text = attrib.dxf.get("text", "")
            additional_offset = 0
            if text.find("+") != -1:
                additional_offset = int(text.split("+")[1])
            text = text.replace("$", str(DrawingGenerator._count_link_page+additional_offset))
            #Add a split we dont want the +x to be in the text
            if text.find("+") != -1:
                text = text.split("+")[0]
            attrib.dxf.text = text
        return replace

        
        
    def replace_name(self,attrib, item: IOItem):
        if attrib.dxf.get("text", "") == item.old_name:
            attrib.dxf.text = item.tag
        if attrib.dxf.get("text", "") == "COM_" + item.old_name:
            attrib.dxf.text = "COM_" + item.tag
        

    def replace_fuse(self, attrib, doc_base):
        text = attrib.dxf.get("text", "")
        
        # Initialize document base on first FU! or FU!+x encountered
        if doc_base is None:
            doc_base = self.biggest_fuse_number + 1
        
        # Check for FU!+x pattern first (more specific)
        # FU!+x means doc_base + x (all FU!+x variants of same base in a document)
        if "FU!+" in text:
            offset = int(text.split("+")[1])
            fuse_num = doc_base + offset
            self.biggest_fuse_number = max(self.biggest_fuse_number, fuse_num)
            DrawingGenerator._biggest_fuse_number = self.biggest_fuse_number
            attrib.dxf.text = "FU" + str(fuse_num)
        
        # Check for exact FU! match (all FU! in same doc use same base)
        elif text == "FU!":
            self.biggest_fuse_number = max(self.biggest_fuse_number, doc_base)
            DrawingGenerator._biggest_fuse_number = self.biggest_fuse_number
            attrib.dxf.text = "FU" + str(doc_base)
        
        return doc_base

    def replace_tagstrip(self,item,entity,attrib):
        #We need for %tagstrip% and %tagstrip_com% to be replaced with the controller number
        if attrib.dxf.get("text", "") == "%"+item.old_name+"%":
            attrib.dxf.text = item.address
            #For this entity if it has the TERM01 Attribute then we change the value of that attribute
            if entity.has_attrib("TERM01"):
                term_attrib = entity.get_attrib("TERM01")
                term_attrib.dxf.text = item.number
            
        if attrib.dxf.get("text", "") == "%COM_"+item.old_name+"%":
            attrib.dxf.text = "COM_" + item.address
            if entity.has_attrib("TERM01"):
                term_attrib = entity.get_attrib("TERM01")
                term_attrib.dxf.text = item.number
    # ── Internal helpers ────────────────────────────────────────────────────
    #Need to add the information of the io
    def _prepare_io_doc(self, source_doc: Drawing, io_item: IOItem, controller_number: int) -> Drawing:
        """Return an in-memory copy of *source_doc* with placeholder attribute text
        replaced by values from *io_item*.

        The original *source_doc* is never modified.

        Placeholder substitutions applied to every ATTRIB inside INSERT blocks:
          ``IO_CODE``     → io_item.tag          (e.g. "DI_001")
          ``COM_IO_CODE`` → io_item.tag + "_COM"
          ``num``         → io_item.address       (e.g. "AI101")
          ``num_com``     → io_item.address + "_COM"
          ``pos``         → io_item.number      (e.g. "1")
        """
        buf = io.StringIO()
        source_doc.write(buf)
        buf.seek(0)
        copy = ezdxf.read(buf)

        is_input = io_item.io_type.lower() == "input"
        i = "I" if is_input else "O"


        substitutions = {
            "IO_CODE":     io_item.tag,
            "COM_IO_CODE": "COM_" + io_item.tag,
            "num": io_item.address,
            "num_com":     "COM_" + io_item.address,
            "%tagstrip%": "CTL" + i + "_" + str(controller_number),
            "%tagstrip_com%": "COM_" + i + "_" + str(controller_number),
            "POS": io_item.number,
         }

        for entity in copy.modelspace():
            if entity.dxftype() != "INSERT":
                continue
            try:
                for attrib in entity.attribs:
                    text = attrib.dxf.get("text", "")
                    if text in substitutions:
                        attrib.dxf.text = substitutions[text]
            except Exception as exc:
                print(f"Warning: failed to substitute attributes for IO '{io_item.tag}': {exc}")
            

        return copy


    def _place_io_template(self, doc: Drawing, source_doc: Drawing, dx: float, dy: float) -> None:
        """Copy all modelspace entities from *source_doc* into *doc*, translated by (dx, dy)."""
        try:
            from ezdxf import xref
            from ezdxf.math import Matrix44

            existing_handles = {e.dxf.handle for e in doc.modelspace() if e.dxf.hasattr("handle")}

            xref.load_modelspace(source_doc, doc)

            if dx != 0.0 or dy != 0.0:
                matrix = Matrix44.translate(dx, dy, 0)
                for entity in doc.modelspace():
                    if entity.dxf.hasattr("handle") and entity.dxf.handle not in existing_handles:
                        try:
                            entity.transform(matrix)
                        except Exception:
                            pass
        except Exception as exc:
            print(f"Warning: failed to place I/O template at ({dx}, {dy}): {exc}")

    def _create_doc(self, template_doc: Drawing | None) -> Drawing:
        if template_doc is None:
            return ezdxf.new("R2018", setup=True)

        # Make a true in-memory copy of the template by round-tripping through
        # the DXF writer/reader.  This preserves ALL table entries (layers,
        # linetypes, text styles, blocks, …), layouts, and paper-space content
        # – something that manual entity-by-entity copying cannot achieve.
        buf = io.StringIO()
        template_doc.write(buf)
        buf.seek(0)
        doc = ezdxf.read(buf)

        # Remove xref-dependent layers (name contains "|").  They reference an
        # xref block record that only exists in the original host drawing; without
        # it AutoCAD rejects the file with "Layer name with vertical bar is not
        # marked dependent".
        xref_layers = [l.dxf.name for l in doc.layers if "|" in l.dxf.name]
        for name in xref_layers:
            try:
                doc.layers.remove(name)
            except Exception:
                pass

        # Remap entities on xref-dependent layers to layer "0" so no reference
        # to a removed layer remains anywhere in the document.
        for entity in doc.modelspace():
            try:
                if entity.dxf.hasattr("layer") and "|" in entity.dxf.layer:
                    entity.dxf.layer = "0"
            except Exception:
                pass

        return doc

    def _setup_layers(self, doc):
        layers = {
            "WIRES":       colors.WHITE,
            "COMPONENTS":  colors.CYAN,
            "TAGS":        colors.YELLOW,
            "BORDER":      colors.WHITE,
            "TITLE_BLOCK": colors.WHITE,
            "RAIL":        colors.WHITE,
        }
        for name, color in layers.items():
            if name not in doc.layers:
                doc.layers.new(name, dxfattribs={"color": color})

    def _draw_border(self, msp: Modelspace):
        cfg = self.config
        pts = [
            (5, 5),
            (cfg.paper_width - 5, 5),
            (cfg.paper_width - 5, cfg.paper_height - 5),
            (5, cfg.paper_height - 5),
        ]
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "BORDER", "lineweight": 50})

    def _draw_title_block(self, msp: Modelspace):
        cfg = self.config
        pw, ph = cfg.paper_width, cfg.paper_height
        tb_y = 5
        tb_h = 25
        tb_x = 5
        tb_w = pw - 10

        # Outer box
        msp.add_lwpolyline(
            [(tb_x, tb_y), (tb_x + tb_w, tb_y), (tb_x + tb_w, tb_y + tb_h), (tb_x, tb_y + tb_h)],
            close=True,
            dxfattribs={"layer": "TITLE_BLOCK"},
        )

        col_w = tb_w / 5
        fields = [
            ("PROJECT", cfg.project),
            ("TITLE", cfg.title),
            ("DWG NO", cfg.drawing_number),
            ("REV", cfg.revision),
            ("DRAWN BY", cfg.drawn_by),
        ]
        for i, (label, value) in enumerate(fields):
            x = tb_x + i * col_w
            # Vertical divider
            msp.add_line((x, tb_y), (x, tb_y + tb_h), dxfattribs={"layer": "TITLE_BLOCK"})
            # Mid horizontal
            mid_y = tb_y + tb_h / 2
            msp.add_line((x, mid_y), (x + col_w, mid_y), dxfattribs={"layer": "TITLE_BLOCK"})
            # Label (small)
            msp.add_text(
                label,
                dxfattribs={"layer": "TITLE_BLOCK", "height": 2.5, "insert": (x + 1, mid_y + 1)},
            )
            # Value (larger)
            msp.add_text(
                value,
                dxfattribs={"layer": "TITLE_BLOCK", "height": 4, "insert": (x + 1, tb_y + 1)},
            )

    def _draw_ladder_rails(self, msp: Modelspace, num_rungs: int):
        cfg = self.config
        bottom_y = cfg.first_rung_y - (num_rungs) * cfg.rung_spacing
        # L rail
        msp.add_line(
            (cfg.left_rail_x, cfg.first_rung_y + cfg.rung_spacing),
            (cfg.left_rail_x, bottom_y),
            dxfattribs={"layer": "RAIL", "lineweight": 50},
        )
        # R rail
        msp.add_line(
            (cfg.right_rail_x, cfg.first_rung_y + cfg.rung_spacing),
            (cfg.right_rail_x, bottom_y),
            dxfattribs={"layer": "RAIL", "lineweight": 50},
        )
        # Rail labels
        msp.add_text("L1", dxfattribs={"height": 4, "insert": (cfg.left_rail_x - 8, cfg.first_rung_y + cfg.rung_spacing)})
        msp.add_text("N", dxfattribs={"height": 4, "insert": (cfg.right_rail_x + 2, cfg.first_rung_y + cfg.rung_spacing)})

    def _draw_rungs(self, msp: Modelspace, rungs: list[Rung], sym_map: dict, io_lookup: dict):
        cfg = self.config
        for i, rung in enumerate(rungs):
            y = cfg.first_rung_y - i * cfg.rung_spacing
            self._draw_single_rung(msp, rung, y, sym_map, io_lookup)

    def _resolve_component_display(self, comp: Component, io_lookup: dict) -> tuple[str, str]:
        """Return (display_tag, display_description) after resolving I/O field links."""
        io_item = io_lookup.get(comp.io_tag) if comp.io_tag else None
        display_tag = (
            getattr(io_item, comp.tag_source, comp.tag)
            if (io_item and comp.tag_source != "manual")
            else comp.tag
        )
        display_desc = (
            getattr(io_item, comp.description_source, comp.description)
            if (io_item and comp.description_source != "manual")
            else comp.description
        )
        return display_tag, display_desc

    def _draw_single_rung(self, msp: Modelspace, rung: Rung, y: float, sym_map: dict, io_lookup: dict):
        cfg = self.config
        # Rung number on left
        msp.add_text(
            str(rung.rung_number if rung.rung_number else ""),
            dxfattribs={"height": 3, "insert": (cfg.left_rail_x - 8, y - 1.5)},
        )
        # Rung description on right
        if rung.description:
            msp.add_text(
                rung.description,
                dxfattribs={"height": 2.5, "insert": (cfg.right_rail_x + 3, y + 1)},
            )

        # Place components along the rung
        n = len(rung.components)
        if n == 0:
            # Empty wire
            msp.add_line((cfg.left_rail_x, y), (cfg.right_rail_x, y), dxfattribs={"layer": "WIRES"})
            return

        span = cfg.right_rail_x - cfg.left_rail_x
        step = span / (n + 1)
        prev_x = cfg.left_rail_x

        for j, comp in enumerate(rung.components):
            cx = cfg.left_rail_x + step * (j + 1)

            # Wire from previous point to symbol left stub
            msp.add_line((prev_x, y), (cx - 1, y), dxfattribs={"layer": "WIRES"})

            # Insert symbol block
            block_name = sym_map.get(comp.symbol)
            if block_name:
                msp.add_blockref(
                    block_name,
                    (cx, y),
                    dxfattribs={"layer": "COMPONENTS", "xscale": 1.5, "yscale": 1.5},
                )
            else:
                # Fallback: small circle
                msp.add_circle((cx, y), 0.5, dxfattribs={"layer": "COMPONENTS"})

            # Tag above / description below — resolved from I/O link if configured
            display_tag, display_desc = self._resolve_component_display(comp, io_lookup)
            if display_tag:
                msp.add_text(
                    display_tag,
                    dxfattribs={"layer": "TAGS", "height": 2.5, "insert": (cx - 1, y + 3)},
                )
            if display_desc:
                msp.add_text(
                    display_desc,
                    dxfattribs={"layer": "TAGS", "height": 2, "insert": (cx - 3, y - 5)},
                )

            prev_x = cx + 1

        # Wire from last symbol to right rail
        msp.add_line((prev_x, y), (cfg.right_rail_x, y), dxfattribs={"layer": "WIRES"})
