#!/usr/bin/env python3
"""Render stored XLSX cells/merges/styles to SVG/HTML, without Excel or APIs."""
from decimal import Decimal
from html import escape
from pathlib import Path
import re
import unicodedata
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from validate_samples import load_workbook

DEV = Path(__file__).resolve().parent
PUBLIC = DEV.parents[1] / "frontend/public/samples/purchase-orders"
N = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def coordinate(address):
    column = 0
    for char in re.match(r"[A-Z]+", address).group():
        column = column * 26 + ord(char) - 64
    return column, int(re.search(r"\d+$", address).group())


def wrapped(value, width, size):
    lines, current, length = [], "", 0
    for char in value:
        advance = size * (1 if unicodedata.east_asian_width(char) in ("W", "F") else 0.56)
        if char == "\n" or length + advance > width:
            lines.append(current)
            current, length = "", 0
            if char == "\n":
                continue
        current += char
        length += advance
    return lines + [current]


def render(case):
    path = PUBLIC / f"purchase_order_{case}.xlsx"
    sheet = next(iter(load_workbook(path).values()))
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        styles = ET.fromstring(archive.read("xl/styles.xml"))
    fonts = list(styles.find("s:fonts", N))
    fills = list(styles.find("s:fills", N))
    xfs = list(styles.find("s:cellXfs", N))
    bounds = coordinate(root.find("s:dimension", N).get("ref").split(":")[-1])
    widths = [80.0] * bounds[0]
    for column in root.findall("s:cols/s:col", N):
        for index in range(int(column.get("min")) - 1, int(column.get("max"))):
            widths[index] = float(column.get("width")) * 7
    default = float(root.find("s:sheetFormatPr", N).get("defaultRowHeight")) * 4 / 3
    heights = [default] * bounds[1]
    for row in root.findall("s:sheetData/s:row", N):
        if row.get("ht"):
            heights[int(row.get("r")) - 1] = float(row.get("ht")) * 4 / 3
    xs, ys = [46.0], [100.0]
    for width in widths:
        xs.append(xs[-1] + width)
    for height in heights:
        ys.append(ys[-1] + height)
    width, height = round(xs[-1] + 24), round(ys[-1] + 24)
    chunks = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
              '<rect width="100%" height="100%" fill="#fff"/>',
              f'<text x="24" y="28" font-family="Malgun Gothic, sans-serif" font-size="20" font-weight="700">{escape(path.name)}</text>',
              '<text x="24" y="53" font-family="Malgun Gothic, sans-serif" font-size="12" fill="#596778">체험용 가상 데이터 · XLSX 셀/병합/스타일 미리보기 (Excel 인쇄 렌더링 아님)</text>']
    merged, covered = {}, set()
    for ref in sheet["merges"]:
        start, end = ref.split(":")
        c1, r1 = coordinate(start)
        c2, r2 = coordinate(end)
        merged[(c1, r1)] = (c2, r2)
        covered.update((c, r) for c in range(c1, c2 + 1) for r in range(r1, r2 + 1) if (c, r) != (c1, r1))
    source_cells = {cell.get("r"): cell for cell in root.findall("s:sheetData/s:row/s:c", N)}
    for address, cell in source_cells.items():
        c, r = coordinate(address)
        if (c, r) in covered:
            continue
        c2, r2 = merged.get((c, r), (c, r))
        x, y, w, h = xs[c - 1], ys[r - 1], xs[c2] - xs[c - 1], ys[r2] - ys[r - 1]
        xf = xfs[int(cell.get("s", "0"))]
        font = fonts[int(xf.get("fontId", "0"))]
        fill = fills[int(xf.get("fillId", "0"))].find("s:patternFill/s:fgColor", N)
        color = "#" + fill.get("rgb")[-6:] if fill is not None else "#ffffff"
        border = "#d2d8df" if int(xf.get("borderId", "0")) or case == "B" else color
        chunks.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{color}" stroke="{border}" stroke-width="0.6"/>')
        value = sheet["cells"].get(address)
        if value is None:
            continue
        if isinstance(value, Decimal):
            label = f"{value:,f}".rstrip("0").rstrip(".") if value.as_tuple().exponent < 0 else f"{value:,f}"
        else:
            label = str(value)
        size = float(font.find("s:sz", N).get("val")) * 4 / 3
        fg = font.find("s:color", N)
        ink = "#" + fg.get("rgb")[-6:] if fg is not None and fg.get("rgb") else "#172331"
        weight = "700" if font.find("s:b", N) is not None else "400"
        alignment = xf.find("s:alignment", N)
        wrap = alignment is not None and alignment.get("wrapText") == "1"
        lines = wrapped(label, w - 10, size) if wrap else [label]
        anchor = "end" if isinstance(value, Decimal) else "middle" if alignment is not None and alignment.get("horizontal") == "center" else "start"
        tx = x + w - 5 if anchor == "end" else x + w / 2 if anchor == "middle" else x + 5
        baseline = y + max(size, (h - len(lines) * size * 1.12) / 2 + size * 0.84)
        clip = f"clip-{address}"
        chunks.append(f'<clipPath id="{clip}"><rect x="{x+2}" y="{y+1}" width="{w-4}" height="{h-2}"/></clipPath>')
        for line in lines:
            chunks.append(f'<text x="{tx}" y="{baseline}" text-anchor="{anchor}" font-family="Malgun Gothic, sans-serif" font-size="{size}" font-weight="{weight}" fill="{ink}" clip-path="url(#{clip})">{escape(line)}</text>')
            baseline += size * 1.12
    for row, y in enumerate(ys[:-1], 1):
        chunks.append(f'<text x="12" y="{y + heights[row-1]/2+4}" font-size="11" fill="#7b8795">{row}</text>')
    chunks.append("</svg>")
    svg = "\n".join(chunks)
    folder = DEV / "previews"
    folder.mkdir(exist_ok=True)
    (folder / f"{case}.svg").write_text(svg, encoding="utf-8")
    html = f'<!doctype html><html lang="ko"><meta charset="utf-8"><title>샘플 {case} 미리보기</title><body style="margin:0;background:white">{svg}</body></html>'
    (folder / f"{case}.html").write_text(html, encoding="utf-8")
    print(f"{case}: {width}x{height}")


if __name__ == "__main__":
    for sample in "ABC":
        render(sample)
