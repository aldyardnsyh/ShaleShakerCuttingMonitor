"""Build a professional Daily Shale Shaker Report style PDF for a session.

Fits on exactly one A4 page with bounded borders for all tables, image, and chart.
"""
from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Group
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.legends import Legend

INK = colors.HexColor("#111827")
SLATE = colors.HexColor("#1F2937")
SLATE_LIGHT = colors.HexColor("#374151")
GREY = colors.HexColor("#6B7280")
LIGHT_BG = colors.HexColor("#F3F4F6")
HEADER_BG = colors.HexColor("#E5E7EB")
LINE = colors.HexColor("#000000")
ORANGE = colors.HexColor("#F47A20")
BLUE = colors.HexColor("#0EA5E9")
REPORT_FORMAT_VERSION = "daily-shale-shaker-a4-v1"

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo.png"


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("HeadTitle", parent=ss["Title"], fontSize=11, textColor=INK,
                          leading=13, spaceAfter=0, alignment=TA_LEFT, fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("HeadSub", parent=ss["Normal"], fontSize=7, textColor=SLATE_LIGHT,
                          leading=8.5, alignment=TA_LEFT, fontName="Helvetica"))
    ss.add(ParagraphStyle("Section", parent=ss["Heading2"], fontSize=8, textColor=INK,
                          leading=9.5, spaceBefore=2, spaceAfter=2, fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("CellBold", parent=ss["Normal"], fontSize=6.2, textColor=INK, leading=7.2, fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("CellNormal", parent=ss["Normal"], fontSize=6.2, textColor=SLATE_LIGHT, leading=7.2, fontName="Helvetica"))
    ss.add(ParagraphStyle("Note", parent=ss["Normal"], fontSize=6, textColor=GREY, leading=7.2, fontName="Helvetica-Oblique"))
    return ss


def _section_header(title_text: str, styles) -> Table:
    p = Paragraph(f"<b>{title_text}</b>", ParagraphStyle("sec", parent=styles["Section"], fontSize=7.5, textColor=INK, leading=9, fontName="Helvetica-Bold"))
    t = Table([[p]], colWidths=[186 * mm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def _header(session: dict, styles) -> Table:
    title = Paragraph("DAILY SHALE SHAKER CUTTING ANALYSIS REPORT", styles["HeadTitle"])
    report_time = session.get("ended_at") or session.get("started_at") or session.get("created_at")
    try:
        report_date = datetime.fromisoformat(str(report_time)).strftime("%d-%b-%Y, %H:%M")
    except Exception:
        report_date = "-"
    sub = Paragraph(
        f"SESSION: <b>{session.get('name', '-')}</b> | DATE: {report_date}",
        styles["HeadSub"],
    )
    text_cell = [[title], [Spacer(1, 1)], [sub]]
    text_tbl = Table(text_cell, colWidths=[160 * mm])
    text_tbl.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    logo_cell = ""
    if LOGO_PATH.exists():
        try:
            logo_cell = RLImage(str(LOGO_PATH), width=12 * mm, height=12 * mm)
        except Exception:
            logo_cell = ""

    band = Table([[logo_cell, text_tbl]], colWidths=[16 * mm, 170 * mm])
    band.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HEADER_BG),
        ("GRID", (0, 0), (-1, -1), 0.6, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return band


def _general_parameters_grid(session: dict, styles) -> Table:
    """Rigid 2-column key-value grid with full borders."""
    roi = session.get("roi_json", "-")
    roi_list = None
    try:
        roi_list = json.loads(roi) if isinstance(roi, str) else roi
    except Exception:
        pass

    def p_b(txt): return Paragraph(str(txt), styles["CellBold"])
    def p_n(txt): return Paragraph(str(txt), styles["CellNormal"])

    def _fmt_ts(val):
        if not val or val == "-": return "-"
        try:
            d = datetime.fromisoformat(str(val))
            return d.strftime("%d %b %Y, %H:%M:%S")
        except Exception:
            return str(val)

    started = _fmt_ts(session.get("started_at"))
    ended = _fmt_ts(session.get("ended_at"))

    tl = f"({int(roi_list[0][0])}, {int(roi_list[0][1])})" if isinstance(roi_list, list) and len(roi_list) > 0 else "-"
    tr = f"({int(roi_list[1][0])}, {int(roi_list[1][1])})" if isinstance(roi_list, list) and len(roi_list) > 1 else "-"
    br = f"({int(roi_list[2][0])}, {int(roi_list[2][1])})" if isinstance(roi_list, list) and len(roi_list) > 2 else "-"
    bl = f"({int(roi_list[3][0])}, {int(roi_list[3][1])})" if isinstance(roi_list, list) and len(roi_list) > 3 else "-"

    rows = [
        [p_b("NAMA SESI"), p_n(session.get("name", "-")), p_b("MODEL SEGMENTASI"), p_n(session.get("model", "-"))],
        [p_b("DETECTION THRESHOLD"), p_n(session.get("threshold", "-")), p_b("FRAME STRIDE"), p_n(f"Tiap {session.get('stride', '-')} frame")],
        [p_b("UKURAN GRID"), p_n(f"{session.get('grid_cell_px', '-')} px"), p_b("FRAKSI OKUPANSI (tau)"), p_n(session.get("grid_occ_fraction", "-"))],
        [p_b("ROI TOP-LEFT (TL)"), p_n(tl), p_b("ROI TOP-RIGHT (TR)"), p_n(tr)],
        [p_b("ROI BOTTOM-RIGHT (BR)"), p_n(br), p_b("ROI BOTTOM-LEFT (BL)"), p_n(bl)],
        [p_b("WAKTU MULAI"), p_n(started), p_b("WAKTU SELESAI"), p_n(ended)],
    ]

    t = Table(rows, colWidths=[43 * mm, 50 * mm, 43 * mm, 50 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.6, LINE),
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_BG),
        ("BACKGROUND", (2, 0), (2, -1), LIGHT_BG),
        ("TOPPADDING", (0, 0), (-1, -1), 1.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _summary_table(summary: dict, styles) -> Table:
    cells = [
        ("FRAME TERANALISIS", f"{summary.get('frames', 0)} frame"),
        ("RATA-RATA COVERAGE", f"{summary.get('avg_coverage_pct', 0):.2f}%"),
        ("RATA-RATA FG AREA", f"{summary.get('avg_fg_area_pct', 0):.2f}%"),
        ("MAX STONE COUNT", f"{summary.get('max_stone_count', 0)} batu"),
        ("RATA-RATA FPS", f"{summary.get('avg_fps', 0):.1f}"),
    ]
    header = [Paragraph(f"<b>{k}</b>", ParagraphStyle("h", fontSize=6, textColor=INK, alignment=1, fontName="Helvetica-Bold")) for k, _ in cells]
    values = [Paragraph(f"<b>{v}</b>", ParagraphStyle("v", fontSize=8.5, textColor=SLATE, alignment=1, fontName="Helvetica-Bold")) for _, v in cells]
    t = Table([header, values], colWidths=[37.2 * mm] * 5)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.6, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return t


def _line_chart(points_cov, points_stone, width, height) -> Table:
    d = Drawing(width, height)

    lp = LinePlot()
    lp.x = 30
    lp.y = 20
    lp.width = width - 42
    lp.height = height - 26

    cov_data = list(points_cov) if points_cov else [(0, 0)]
    stone_data = list(points_stone) if points_stone else [(0, 0)]

    if len(cov_data) == 1:
        cov_data.append((cov_data[0][0] + 1.0, cov_data[0][1]))
    if len(stone_data) == 1:
        stone_data.append((stone_data[0][0] + 1.0, stone_data[0][1]))

    data = [cov_data, stone_data]
    lp.data = data
    lp.lines[0].strokeColor = ORANGE
    lp.lines[0].strokeWidth = 1.6
    if len(data) > 1:
        lp.lines[1].strokeColor = BLUE
        lp.lines[1].strokeWidth = 1.4

    # Garis-garis kisi (Gridlines) untuk tampilan grafik profesional
    lp.xValueAxis.labels.fontSize = 5.5
    lp.yValueAxis.labels.fontSize = 5.5
    lp.xValueAxis.strokeColor = LINE
    lp.yValueAxis.strokeColor = LINE
    lp.xValueAxis.visibleGrid = 1
    lp.yValueAxis.visibleGrid = 1
    lp.xValueAxis.gridStrokeColor = colors.HexColor("#E5E7EB")
    lp.yValueAxis.gridStrokeColor = colors.HexColor("#E5E7EB")
    lp.xValueAxis.gridStrokeWidth = 0.5
    lp.yValueAxis.gridStrokeWidth = 0.5

    # Label Aksis X dan Y yang Informatif di PDF
    d.add(String(width / 2, 0, "Indeks Frame (Source Frame Index)", textAnchor="middle", fontSize=6, fontName="Helvetica-Bold", fillColor=SLATE))

    y_label = Group()
    y_label.add(String(0, 0, "Nilai (%) / Stone", textAnchor="middle", fontSize=5.5, fontName="Helvetica-Bold", fillColor=SLATE))
    y_label.transform = (0, 1, -1, 0, 10, height / 2)
    d.add(y_label)

    # Add embedded Legend
    legend = Legend()
    legend.x = width - 110
    legend.y = height - 4
    legend.dxTextSpace = 4
    legend.dy = 4
    legend.dx = 12
    legend.deltay = 8
    legend.alignment = "right"
    legend.colorNamePairs = [(ORANGE, "Coverage %"), (BLUE, "Stone Count")]
    legend.fontName = "Helvetica-Bold"
    legend.fontSize = 5.5

    d.add(lp)
    d.add(legend)

    # Wrap chart in a table to enforce solid border
    chart_box = Table([[d]], colWidths=[width])
    chart_box.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return chart_box


def build_session_pdf(session: dict, summary: dict, rows: list, best_frame_jpg: bytes | None = None) -> bytes:
    """Build a standard A4 Daily Shale Shaker Report style PDF."""
    buf = io.BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=12 * mm, rightMargin=12 * mm, topMargin=6 * mm, bottomMargin=6 * mm,
        title=f"Report - Session {session.get('name', '-')}",
    )
    story: list = []

    story.append(_header(session, styles))
    story.append(Spacer(1, 2))

    story.append(_section_header("GENERAL SESSION &amp; DETECTION PARAMETERS", styles))
    story.append(_general_parameters_grid(session, styles))
    story.append(Spacer(1, 2))

    story.append(_section_header("ANALYTICAL PERFORMANCE &amp; SUMMARY", styles))
    story.append(_summary_table(summary, styles))
    story.append(Spacer(1, 2))

    def _v(r, k, default=0):
        if hasattr(r, k): return getattr(r, k)
        if isinstance(r, dict): return r.get(k, default)
        return default

    cov = [(float(_v(r, "frame_idx", i)), float(_v(r, "coverage_pct", 0) or 0)) for i, r in enumerate(rows)]
    stone = [(float(_v(r, "frame_idx", i)), float(_v(r, "stone_count", 0) or 0)) for i, r in enumerate(rows)]

    if best_frame_jpg:
        try:
            from PIL import Image as PILImage
            img_io = io.BytesIO(best_frame_jpg)
            pil_img = PILImage.open(img_io)
            img_w, img_h = pil_img.size
            img_io.seek(0)
            max_w = 182 * mm
            aspect = img_h / img_w
            img_obj = RLImage(img_io, width=max_w, height=max_w * aspect)
            img_box = Table([[img_obj]], colWidths=[186 * mm])
            img_box.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.6, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.append(_section_header("SAMPLE FRAME RESULT (VERIFIED OVERLAY)", styles))
            story.append(img_box)
            story.append(Spacer(1, 2))
        except Exception:
            pass

    story.append(_section_header("TREND ANALYSIS", styles))
    story.append(_line_chart(cov, stone, 186 * mm, 46 * mm))

    story.append(Spacer(1, 2))
    story.append(Paragraph(
        "CATATAN PARAMETER: <b>Total Frame Teranalisis</b> adalah jumlah sampel frame yang diproses oleh AI "
        "berdasarkan <b>Frame Stride</b> (misal Stride=10 membaca 1 dari 10 frame video). Sumbu X grafik menunjukkan "
        "<b>Indeks Frame Asli</b> pada file video (misal 0 s.d 851).",
        styles["Note"],
    ))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def _footer(c, doc):
    """Standard page footer with confidentiality & page numbers."""
    W, H = A4
    c.saveState()
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(12 * mm, 10 * mm, W - 12 * mm, 10 * mm)
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColor(INK)
    c.drawString(12 * mm, 6 * mm, "CONFIDENTIAL | SHALE SHAKER MONITORING SYSTEM")
    c.setFont("Helvetica", 6.5)
    c.setFillColor(GREY)
    c.drawRightString(W - 12 * mm, 6 * mm, f"Page {doc.page} of 1")
    c.restoreState()
