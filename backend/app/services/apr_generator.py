"""
APR (Action Taken Report) PDF generator using fpdf2.
Pure Python -- no GTK/GLib dependencies, works on Windows.
"""
from __future__ import annotations
import base64
import hashlib
import io
import unicodedata
from datetime import datetime
from typing import Optional

from fpdf import FPDF

DEPT_NAMES = {
    "PWD": "Public Works Department",
    "WATER": "Water Supply & Sewerage Board",
    "ELEC": "Electricity Board",
    "HEALTH": "Health & Sanitation",
    "PARKS": "Parks & Horticulture",
    "TRAFFIC": "Traffic Engineering",
    "HERITAGE": "Heritage Conservation",
    "SOLID_WASTE": "Solid Waste Management",
    "STORM": "Storm Water Drains",
    "REVENUE": "Revenue Department",
}

PRIORITY_COLORS = {
    "CRITICAL": (220, 53, 69),
    "HIGH": (255, 133, 27),
    "MEDIUM": (200, 150, 0),
    "LOW": (40, 167, 69),
}

PAGE_W = 210  # A4 mm
L_MARGIN = 14
R_MARGIN = 14
CONTENT_W = PAGE_W - L_MARGIN - R_MARGIN  # 182 mm


def _safe(text: object) -> str:
    """Convert any value to a latin-1-safe string for fpdf2 built-in fonts."""
    if text is None:
        return "-"
    s = unicodedata.normalize("NFKD", str(text))
    return s.encode("latin-1", errors="replace").decode("latin-1")


class APRPDF(FPDF):
    def header(self):
        self.set_fill_color(15, 52, 96)
        self.rect(0, 0, PAGE_W, 26, "F")
        # Title
        self.set_xy(L_MARGIN, 6)
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(255, 255, 255)
        self.cell(CONTENT_W, 8, "JanVedha Civic Platform", align="C", new_x="LMARGIN", new_y="NEXT")
        # Subtitle
        self.set_x(L_MARGIN)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(180, 210, 240)
        self.cell(CONTENT_W, 5, "Action Taken Report (APR) - Official Document", align="C",
                  new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(4)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(130, 130, 130)
        self.cell(CONTENT_W, 5,
                  "System-generated document. Verify at janvedha.gov.in  |  Page " + str(self.page_no()),
                  align="C")


def _section(pdf: APRPDF, title: str) -> None:
    pdf.set_fill_color(220, 230, 245)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(15, 52, 96)
    pdf.set_x(L_MARGIN)
    pdf.cell(CONTENT_W, 7, "  " + _safe(title), fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)


def _row(pdf: APRPDF, label: str, value: object, shade: bool = False) -> None:
    """Render a label-value row. Both cells are explicit-width so no overflow."""
    col1 = 52   # label column width mm
    col2 = CONTENT_W - col1  # value column (130 mm)
    # Guard: ensure col2 is always positive
    if col2 <= 0:
        col2 = 80
    fill = (248, 249, 252) if shade else (255, 255, 255)

    # Capture starting Y so we can align both columns
    y_start = pdf.get_y()
    pdf.set_x(L_MARGIN)

    # Measure how many lines the value needs (safe value already stripped)
    safe_value = _safe(value)
    pdf.set_font("Helvetica", "", 9)
    try:
        n_lines = max(1, len(pdf.multi_cell(col2, 6, safe_value, dry_run=True, output="LINES")))
    except Exception:
        n_lines = 1
    row_h = n_lines * 6

    pdf.set_fill_color(*fill)

    # Label cell
    pdf.set_xy(L_MARGIN, y_start)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(col1, row_h, _safe(label), fill=True)

    # Value cell — use explicit width, positioned right after label
    pdf.set_xy(L_MARGIN + col1, y_start)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(30, 30, 30)
    try:
        pdf.multi_cell(col2, 6, safe_value, fill=True)
    except Exception:
        pdf.multi_cell(col2, 6, safe_value[:200] if safe_value else "-", fill=True)

    # Ensure Y is past the row
    if pdf.get_y() < y_start + row_h:
        pdf.set_y(y_start + row_h)


def _embed_image(pdf: APRPDF, data_uri: Optional[str], label: str, x: float, y: float, w: float = 80) -> None:
    """Decode a base64 data URI and embed it at given position."""
    if not data_uri or not data_uri.startswith("data:image"):
        return
    try:
        header, b64data = data_uri.split(",", 1)
        buf = io.BytesIO(base64.b64decode(b64data))
        fmt = "PNG" if "png" in header else "JPEG"
        pdf.set_xy(x, y)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(w, 5, _safe(label), new_x="LMARGIN", new_y="NEXT")
        img_y = pdf.get_y()
        pdf.image(buf, x=x, y=img_y, w=w, type=fmt)
    except Exception:
        pdf.set_xy(x, y)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(w, 5, f"[{_safe(label)}: image unavailable]", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)


def generate_apr_pdf(
    ticket_code: str,
    priority: str,
    department: str,
    ward_id,
    status: str,
    reporter_name: str,
    issue_category: Optional[str],
    description: str,
    created_at: str,
    officer_id: str,
    technician_id: str,
    resolved_at: str,
    verification_verdict: str,
    verification_confidence: str,
    verification_explanation: str,
    before_photo_url: Optional[str] = None,
    after_photo_url: Optional[str] = None,
) -> bytes:
    """Build and return an APR PDF as bytes."""
    pdf = APRPDF()
    pdf.set_margins(L_MARGIN, 34, R_MARGIN)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    generated_at = datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")
    doc_hash = hashlib.sha256(
        f"{ticket_code}-{datetime.utcnow().isoformat()}".encode()
    ).hexdigest()[:12].upper()
    dept_name = DEPT_NAMES.get(str(department), str(department))

    # Strip enum prefix from priority (e.g. "PriorityLabel.HIGH" -> "HIGH")
    pri_key = str(priority).upper()
    for prefix in ("PRIORITYLABEL.", "PRIORITY_LABEL."):
        if prefix in pri_key:
            pri_key = pri_key.split(".")[-1]

    # ── Priority banner ───────────────────────────────────────────────────────
    pri_color = PRIORITY_COLORS.get(pri_key, (100, 100, 100))
    pdf.set_fill_color(*pri_color)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_x(L_MARGIN)
    pdf.cell(CONTENT_W, 10,
             f"  Ticket {_safe(ticket_code)}   [{pri_key} PRIORITY]",
             fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # ── Complaint Details ─────────────────────────────────────────────────────
    _section(pdf, "Complaint Details")
    _row(pdf, "Ticket Code", ticket_code, shade=True)
    _row(pdf, "Department", dept_name)
    _row(pdf, "Category", issue_category or "General", shade=True)
    _row(pdf, "Ward", str(ward_id))
    _row(pdf, "Reporter", reporter_name, shade=True)
    _row(pdf, "Reported On", created_at)
    _row(pdf, "Status", status, shade=True)
    _row(pdf, "Resolved On", resolved_at)
    pdf.ln(5)

    # ── Issue Description ─────────────────────────────────────────────────────
    _section(pdf, "Issue Description")
    pdf.set_x(L_MARGIN)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_fill_color(252, 252, 255)
    pdf.multi_cell(CONTENT_W, 6, _safe(description), fill=True)
    pdf.ln(5)

    # ── Assignment ────────────────────────────────────────────────────────────
    _section(pdf, "Assignment")
    _row(pdf, "Officer ID", officer_id, shade=True)
    _row(pdf, "Field Staff ID", technician_id)
    pdf.ln(5)

    # ── AI Verification ───────────────────────────────────────────────────────
    _section(pdf, "AI Work Verification")
    verdict_color = (
        (40, 167, 69) if "Verified" in str(verification_verdict)
        else (220, 53, 69) if "Failed" in str(verification_verdict)
        else (100, 100, 100)
    )
    pdf.set_x(L_MARGIN)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*verdict_color)
    pdf.cell(CONTENT_W, 7,
             f"  Verdict: {_safe(verification_verdict)}   Confidence: {_safe(verification_confidence)}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_x(L_MARGIN)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_fill_color(245, 245, 255)
    pdf.multi_cell(CONTENT_W, 6, _safe(verification_explanation), fill=True)
    pdf.ln(5)

    # ── Photo Evidence ────────────────────────────────────────────────────────
    if before_photo_url or after_photo_url:
        _section(pdf, "Photo Evidence")
        img_y = pdf.get_y()
        if before_photo_url and after_photo_url:
            _embed_image(pdf, before_photo_url, "Before (Citizen Photo)", x=L_MARGIN, y=img_y, w=80)
            _embed_image(pdf, after_photo_url, "After (Completion Proof)", x=L_MARGIN + 91, y=img_y, w=80)
            pdf.set_y(img_y + 60)
        elif before_photo_url:
            _embed_image(pdf, before_photo_url, "Before (Citizen Photo)", x=L_MARGIN, y=img_y, w=90)
            pdf.ln(60)
        elif after_photo_url:
            _embed_image(pdf, after_photo_url, "After (Completion Proof)", x=L_MARGIN, y=img_y, w=90)
            pdf.ln(60)
        pdf.ln(3)

    # ── Document Hash Footer ──────────────────────────────────────────────────
    pdf.ln(4)
    pdf.set_x(L_MARGIN)
    pdf.set_fill_color(240, 240, 245)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(CONTENT_W, 6,
             f"  Hash: {doc_hash}   |   Generated: {_safe(generated_at)}",
             fill=True, new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
