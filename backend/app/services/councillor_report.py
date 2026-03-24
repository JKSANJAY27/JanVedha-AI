"""
Councillor Ward Executive Report PDF generator using fpdf2.
Generates an official government-grade report for councillors
to present to higher authorities (Zonal Commissioner, State Officials).
"""
from __future__ import annotations
import hashlib
import unicodedata
from datetime import datetime
from typing import Optional, List, Dict, Any

from fpdf import FPDF

PAGE_W = 210
L_MARGIN = 16
R_MARGIN = 16
CONTENT_W = PAGE_W - L_MARGIN - R_MARGIN

# Official government palette
NAVY          = (10, 40, 85)
SAFFRON       = (220, 100, 0)
GOLD          = (185, 140, 20)
DEEP_GREEN    = (0, 110, 60)
LIGHT_NAVY    = (220, 230, 248)
GRAY_BG       = (248, 249, 252)
GRAY_TEXT     = (60, 60, 70)
RED_ALERT     = (190, 35, 45)
GREEN_OK      = (18, 140, 80)
AMBER         = (190, 130, 0)

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


def _section(pdf: "CouncillorPDF", title: str) -> None:
    pdf.ln(2)
    pdf.set_fill_color(*NAVY)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(255, 255, 255)
    pdf.set_x(L_MARGIN)
    pdf.cell(CONTENT_W, 8, f"  {_safe(title).upper()}", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def _kpi_row(pdf: "CouncillorPDF", items: List[Dict]) -> None:
    n = len(items)
    w = CONTENT_W / n - 1.5
    y = pdf.get_y()
    for i, item in enumerate(items):
        x = L_MARGIN + i * (w + 1.5)
        c = item.get("color", NAVY)
        pdf.set_fill_color(*GRAY_BG)
        pdf.rect(x, y, w, 22, "F")
        pdf.set_fill_color(*c)
        pdf.rect(x, y, w, 2.5, "F")
        pdf.set_xy(x, y + 3)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*c)
        pdf.cell(w, 8, _safe(item["value"]), align="C", new_x="RIGHT", new_y="LAST")
        pdf.set_xy(x, y + 12.5)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*GRAY_TEXT)
        pdf.cell(w, 6, _safe(item["label"]), align="C", new_x="RIGHT", new_y="LAST")
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y + 26)


class CouncillorPDF(FPDF):
    def header(self):
        # Triple-stripe top bar: saffron | white | green (national flag inspired)
        self.set_fill_color(*SAFFRON)
        self.rect(0, 0, PAGE_W, 5, "F")
        self.set_fill_color(255, 255, 255)
        self.rect(0, 5, PAGE_W, 4, "F")
        self.set_fill_color(*DEEP_GREEN)
        self.rect(0, 9, PAGE_W, 5, "F")
        # Dark navy body header
        self.set_fill_color(*NAVY)
        self.rect(0, 14, PAGE_W, 18, "F")
        self.set_xy(L_MARGIN, 15)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(255, 255, 255)
        self.cell(CONTENT_W - 50, 7, "WARD CIVIC STATUS REPORT", align="L", new_x="RIGHT", new_y="LAST")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*LIGHT_NAVY)
        self.cell(50, 7, "OFFICIAL DOCUMENT", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_x(L_MARGIN)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(180, 200, 235)
        self.cell(CONTENT_W, 5, "JanVedha AI Civic Platform   |   Government of Tamil Nadu", align="L")
        self.set_text_color(0, 0, 0)
        self.ln(8)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(150, 150, 150)
        self.cell(CONTENT_W, 5,
                  "OFFICIAL USE ONLY — JanVedha AI Civic Platform   |   Page " + str(self.page_no()),
                  align="C")


def generate_councillor_report_pdf(
    ward_id: int,
    ward_label: str,
    councillor_name: str,
    report_period: str,
    # KPIs
    total_tickets: int,
    open_tickets: int,
    closed_tickets: int,
    overdue_tickets: int,
    resolution_rate: float,
    avg_resolution_days: float,
    avg_satisfaction: Optional[float],
    # Priority breakdown
    priority_breakdown: Dict[str, int],
    # Department performance: [{dept_id, total, open, closed, overdue}]
    dept_performance: List[Dict[str, Any]],
    # Top issues: [{category, count, percentage}]
    top_issues: List[Dict[str, Any]],
    # Overdue list: [{ticket_code, issue_category, priority_label, days_overdue, dept_id}]
    overdue_list: List[Dict[str, Any]],
    # AI Briefing text (optional)
    ai_briefing: Optional[str] = None,
) -> bytes:
    pdf = CouncillorPDF()
    pdf.set_margins(L_MARGIN, 36, R_MARGIN)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    generated_at = datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")
    doc_hash = hashlib.sha256(f"councillor-{ward_id}-{generated_at}".encode()).hexdigest()[:12].upper()
    sla_compliance = round((1 - overdue_tickets / max(open_tickets, 1)) * 100, 1)

    # ── DOCUMENT HEADER INFO ─────────────────────────────────────────────────
    pdf.set_fill_color(*LIGHT_NAVY)
    pdf.set_x(L_MARGIN)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*NAVY)
    pdf.cell(CONTENT_W, 9, f"Ward {ward_id} — {_safe(ward_label)}", fill=True,
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(L_MARGIN)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY_TEXT)
    pdf.cell(CONTENT_W / 2, 6, f"Submitted by: {_safe(councillor_name)}", new_x="RIGHT", new_y="LAST")
    pdf.cell(CONTENT_W / 2, 6, f"Reporting Period: {_safe(report_period)}", align="R",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(L_MARGIN)
    pdf.cell(CONTENT_W / 2, 6, "Submitted to: Zonal Commissioner / State Officials", new_x="RIGHT", new_y="LAST")
    pdf.cell(CONTENT_W / 2, 6, f"Date: {datetime.utcnow().strftime('%d %B %Y')}", align="R",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)

    # ── SECTION 1: EXECUTIVE SUMMARY ─────────────────────────────────────────
    _section(pdf, "1. Executive Summary")
    civic_health = "HEALTHY" if resolution_rate >= 70 else "NEEDS IMPROVEMENT"
    health_color = GREEN_OK if resolution_rate >= 70 else RED_ALERT

    summary_lines = [
        f"Ward {ward_id} ({ward_label}) recorded {total_tickets} civic complaints during {report_period}.",
        f"Of these, {closed_tickets} have been resolved, yielding a resolution rate of {resolution_rate:.1f}%.",
        f"The ward civic health status is classified as: {civic_health}.",
        f"Average resolution time stood at {avg_resolution_days} days.",
        f"There are currently {overdue_tickets} tickets in SLA breach, requiring immediate escalation.",
    ]
    if avg_satisfaction:
        summary_lines.append(f"Citizen satisfaction score: {avg_satisfaction}/5.0.")

    pdf.set_x(L_MARGIN)
    # Civic health badge
    pdf.set_fill_color(*health_color)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(255, 255, 255)
    badge_w = 50
    pdf.cell(badge_w, 7, f"  STATUS: {_safe(civic_health)}", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_text_color(0, 0, 0)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY_TEXT)
    pdf.set_x(L_MARGIN)
    for line in summary_lines:
        pdf.multi_cell(CONTENT_W, 6, _safe(line))
    pdf.ln(4)

    # ── SECTION 2: KEY PERFORMANCE INDICATORS ────────────────────────────────
    _section(pdf, "2. Key Performance Indicators")
    _kpi_row(pdf, [
        {"label": "Total Complaints",    "value": str(total_tickets),          "color": NAVY},
        {"label": "Resolved",            "value": str(closed_tickets),         "color": GREEN_OK},
        {"label": "Pending / Open",      "value": str(open_tickets),           "color": AMBER},
        {"label": "SLA Breaches",        "value": str(overdue_tickets),        "color": RED_ALERT},
        {"label": "Resolution Rate",     "value": f"{resolution_rate:.1f}%",   "color": GREEN_OK if resolution_rate >= 70 else RED_ALERT},
    ])
    pdf.set_x(L_MARGIN)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY_TEXT)
    extra = (
        f"Avg. Resolution: {avg_resolution_days} days   |   "
        f"SLA Compliance: {sla_compliance:.1f}%   |   "
        f"Satisfaction: {f'{avg_satisfaction}/5' if avg_satisfaction else 'No data'}"
    )
    pdf.multi_cell(CONTENT_W, 6, _safe(extra), fill=False, align="C")
    pdf.ln(5)

    # ── SECTION 3: DEPARTMENT ACCOUNTABILITY ─────────────────────────────────
    _section(pdf, "3. Department-Wise Accountability")
    col_w = [62, 26, 26, 26, 40]
    headers = ["Department", "Total", "Resolved", "Overdue", "Resolution Rate"]
    pdf.set_fill_color(*NAVY)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_x(L_MARGIN)
    for h, w in zip(headers, col_w):
        pdf.cell(w, 7, h, fill=True, align="C" if h != "Department" else "L", new_x="RIGHT", new_y="LAST")
    pdf.ln(7)
    pdf.set_text_color(0, 0, 0)

    # Sort by worst performing first (highest overdue)
    sorted_depts = sorted(dept_performance, key=lambda d: d.get("overdue", 0), reverse=True)
    for i, dept in enumerate(sorted_depts):
        total = dept.get("total", 0)
        closed = dept.get("closed", 0)
        overdue = dept.get("overdue", 0)
        rate = round(closed / total * 100) if total > 0 else 0
        dept_name = DEPT_NAMES.get(dept.get("dept_id", ""), dept.get("dept_id", "Unknown"))
        fill = GRAY_BG if i % 2 == 0 else (255, 255, 255)
        pdf.set_fill_color(*fill)
        pdf.set_x(L_MARGIN)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*GRAY_TEXT)
        pdf.cell(col_w[0], 6, _safe(dept_name[:30]), fill=True, new_x="RIGHT", new_y="LAST")
        pdf.cell(col_w[1], 6, str(total), fill=True, align="C", new_x="RIGHT", new_y="LAST")
        pdf.cell(col_w[2], 6, str(closed), fill=True, align="C", new_x="RIGHT", new_y="LAST")
        pdf.set_text_color(RED_ALERT[0], RED_ALERT[1], RED_ALERT[2]) if overdue > 0 else pdf.set_text_color(*GRAY_TEXT)
        pdf.cell(col_w[3], 6, str(overdue), fill=True, align="C", new_x="RIGHT", new_y="LAST")
        color = GREEN_OK if rate >= 70 else RED_ALERT
        pdf.set_text_color(*color)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(col_w[4], 6, f"{rate}%", fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    # ── SECTION 4: TOP SYSTEMIC CIVIC ISSUES ─────────────────────────────────
    _section(pdf, "4. Top Systemic Civic Issues")
    for i, issue in enumerate(top_issues[:5], 1):
        cat = issue.get("category", "General")
        cnt = issue.get("count", 0)
        pct = issue.get("percentage", 0)
        pdf.set_x(L_MARGIN)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*SAFFRON)
        pdf.cell(8, 7, f"{i}.", new_x="RIGHT", new_y="LAST")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*GRAY_TEXT)
        pdf.cell(100, 7, _safe(cat), new_x="RIGHT", new_y="LAST")
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*NAVY)
        pdf.cell(30, 7, f"{cnt} complaints", new_x="RIGHT", new_y="LAST")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*GRAY_TEXT)
        pdf.cell(30, 7, f"({pct:.1f}% of total)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    # ── SECTION 5: SLA BREACH ESCALATION LIST ────────────────────────────────
    if overdue_list:
        _section(pdf, f"5. SLA Breach Escalation — {len(overdue_list)} Unresolved Critical Cases")
        pdf.set_x(L_MARGIN)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*GRAY_TEXT)
        pdf.multi_cell(CONTENT_W, 5,
            _safe("The following complaints have exceeded the prescribed Service Level Agreement (SLA) "
                  "window and require immediate departmental escalation. The Councillor urges the concerned "
                  "department heads to expedite resolution within 48 hours."))
        pdf.ln(3)

        col_w2 = [44, 60, 26, 24, 24]
        hdrs2 = ["Ticket No.", "Issue Category", "Priority", "Days OD", "Dept."]
        pdf.set_fill_color(*RED_ALERT)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(255, 255, 255)
        pdf.set_x(L_MARGIN)
        for h, w in zip(hdrs2, col_w2):
            pdf.cell(w, 7, h, fill=True, align="C" if h != "Ticket No." else "L", new_x="RIGHT", new_y="LAST")
        pdf.ln(7)
        pdf.set_text_color(0, 0, 0)

        for i, t in enumerate(overdue_list[:20]):
            fill = (255, 245, 245) if i % 2 == 0 else (255, 255, 255)
            pdf.set_fill_color(*fill)
            pdf.set_x(L_MARGIN)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*RED_ALERT)
            pdf.cell(col_w2[0], 6, _safe(t.get("ticket_code", "—")), fill=True, new_x="RIGHT", new_y="LAST")
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*GRAY_TEXT)
            pdf.cell(col_w2[1], 6, _safe(t.get("issue_category", "General")), fill=True, new_x="RIGHT", new_y="LAST")
            pdf.cell(col_w2[2], 6, _safe(t.get("priority_label", "—")), fill=True, align="C", new_x="RIGHT", new_y="LAST")
            pdf.set_text_color(*RED_ALERT)
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(col_w2[3], 6, str(t.get("days_overdue", "—")), fill=True, align="C", new_x="RIGHT", new_y="LAST")
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*GRAY_TEXT)
            dept_short = DEPT_NAMES.get(str(t.get("dept_id", "")), str(t.get("dept_id", "—")))
            pdf.cell(col_w2[4], 6, _safe(dept_short[:12]), fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)

    # ── SECTION 6: AI WARD BRIEFING (if available) ───────────────────────────
    if ai_briefing and ai_briefing.strip():
        _section(pdf, "6. AI-Assisted Ward Intelligence Briefing")
        pdf.set_x(L_MARGIN)
        pdf.set_fill_color(*GRAY_BG)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*GRAY_TEXT)
        try:
            pdf.multi_cell(CONTENT_W, 5, _safe(ai_briefing[:2000]), fill=True)
        except Exception:
            pdf.multi_cell(CONTENT_W, 5, _safe(ai_briefing[:500]) + "...", fill=True)
        pdf.ln(5)

    # ── SECTION 7: ATTESTATION & SIGNATURE ───────────────────────────────────
    _section(pdf, f"{'7' if ai_briefing and ai_briefing.strip() else '6'}. Attestation & Official Submission")
    pdf.set_x(L_MARGIN)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY_TEXT)
    attest_text = (
        f"I, {_safe(councillor_name)}, Elected Councillor for Ward {ward_id} ({_safe(ward_label)}), "
        "hereby present this civic status report for the period mentioned above, based on data recorded "
        "in the JanVedha AI Civic Management Platform. This report accurately reflects the state of "
        "civic services and grievance redressal in the ward to the best of available data."
    )
    pdf.multi_cell(CONTENT_W, 6, _safe(attest_text))
    pdf.ln(12)

    # Signature blocks
    col = CONTENT_W / 3
    for label, offset in [("Councillor Signature", 0), ("Ward Officer Signature", col), ("Zonal Comm. Signature", 2 * col)]:
        x = L_MARGIN + offset
        pdf.set_draw_color(*NAVY)
        pdf.set_line_width(0.4)
        pdf.line(x, pdf.get_y(), x + col - 6, pdf.get_y())
        pdf.set_xy(x, pdf.get_y() + 1)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*GRAY_TEXT)
        pdf.cell(col - 6, 5, _safe(label), align="C")
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)

    # Date & Seal placeholder
    pdf.set_x(L_MARGIN)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*GRAY_TEXT)
    pdf.cell(CONTENT_W / 2, 6, f"Date: {datetime.utcnow().strftime('%d %B %Y')}")
    pdf.cell(CONTENT_W / 2, 6, "Official Seal / Stamp", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # ── DOCUMENT HASH FOOTER ─────────────────────────────────────────────────
    pdf.set_fill_color(235, 240, 250)
    pdf.set_x(L_MARGIN)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(120, 120, 140)
    pdf.cell(CONTENT_W, 6,
             f"  Hash: {doc_hash}   |   Generated: {_safe(generated_at)}   |   Ward {ward_id}   |   OFFICIAL USE ONLY",
             fill=True, new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
