"""PPTX report generator for AStockGraphReport — Phase 17.

Generates a PowerPoint deck with:
1. Cover slide (symbol, trade_date, runtime_profile)
2. Research Conclusion (recommendation, confidence, summary)
3. Advisory Chain (TraderProposal, RiskDecision, PortfolioDecision)
4. Provider Coverage (table)
5. Runtime Trace (timeline)

python-pptx is OPTIONAL — if not installed, ``to_pptx()`` raises ImportError
with a clear message.  Use ``has_pptx`` to check availability at call sites.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

try:
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

    HAS_PPTX = True
except ImportError:
    HAS_PPTX = False

# ---------------------------------------------------------------------------
# Colour palette (dark theme — close to the WebUI look)
# ---------------------------------------------------------------------------

BG_DARK = RGBColor(0x0F, 0x17, 0x2A)
BG_CARD = RGBColor(0x1E, 0x29, 0x3B)
TEXT_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
TEXT_GRAY = RGBColor(0xCA, 0xCA, 0xCA)
ACCENT_INDIGO = RGBColor(0x63, 0x66, 0xF1)
ACCENT_EMERALD = RGBColor(0x34, 0xD3, 0x99)
ACCENT_AMBER = RGBColor(0xFB, 0xBD, 0x23)
ACCENT_RED = RGBColor(0xF8, 0x71, 0x71)
ACCENT_SKY = RGBColor(0x38, 0xBD, 0xF8)

if HAS_PPTX:

    def _add_bg(slide, color: RGBColor = BG_DARK) -> None:
        """Set the slide background to a solid colour."""
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = color

    def _add_text_box(
        slide,
        left: float,
        top: float,
        width: float,
        height: float,
        text: str,
        font_size: int = 14,
        bold: bool = False,
        color: RGBColor = TEXT_WHITE,
        alignment: int = PP_ALIGN.LEFT,
    ) -> None:
        """Add a text box to a slide (coordinates in inches)."""
        txBox = slide.shapes.add_textbox(
            Inches(left), Inches(top), Inches(width), Inches(height)
        )
        tf = txBox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = text
        p.font.size = Pt(font_size)
        p.font.bold = bold
        p.font.color.rgb = color
        p.alignment = alignment

    def _add_table(
        slide,
        left: float,
        top: float,
        width: float,
        height: float,
        rows: int,
        cols: int,
        data: list[list[str]],
        header: bool = True,
    ) -> None:
        """Add a table slide shape."""
        table_shape = slide.shapes.add_table(
            rows, cols, Inches(left), Inches(top), Inches(width), Inches(height)
        )
        table = table_shape.table

        for r_idx, row_data in enumerate(data):
            for c_idx, cell_text in enumerate(row_data):
                cell = table.cell(r_idx, c_idx)
                cell.text = str(cell_text)
                for paragraph in cell.text_frame.paragraphs:
                    paragraph.font.size = Pt(11)
                    paragraph.font.color.rgb = TEXT_WHITE if (header and r_idx == 0) else TEXT_GRAY
                    if header and r_idx == 0:
                        paragraph.font.bold = True

    def _add_bullet_list(
        slide,
        left: float,
        top: float,
        width: float,
        height: float,
        items: list[str],
        font_size: int = 12,
        color: RGBColor = TEXT_GRAY,
    ) -> None:
        """Add a bulleted list text box."""
        txBox = slide.shapes.add_textbox(
            Inches(left), Inches(top), Inches(width), Inches(height)
        )
        tf = txBox.text_frame
        tf.word_wrap = True

        for i, item in enumerate(items):
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = f"• {item}"
            p.font.size = Pt(font_size)
            p.font.color.rgb = color
            p.space_after = Pt(4)


# ===================================================================
# Public API
# ===================================================================


class ReportGenerator:
    """Generate PowerPoint (.pptx) reports from AStockGraphReport data."""

    def __init__(self) -> None:
        if not HAS_PPTX:
            raise ImportError(
                "python-pptx is not installed. "
                "Install it with: pip install python-pptx"
            )

    # ------------------------------------------------------------------
    # Public method
    # ------------------------------------------------------------------

    def to_pptx(self, report: dict, output_path: str) -> str:
        """Generate a PowerPoint report from an AStockGraphReport dict.

        Parameters
        ----------
        report : dict
            An ``AStockGraphReport`` dict (from ``to_dict()`` or API JSON).
        output_path : str
            Path to write the ``.pptx`` file.

        Returns
        -------
        str
            ``output_path`` on success.
        """
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

        # Slide 1: Cover
        self._slide_cover(prs, report)
        # Slide 2: Research Conclusion
        self._slide_research_conclusion(prs, report)
        # Slide 3: Advisory Chain
        self._slide_advisory_chain(prs, report)
        # Slide 4: Provider Coverage
        self._slide_provider_coverage(prs, report)
        # Slide 5: Runtime Trace
        self._slide_runtime_trace(prs, report)

        prs.save(output_path)
        logger.info("PPTX report saved to %s", output_path)
        return output_path

    # ------------------------------------------------------------------
    # Private slide builders
    # ------------------------------------------------------------------

    def _slide_cover(self, prs: Presentation, report: dict) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
        _add_bg(slide, BG_DARK)

        symbol = report.get("symbol", "N/A")
        trade_date = report.get("trade_date", "N/A")
        profile = report.get("runtime_profile", "N/A")

        _add_text_box(slide, 1.0, 1.5, 11.0, 1.5, "AStock Research Report", 36, True, ACCENT_INDIGO, PP_ALIGN.CENTER)
        _add_text_box(slide, 1.0, 3.2, 11.0, 0.6, f"Symbol: {symbol}", 24, False, TEXT_WHITE, PP_ALIGN.CENTER)
        _add_text_box(slide, 1.0, 3.9, 11.0, 0.5, f"Trade Date: {trade_date}", 18, False, TEXT_GRAY, PP_ALIGN.CENTER)
        _add_text_box(slide, 1.0, 4.5, 11.0, 0.5, f"Runtime Profile: {profile}", 16, False, TEXT_GRAY, PP_ALIGN.CENTER)
        _add_text_box(slide, 1.0, 5.5, 11.0, 0.5, f"Status: {report.get('status', 'N/A')}", 14, False, ACCENT_EMERALD, PP_ALIGN.CENTER)

    def _slide_research_conclusion(self, prs: Presentation, report: dict) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        _add_bg(slide, BG_DARK)
        _add_text_box(slide, 0.5, 0.3, 12.0, 0.6, "Research Conclusion", 28, True, ACCENT_SKY)

        conclusion = report.get("research_conclusion") or {}
        rec = conclusion.get("recommendation", "N/A")
        conf = conclusion.get("confidence", "N/A")
        summary = conclusion.get("summary", report.get("summary", "N/A"))

        items = [
            f"Recommendation: {rec}",
            f"Confidence: {conf}",
        ]
        _add_bullet_list(slide, 0.5, 1.2, 12.0, 1.5, items, 16, TEXT_WHITE)

        _add_text_box(slide, 0.5, 2.8, 12.0, 0.4, "Summary", 20, True, ACCENT_INDIGO)
        _add_text_box(slide, 0.5, 3.3, 12.0, 3.0, summary, 14, False, TEXT_GRAY)

        # Investment plan
        inv_plan = report.get("investment_plan", "")
        if inv_plan:
            _add_text_box(slide, 0.5, 5.5, 12.0, 0.3, "Investment Plan", 18, True, ACCENT_EMERALD)
            _add_text_box(slide, 0.5, 5.9, 12.0, 1.5, inv_plan, 13, False, TEXT_GRAY)

    def _slide_advisory_chain(self, prs: Presentation, report: dict) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        _add_bg(slide, BG_DARK)
        _add_text_box(slide, 0.5, 0.3, 12.0, 0.6, "Advisory Chain", 28, True, ACCENT_AMBER)

        y = 1.2
        sections = [
            ("Trader Proposal", report.get("trader_proposal")),
            ("Risk Decision", report.get("risk_decision")),
            ("Portfolio Decision", report.get("portfolio_decision")),
        ]

        for title, data in sections:
            if data and isinstance(data, dict):
                _add_text_box(slide, 0.5, y, 12.0, 0.4, title, 18, True, ACCENT_SKY)
                y += 0.45
                lines = [f"{k}: {v}" for k, v in data.items() if v]
                _add_bullet_list(slide, 0.5, y, 12.0, 0.8, lines[:6], 12, TEXT_GRAY)
                y += 1.2
            else:
                _add_text_box(slide, 0.5, y, 12.0, 0.3, f"{title}: N/A", 14, False, TEXT_GRAY)
                y += 0.4

    def _slide_provider_coverage(self, prs: Presentation, report: dict) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        _add_bg(slide, BG_DARK)
        _add_text_box(slide, 0.5, 0.3, 12.0, 0.6, "Provider Coverage", 28, True, ACCENT_EMERALD)

        coverage = report.get("provider_coverage") or {}
        if coverage:
            headers = ["Provider", "Status", "Source", "Records"]
            rows = [headers]
            for provider, info in coverage.items():
                if isinstance(info, dict):
                    rows.append([
                        str(provider),
                        str(info.get("status", "?")),
                        str(info.get("source", "?")),
                        str(info.get("records", info.get("count", "?"))),
                    ])
                else:
                    rows.append([str(provider), str(info), "", ""])
            _add_table(slide, 0.5, 1.2, 12.0, 0.4 * len(rows), len(rows), 4, rows)
        else:
            _add_text_box(slide, 0.5, 1.2, 12.0, 0.5, "No provider coverage data available.", 14, False, TEXT_GRAY)

        # Missing data notes
        missing = report.get("missing_data_notes", [])
        if missing:
            _add_text_box(slide, 0.5, 4.0, 12.0, 0.3, "Missing Data Notes", 18, True, ACCENT_RED)
            _add_bullet_list(slide, 0.5, 4.4, 12.0, 2.0, missing[:8], 12, TEXT_GRAY)

        # Degradation notes
        degraded = report.get("degradation_notes", [])
        if degraded:
            _add_text_box(slide, 0.5, 5.5, 12.0, 0.3, "Degradation Notes", 18, True, ACCENT_AMBER)
            _add_bullet_list(slide, 0.5, 5.9, 12.0, 1.5, degraded[:6], 12, TEXT_GRAY)

    def _slide_runtime_trace(self, prs: Presentation, report: dict) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        _add_bg(slide, BG_DARK)
        _add_text_box(slide, 0.5, 0.3, 12.0, 0.6, "Runtime Trace", 28, True, ACCENT_SKY)

        trace = report.get("runtime_trace", [])
        if trace:
            # Limit to 30 entries to avoid text overflow
            items = trace[:30]
            _add_bullet_list(slide, 0.5, 1.2, 12.0, 5.5, items, 11, TEXT_GRAY)
            if len(trace) > 30:
                _add_text_box(slide, 0.5, 6.8, 12.0, 0.3, f"... and {len(trace) - 30} more entries", 11, False, TEXT_GRAY)
        else:
            _add_text_box(slide, 0.5, 1.2, 12.0, 0.5, "No runtime trace available.", 14, False, TEXT_GRAY)


__all__ = ["ReportGenerator", "HAS_PPTX"]
