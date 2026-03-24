"""
Supervisor Ward Statistics Report PDF generator using fpdf2.
Generates a professional presentation-ready ward report for supervisors.
"""
from __future__ import annotations
import hashlib
import unicodedata
from datetime import datetime
from typing import Optional, List, Dict, Any

from fpdf import FPDF

PAGE_W = 210
L_MARGIN = 14
R_MARGIN = 14
CONTENT_W = PAGE_W - L_MARGIN - R_MARGIN

BRAND_DARK   = (15, 52, 96)
BRAND_MID    = (30, 90, 160)
BRAND_LIGHT  = (210, 230, 250)
ACCENT_GREEN = (22, 160, 90)
ACCENT_RED   = (200, 45, 55)
ACCENT_ORG   = (220, 100, 20)
ACCENT_AMBER = (190, 140, 0)
GRAY_TEXT    = (70, 70, 70)
LIGHT_BG     = (248, 250, 253)

PRIORITY_COLORS: Dict[str, tuple] = {
    "CRITICAL": ACCENT_RED,
    "HIGH":     ACCENT_ORG,
    "MEDIUM":   ACCENT_AMBER,
    "LOW":      ACCENT_GREEN,
}

DEPT_NAMES: Dict[str, str] = {
    "D01": "Roads & Infrastructure",
    "D02": "Water Supply",
    "D03": "Sewage & Drainage",
    "D04": "Solid Waste Management",
    "D05": "Street Lighting",
    "D06": "Parks & Horticulture",
    "D07": "Health & Sanitation",
    "D08": "Education & Libraries",
    "D09": "Fire & Emergency",
    "D10": "Town Planning",
    "D11": "Revenue & Finance",
    "D12": "Social Welfare",
    "D13": "Market & Commerce",
    "D14": "Animal Husbandry",
    "PWD": "Public Works Department",
    "WATER": "Water Supply & Sewerage",
    "ELEC": "Electricity Board",
    "HEALTH": "Health & Sanitation",
    "PARKS": "Parks & Horticulture",
    "STORM": "Storm Water Drains",
    "SOLID_WASTE": "Solid Waste Management",
}


def _safe(text: object) -> str:
    if text is None:
        return "—"
    s = str(text)
    if s.startswith("data:"):
        return "[image data]"
    s = unicodedata.normalize("NFKD", s)
    return s.encode("latin-1", errors="replace").decode("latin-1")


class SupervisorPDF(FPDF):
    def header(self):
        self.set_fill_color(*BRAND_DARK)
        self.rect(0, 0, PAGE_W, 22, "F")
        self.set_fill_color(*BRAND_MID)
        self.rect(0, 22, PAGE_W, 3, "F")
        self.set_xy(L_MARGIN, 5)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(255, 255, 255)
        self.cell(CONTENT_W - 50, 7, "JanVedha Civic Platform", align="L", new_x="RIGHT", new_y="LAST")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(180, 210, 240)
        self.cell(50, 7, "SUPERVISOR REPORT", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_x(L_MARGIN)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(160, 195, 230)
        self.cell(CONTENT_W, 5, "Ward Statistics & Operational Overview — Confidential", align="L", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(4)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(150, 150, 150)
        self.cell(CONTENT_W, 5,
                  "JanVedha AI — Confidential Operational Document   |   Page " + str(self.page_no()),
                  align="C")


def _section_header(pdf: SupervisorPDF, title: str) -> None:
    pdf.set_fill_color(*BRAND_DARK)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(255, 255, 255)
    pdf.set_x(L_MARGIN)
    pdf.cell(CONTENT_W, 8, f"  {_safe(title)}", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def _kpi_boxes(pdf: SupervisorPDF, kpis: List[Dict[str, Any]]) -> None:
    """Render a row of KPI boxes."""
    n = len(kpis)
    box_w = CONTENT_W / n - 1
    x_start = L_MARGIN
    y = pdf.get_y()
    box_h = 20

    for i, kpi in enumerate(kpis):
        x = x_start + i * (box_w + 1)
        label_color = kpi.get("color", BRAND_MID)
        pdf.set_fill_color(*LIGHT_BG)
        pdf.rect(x, y, box_w, box_h, "F")
        pdf.set_draw_color(*label_color)
        pdf.set_line_width(0.6)
        pdf.rect(x, y, box_w, box_h)
        pdf.set_line_width(0.2)
        # Color accent bar top
        pdf.set_fill_color(*label_color)
        pdf.rect(x, y, box_w, 2, "F")
        # Value
        pdf.set_xy(x, y + 3)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*label_color)
        pdf.cell(box_w, 8, _safe(kpi["value"]), align="C", new_x="RIGHT", new_y="LAST")
        # Label
        pdf.set_xy(x, y + 12)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*GRAY_TEXT)
        pdf.cell(box_w, 5, _safe(kpi["label"]), align="C", new_x="RIGHT", new_y="LAST")

    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y + box_h + 4)


def _mini_bar(pdf: SupervisorPDF, label: str, count: int, total: int, color: tuple) -> None:
    x = L_MARGIN
    y = pdf.get_y()
    pct = (count / total * 100) if total > 0 else 0
    bar_max = CONTENT_W - 80

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*GRAY_TEXT)
    pdf.set_xy(x, y)
    pdf.cell(30, 7, _safe(label), new_x="RIGHT", new_y="LAST")

    pdf.set_fill_color(230, 235, 245)
    pdf.rect(x + 32, y + 2, bar_max, 4, "F")
    filled = bar_max * pct / 100
    if filled > 0:
        pdf.set_fill_color(*color)
        pdf.rect(x + 32, y + 2, filled, 4, "F")

    pdf.set_xy(x + 34 + bar_max, y)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(25, 7, f"{count}  ({pct:.0f}%)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)


def _dept_table_row(pdf: SupervisorPDF, dept: str, total: int, closed: int, overdue: int, shade: bool) -> None:
    rate = round(closed / total * 100, 0) if total > 0 else 0
    fill = (248, 250, 253) if shade else (255, 255, 255)
    pdf.set_fill_color(*fill)
    col_w = [60, 28, 28, 28, 38]
    row_h = 6
    y = pdf.get_y()
    pdf.set_xy(L_MARGIN, y)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*GRAY_TEXT)
    for i, (val, w) in enumerate(zip([dept, str(total), str(closed), str(overdue), f"{rate:.0f}%"], col_w)):
        align = "L" if i == 0 else "C"
        if i == 4:
            color = ACCENT_GREEN if rate >= 70 else ACCENT_RED
            pdf.set_text_color(*color)
            pdf.set_font("Helvetica", "B", 8)
        pdf.cell(w, row_h, _safe(val), fill=True, border=0, align=align, new_x="RIGHT", new_y="LAST")
        pdf.set_text_color(*GRAY_TEXT)
        pdf.set_font("Helvetica", "", 8)
    pdf.ln(row_h)


def generate_supervisor_report_pdf(
    ward_id: int,
    ward_label: str,
    supervisor_name: str,
    report_period: str,
    # Main KPIs
    total_tickets: int,
    open_tickets: int,
    closed_tickets: int,
    overdue_tickets: int,
    critical_tickets: int,
    resolution_rate: float,
    avg_resolution_days: float,
    avg_satisfaction: Optional[float],
    # Priority breakdown
    priority_breakdown: Dict[str, int],
    # Department performance list: [{dept_id, total, open, closed, overdue}]
    dept_performance: List[Dict[str, Any]],
    # Top issue categories: [{category, count, percentage}]
    top_issues: List[Dict[str, Any]],
    # Overdue ticket list for escalation table: [{ticket_code, issue_category, priority_label, days_overdue, dept_id}]
    overdue_list: List[Dict[str, Any]],
) -> bytes:
    pdf = SupervisorPDF()
    pdf.set_margins(L_MARGIN, 30, R_MARGIN)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    generated_at = datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")
    doc_hash = hashlib.sha256(f"supervisor-{ward_id}-{generated_at}".encode()).hexdigest()[:12].upper()

    # ── COVER INFO BAR ────────────────────────────────────────────────────────
    pdf.set_fill_color(*BRAND_LIGHT)
    pdf.set_x(L_MARGIN)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*BRAND_DARK)
    pdf.cell(CONTENT_W, 10, f"Ward {ward_id} — {_safe(ward_label)}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(L_MARGIN)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY_TEXT)
    pdf.cell(CONTENT_W / 2, 6, f"Supervisor: {_safe(supervisor_name)}", new_x="RIGHT", new_y="LAST")
    pdf.cell(CONTENT_W / 2, 6, f"Period: {_safe(report_period)}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    # ── SECTION 1: KEY PERFORMANCE INDICATORS ────────────────────────────────
    _section_header(pdf, "KEY PERFORMANCE INDICATORS")
    _kpi_boxes(pdf, [
        {"label": "Total Tickets",    "value": str(total_tickets),             "color": BRAND_MID},
        {"label": "Open",             "value": str(open_tickets),              "color": ACCENT_ORG},
        {"label": "Closed",           "value": str(closed_tickets),            "color": ACCENT_GREEN},
        {"label": "Overdue (SLA)",    "value": str(overdue_tickets),           "color": ACCENT_RED},
        {"label": "Critical",         "value": str(critical_tickets),          "color": ACCENT_RED},
        {"label": "Resolution Rate",  "value": f"{resolution_rate:.1f}%",      "color": ACCENT_GREEN if resolution_rate >= 70 else ACCENT_RED},
    ])

    # Sub-KPIs
    pdf.set_x(L_MARGIN)
    pdf.set_fill_color(*LIGHT_BG)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY_TEXT)
    sub_text = (
        f"Avg. Resolution Time: {avg_resolution_days} days    |    "
        f"Citizen Satisfaction: {f'{avg_satisfaction}/5' if avg_satisfaction else 'No data yet'}    |    "
        f"SLA Target: 70% — {'MET ✓' if resolution_rate >= 70 else 'NOT MET ✗'}"
    )
    pdf.multi_cell(CONTENT_W, 7, _safe(sub_text), fill=True, align="C")
    pdf.ln(6)

    # ── SECTION 2: PRIORITY BREAKDOWN ────────────────────────────────────────
    _section_header(pdf, "PRIORITY BREAKDOWN")
    total_pri = sum(priority_breakdown.values()) or 1
    for p_label, color in [("CRITICAL", ACCENT_RED), ("HIGH", ACCENT_ORG), ("MEDIUM", ACCENT_AMBER), ("LOW", ACCENT_GREEN)]:
        _mini_bar(pdf, p_label, priority_breakdown.get(p_label, 0), total_pri, color)
    pdf.ln(4)

    # ── SECTION 3: DEPARTMENT PERFORMANCE ────────────────────────────────────
    _section_header(pdf, "DEPARTMENT PERFORMANCE TABLE")
    # Table header
    col_w = [60, 28, 28, 28, 38]
    pdf.set_fill_color(*BRAND_DARK)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_x(L_MARGIN)
    for header, w in zip(["Department", "Total", "Closed", "Overdue", "Res. Rate"], col_w):
        pdf.cell(w, 7, header, fill=True, align="C" if header != "Department" else "L", new_x="RIGHT", new_y="LAST")
    pdf.ln(7)
    pdf.set_text_color(0, 0, 0)

    for i, dept in enumerate(dept_performance):
        dept_name = DEPT_NAMES.get(dept.get("dept_id", ""), dept.get("dept_id", "Unknown"))
        _dept_table_row(
            pdf,
            dept_name,
            dept.get("total", 0),
            dept.get("closed", 0),
            dept.get("overdue", 0),
            shade=(i % 2 == 0),
        )
    pdf.ln(6)

    # ── SECTION 4: TOP ISSUE CATEGORIES ──────────────────────────────────────
    _section_header(pdf, "TOP CIVIC ISSUE CATEGORIES")
    for i, issue in enumerate(top_issues[:8], 1):
        pdf.set_x(L_MARGIN)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*GRAY_TEXT)
        pct = issue.get("percentage", 0)
        cat = issue.get("category", "General")
        cnt = issue.get("count", 0)
        pdf.cell(8, 7, f"{i}.", new_x="RIGHT", new_y="LAST")
        pdf.cell(90, 7, _safe(cat), new_x="RIGHT", new_y="LAST")
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*BRAND_MID)
        pdf.cell(30, 7, f"{cnt} tickets", new_x="RIGHT", new_y="LAST")
        pdf.set_text_color(*GRAY_TEXT)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(30, 7, f"({pct:.1f}%)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # ── SECTION 5: SLA BREACH ESCALATION TABLE ────────────────────────────────
    if overdue_list:
        _section_header(pdf, f"SLA BREACH ESCALATION — {len(overdue_list)} TICKETS REQUIRING ATTENTION")
        col_w2 = [45, 55, 28, 26, 28]
        pdf.set_fill_color(*ACCENT_RED)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(255, 255, 255)
        pdf.set_x(L_MARGIN)
        for header, w in zip(["Ticket Code", "Category", "Priority", "Days OD", "Dept"], col_w2):
            pdf.cell(w, 7, header, fill=True, align="C" if header != "Ticket Code" else "L", new_x="RIGHT", new_y="LAST")
        pdf.ln(7)
        pdf.set_text_color(0, 0, 0)
        for i, t in enumerate(overdue_list[:20]):
            fill = (255, 245, 245) if i % 2 == 0 else (255, 255, 255)
            pdf.set_fill_color(*fill)
            pdf.set_x(L_MARGIN)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*ACCENT_RED)
            pdf.cell(45, 6, _safe(t.get("ticket_code", "—")), fill=True, new_x="RIGHT", new_y="LAST")
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*GRAY_TEXT)
            pdf.cell(55, 6, _safe(t.get("issue_category", "General")), fill=True, new_x="RIGHT", new_y="LAST")
            pdf.cell(28, 6, _safe(t.get("priority_label", "—")), fill=True, align="C", new_x="RIGHT", new_y="LAST")
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*ACCENT_RED)
            pdf.cell(26, 6, str(t.get("days_overdue", "—")), fill=True, align="C", new_x="RIGHT", new_y="LAST")
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*GRAY_TEXT)
            dept_short = DEPT_NAMES.get(str(t.get("dept_id", "")), str(t.get("dept_id", "—")))
            pdf.cell(28, 6, _safe(dept_short[:18]), fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)

    # ── DOCUMENT HASH ─────────────────────────────────────────────────────────
    pdf.set_fill_color(240, 242, 248)
    pdf.set_x(L_MARGIN)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(120, 120, 130)
    pdf.cell(CONTENT_W, 6,
             f"  Document Hash: {doc_hash}   |   Generated: {_safe(generated_at)}   |   Ward {ward_id}",
             fill=True, new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
