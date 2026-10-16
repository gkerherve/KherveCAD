"""A minimal .xlsx writer (Qt-free, no openpyxl): Office Open XML by
zipfile, for the BOM and the P&ID schedules. `write(path, sheets)`
takes {sheet name: rows}; the first row of each sheet is a bold, frozen
header, numbers stay numbers, a row starting "TOTAL" is bold too.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import re
import zipfile
from xml.sax.saxutils import escape

_NS = "http://schemas.openxmlformats.org"


def _col(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _cell(r, c, value, bold):
    ref = f"{_col(c)}{r + 1}"
    style = ' s="1"' if bold else ""
    if isinstance(value, bool):
        value = str(value)
    if isinstance(value, (int, float)) and not (
            isinstance(value, float) and (math.isnan(value) or
                                          math.isinf(value))):
        return f'<c r="{ref}"{style}><v>{value}</v></c>'
    if value in ("", None):
        return ""
    return (f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space='
            f'"preserve">{escape(str(value))}</t></is></c>')


def _sheet(rows):
    out = []
    for r, row in enumerate(rows):
        bold = r == 0 or (len(row) > 1 and "TOTAL" in (row[0], row[1]))
        out.append(f'<row r="{r + 1}">' + "".join(
            _cell(r, c, v, bold) for c, v in enumerate(row)) + "</row>")
    ncol = max((len(r) for r in rows), default=1)
    widths = [max(8, min(60, max((len(str(row[c])) for row in rows
                                  if c < len(row)), default=6) + 2))
              for c in range(ncol)]
    cols = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" '
                   'customWidth="1"/>' for i, w in enumerate(widths))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<worksheet xmlns="{_NS}/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" '
            'topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
            f'</sheetView></sheetViews><cols>{cols}</cols><sheetData>'
            + "".join(out) + "</sheetData></worksheet>")


def write(path, sheets):
    """*sheets*: {name: [row, ...]} (or a list of (name, rows))."""
    items = list(sheets.items()) if isinstance(sheets, dict) else \
        list(sheets)
    names = []
    for name, _rows in items:
        clean = re.sub(r"[\[\]:*?/\\]", " ", str(name))[:31] or "Sheet"
        while clean in names:
            clean = clean[:28] + f"_{len(names)}"
        names.append(clean)
    rel = f"{_NS}/officeDocument/2006/relationships"
    ctype = "application/vnd.openxmlformats-officedocument.spreadsheetml"
    files = {
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Types xmlns="{_NS}/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.'
            'openxmlformats-package.relationships+xml"/><Default '
            'Extension="xml" ContentType="application/xml"/>'
            f'<Override PartName="/xl/workbook.xml" ContentType="{ctype}'
            '.sheet.main+xml"/>' + "".join(
                f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" '
                f'ContentType="{ctype}.worksheet+xml"/>'
                for i in range(len(items))) +
            f'<Override PartName="/xl/styles.xml" ContentType="{ctype}'
            '.styles+xml"/></Types>',
        "_rels/.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{_NS}/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{rel}/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<workbook xmlns="{_NS}/spreadsheetml/2006/main" '
            f'xmlns:r="{rel}"><sheets>' + "".join(
                f'<sheet name="{escape(n)}" sheetId="{i + 1}" '
                f'r:id="rId{i + 1}"/>' for i, n in enumerate(names)) +
            '</sheets></workbook>',
        "xl/_rels/workbook.xml.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{_NS}/package/2006/relationships">'
            + "".join(f'<Relationship Id="rId{i + 1}" Type="{rel}/'
                      f'worksheet" Target="worksheets/sheet{i + 1}.xml"/>'
                      for i in range(len(items))) +
            f'<Relationship Id="rId{len(items) + 1}" Type="{rel}/styles" '
            'Target="styles.xml"/></Relationships>',
        "xl/styles.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<styleSheet xmlns="{_NS}/spreadsheetml/2006/main">'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/>'
            '</font><font><b/><sz val="11"/><name val="Calibri"/></font>'
            '</fonts><fills count="2"><fill><patternFill patternType='
            '"none"/></fill><fill><patternFill patternType="gray125"/>'
            '</fill></fills><borders count="1"><border/></borders>'
            '<cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs '
            'count="2"><xf/><xf fontId="1" applyFont="1"/></cellXfs>'
            '</styleSheet>',
    }
    for i, (_n, rows) in enumerate(items):
        files[f"xl/worksheets/sheet{i + 1}.xml"] = _sheet(rows)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return path
