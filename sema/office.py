"""Microsoft Office apps beyond Word and Outlook: Excel, PowerPoint, OneNote.

Spreadsheets need their own treatment: read cell by cell, "1200\t1350\t980" is
noise. Sema reads a selected table the way a person would describe it, pairing
each value with its column header ("North. Q1: twelve hundred dollars, Q2: ...").
"""
from __future__ import annotations

import re

MAX_CELLS = 3000


def _is_number(s: str) -> bool:
    return bool(re.fullmatch(r"[-+(]?[$€£¥₹]?\s?[\d,]*\.?\d+\s?%?[)]?[kKmMbB]?", s.strip()))


def table_to_speech(rows: list[list[str]]) -> str:
    """Turn a grid of displayed cell texts into natural sentences."""
    rows = [[(c or "").strip() for c in r] for r in rows]
    rows = [r for r in rows if any(r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    cols = [c for c in range(width) if any(r[c] for r in rows)]
    rows = [[r[c] for c in cols] for r in rows]
    width = len(cols)

    if len(rows) == 1 or width == 1:              # a single row or column: just list it
        cells = [c for r in rows for c in r if c]
        if len(cells) == 1:
            return cells[0]
        return ". ".join(cells) + "."

    head = rows[0]
    body = rows[1:]
    header_like = all(head) and not any(_is_number(h) for h in head) and \
        any(_is_number(c) for r in body for c in r)
    label_col = all(r[0] and not _is_number(r[0]) for r in body)
    out = []
    if header_like:
        for r in body:
            parts = []
            start = 0
            lead = ""
            if label_col:
                lead = r[0] + ". "
                start = 1
            for h, v in zip(head[start:], r[start:]):
                if v:
                    parts.append(f"{h}: {v}")
            out.append(lead + ", ".join(parts) + ".")
    else:
        for i, r in enumerate(rows, 1):
            cells = [c for c in r if c]
            if cells:
                out.append(f"Row {i}: " + ", ".join(cells) + ".")
    return "\n".join(out)


def tsv_to_speech(text: str) -> str:
    """Clipboard copies from Excel arrive as tab-separated lines."""
    if "\t" not in text:
        return text
    return table_to_speech([line.split("\t") for line in text.rstrip("\r\n").split("\n")])


# --------------------------------------------------------------------------- Excel (COM)

def _range_rows(rng) -> list[list[str]]:
    rows = []
    n = 0
    for r in range(1, rng.Rows.Count + 1):
        row = []
        for c in range(1, rng.Columns.Count + 1):
            n += 1
            if n > MAX_CELLS:
                return rows
            row.append(str(rng.Cells(r, c).Text))  # .Text is what's displayed: "$1,200", "18-Oct"
        rows.append(row)
    return rows


def excel_selection(app) -> str:
    sel = app.Selection
    try:
        areas = sel.Areas
    except Exception:  # a chart or shape is selected, not cells
        return ""
    parts = []
    for i in range(1, areas.Count + 1):
        area = areas.Item(i)
        if area.Count == 1:
            parts.append(_single_cell(area))
        else:
            parts.append(table_to_speech(_range_rows(area)))
    return "\n\n".join(p for p in parts if p)


def _single_cell(cell) -> str:
    text = str(cell.Text)
    try:
        if cell.HasFormula and not text.strip():
            return ""
    except Exception:
        pass
    return text


def excel_sheet(app) -> str:
    """The active sheet's used area, starting from the selected row."""
    sheet = app.ActiveSheet
    used = sheet.UsedRange
    first_row = max(used.Row, app.ActiveCell.Row if app.ActiveCell is not None else used.Row)
    head = sheet.Range(sheet.Cells(used.Row, used.Column),
                       sheet.Cells(used.Row, used.Column + used.Columns.Count - 1))
    last_row = used.Row + used.Rows.Count - 1
    body = sheet.Range(sheet.Cells(max(first_row, used.Row + 1), used.Column),
                       sheet.Cells(last_row, used.Column + used.Columns.Count - 1))
    rows = _range_rows(head) + _range_rows(body)
    return f"Sheet {sheet.Name}.\n\n" + table_to_speech(rows)


# --------------------------------------------------------------------------- PowerPoint (COM)

def _shape_text(shape) -> str:
    try:
        if shape.HasTextFrame and shape.TextFrame.HasText:
            return str(shape.TextFrame.TextRange.Text).replace("\r", "\n")
        if shape.HasTable:
            t = shape.Table
            return table_to_speech([[str(t.Cell(r, c).Shape.TextFrame.TextRange.Text)
                                     for c in range(1, t.Columns.Count + 1)]
                                    for r in range(1, t.Rows.Count + 1)])
    except Exception:
        pass
    return ""


def powerpoint_selection(app) -> str:
    sel = app.ActiveWindow.Selection
    if sel.Type == 3:      # ppSelectionText
        return str(sel.TextRange.Text).replace("\r", "\n")
    if sel.Type == 2:      # ppSelectionShapes
        return "\n\n".join(t for t in (_shape_text(s) for s in sel.ShapeRange) if t)
    return ""


def powerpoint_from_current_slide(app, with_notes: bool = True) -> str:
    pres = app.ActivePresentation
    start = app.ActiveWindow.View.Slide.SlideIndex
    out = []
    for i in range(start, pres.Slides.Count + 1):
        slide = pres.Slides(i)
        texts = [t for t in (_shape_text(s) for s in slide.Shapes) if t]
        block = f"Slide {i}.\n\n" + "\n\n".join(texts)
        if with_notes:
            try:
                notes = _shape_text(slide.NotesPage.Shapes.Placeholders(2))
                if notes.strip():
                    block += "\n\nSpeaker notes. " + notes
            except Exception:
                pass
        out.append(block)
    return "\n\n".join(out)
