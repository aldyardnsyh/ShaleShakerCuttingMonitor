"""Build a professional PDF report for a session (reportlab Platypus).

Layout: branded header with logo, session-info table, summary-statistics table,
a coverage% / stone-count trend chart, and an interpretation note. Pure-python
(no system deps) so it stays light on the VPS.
"""
from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage,
)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.lineplots import LinePlot

BRAND = colors.HexColor("#F47A20")
BRAND_DARK = colors.HexColor("#C75B12")
SLATE = colors.HexColor("#334155")
SLATE_LIGHT = colors.HexColor("#64748b")
GREY = colors.HexColor("#94a3b8")
ROW_ALT = colors.HexColor("#FBF3EC")
LINE = colors.HexColor("#E5E7EB")

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo.png"


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("HeadTitle", parent=ss["Title"], fontSize=18, textColor=colors.white,
                          leading=22, spaceAfter=0, alignment=TA_LEFT))
    ss.add(ParagraphStyle("HeadSub", parent=ss["Normal"], fontSize=9, textColor=colors.white,
                          leading=12, alignment=TA_LEFT))
    ss.add(ParagraphStyle("Section", parent=ss["Heading2"], fontSize=12, textColor=BRAND_DARK,
                          spaceBefore=10, spaceAfter=6))
    ss.add(ParagraphStyle("Note", parent=ss["Normal"], fontSize=8.5, textColor=SLATE_LIGHT, leading=12))
    return ss


def _header(session: dict, styles) -> Table:
    title = Paragraph("Laporan Analisis Cutting Shale Shaker", styles["HeadTitle"])
    sub = Paragraph(
        f"Sesi: <b>{session.get('name', '-')}</b><br/>"
        f"Dibuat: {datetime.now().strftime('%d %B %Y, %H:%M')}",
        styles["HeadSub"],
    )
    text_cell = [[title], [Spacer(1, 2)], [sub]]
    text_tbl = Table(text_cell, colWidths=[125 * mm])
    text_tbl.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    logo_cell = ""
    if LOGO_PATH.exists():
        try:
            logo_cell = RLImage(str(LOGO_PATH), width=20 * mm, height=20 * mm)
        except Exception:
            logo_cell = ""

    band = Table([[logo_cell, text_tbl]], colWidths=[26 * mm, 150 * mm])
    band.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return band


def _kv_table(rows: list[tuple[str, str]], styles, col0=55 * mm, col1=121 * mm) -> Table:
    data = [[Paragraph(f"<b>{k}</b>", styles["Note"]), Paragraph(str(v), styles["Note"])] for k, v in rows]
    t = Table(data, colWidths=[col0, col1])
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (0, -1), SLATE),
    ]
    for i in range(len(data)):
        if i % 2 == 1:
            style.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
    t.setStyle(TableStyle(style))
    return t


def _summary_table(summary: dict, styles) -> Table:
    cells = [
        ("Total Frame", str(summary.get("frames", 0))),
        ("Rata-rata Coverage", f"{summary.get('avg_coverage_pct', 0):.2f}%"),
        ("Rata-rata FG Area", f"{summary.get('avg_fg_area_pct', 0):.2f}%"),
        ("Maks Stone", str(summary.get("max_stone_count", 0))),
        ("Rata-rata FPS", f"{summary.get('avg_fps', 0):.1f}"),
    ]
    header = [Paragraph(f"<b>{k}</b>", ParagraphStyle("h", fontSize=8.5, textColor=colors.white, alignment=1)) for k, _ in cells]
    values = [Paragraph(f"<b>{v}</b>", ParagraphStyle("v", fontSize=12, textColor=SLATE, alignment=1)) for _, v in cells]
    t = Table([header, values], colWidths=[35.2 * mm] * 5)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def _line_chart(points_cov, points_stone, width, height) -> Drawing:
    d = Drawing(width, height)
    lp = LinePlot()
    lp.x = 40
    lp.y = 26
    lp.width = width - 64
    lp.height = height - 50
    data = [points_cov or [(0, 0)]]
    if points_stone:
        data.append(points_stone)
    lp.data = data
    lp.lines[0].strokeColor = BRAND
    lp.lines[0].strokeWidth = 1.5
    if len(data) > 1:
        lp.lines[1].strokeColor = colors.HexColor("#0ea5e9")
        lp.lines[1].strokeWidth = 1
    lp.xValueAxis.labels.fontSize = 6
    lp.yValueAxis.labels.fontSize = 6
    lp.xValueAxis.strokeColor = GREY
    lp.yValueAxis.strokeColor = GREY
    d.add(lp)
    return d


def build_session_pdf(session: dict, summary: dict, rows: list) -> bytes:
    """rows: list of dicts/objects with frame_idx, coverage_pct, stone_count."""
    buf = io.BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=17 * mm, rightMargin=17 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
        title=f"Laporan Sesi: {session.get('name', '-')}",
    )
    story: list = []

    story.append(_header(session, styles))
    story.append(Spacer(1, 10))

    # ROI formatting
    roi = session.get("roi_json", "-")
    try:
        roi_list = json.loads(roi) if isinstance(roi, str) else roi
        if isinstance(roi_list, list):
            labels = ["TL", "TR", "BR", "BL"]
            roi = "  ".join(f"{labels[i]}({int(p[0])},{int(p[1])})" for i, p in enumerate(roi_list[:4]))
    except Exception:
        pass

    started = session.get("started_at") or "-"
    ended = session.get("ended_at") or "-"

    story.append(Paragraph("Informasi Sesi", styles["Section"]))
    story.append(_kv_table([
        ("Nama Sesi", session.get("name", "-")),
        ("Model", session.get("model", "-")),
        ("Threshold", session.get("threshold", "-")),
        ("Stride", f"deteksi tiap {session.get('stride', '-')} frame"),
        ("Ukuran Grid / Okupansi", f"{session.get('grid_cell_px', '-')} px / τ={session.get('grid_occ_fraction', '-')}"),
        ("ROI (4 titik)", roi),
        ("Mulai", str(started)),
        ("Selesai", str(ended)),
    ], styles))

    story.append(Paragraph("Ringkasan Hasil Analisis", styles["Section"]))
    story.append(_summary_table(summary, styles))

    # Trend chart
    def _v(r, k, default=0):
        if hasattr(r, k):
            return getattr(r, k)
        if isinstance(r, dict):
            return r.get(k, default)
        return default

    cov = [(float(_v(r, "frame_idx", i)), float(_v(r, "coverage_pct", 0) or 0)) for i, r in enumerate(rows)]
    stone = [(float(_v(r, "frame_idx", i)), float(_v(r, "stone_count", 0) or 0)) for i, r in enumerate(rows)]

    story.append(Paragraph("Tren Coverage % (oranye) &amp; Stone Count (biru)", styles["Section"]))
    story.append(_line_chart(cov, stone, 176 * mm, 72 * mm))

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Catatan: <b>Coverage%</b> dihitung dengan metode <b>grid-kuadrat</b> pada ROI ter-rektifikasi "
        "(640x224 px). ROI dibagi sel, sel dihitung &quot;terisi&quot; bila fraksi piksel cutting >= tau, "
        "lalu coverage = sel terisi / total sel x 100. Nilainya bergantung pada ukuran batuan relatif "
        "terhadap ukuran sel. <b>FG Area%</b> adalah persentase piksel mentah sebagai pembanding.",
        styles["Note"],
    ))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def _footer(c, doc):
    """Page footer (credentials): auto-generated note + page number."""
    W, H = A4
    c.saveState()
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(17 * mm, 14 * mm, W - 17 * mm, 14 * mm)
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(GREY)
    c.drawString(17 * mm, 9.5 * mm, "Dokumen ini dihasilkan otomatis oleh sistem.")
    c.setFont("Helvetica", 8)
    c.setFillColor(GREY)
    c.drawRightString(W - 17 * mm, 9.5 * mm, f"Hal. {doc.page}")
    c.restoreState()
