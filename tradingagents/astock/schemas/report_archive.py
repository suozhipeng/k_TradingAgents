"""Report archive schema — Phase 33 unified report metadata.

Defines a common ``ReportArchive`` schema for all report formats:
Markdown, JSON, PPTX, and Web reports.  Each archive entry carries
metadata for retrieval, comparison, and audit.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ReportFormat(str, Enum):
    """Supported report output formats."""

    MARKDOWN = "markdown"
    JSON = "json"
    PPTX = "pptx"
    WEB = "web"


class ResearchConclusionSummary(BaseModel):
    """Lightweight summary of a research conclusion for archive display."""

    recommendation: str = "N/A"
    confidence: str = "N/A"
    summary: str = ""


class ReportItem(BaseModel):
    """A single archived report entry.

    Attributes
    ----------
    report_id : str
        Unique report identifier.
    report_type : ReportFormat
        Report format (markdown, json, pptx, web).
    symbol : str
        Target stock symbol.
    title : str
        Human-readable report title.
    summary : str
        Short summary / abstract of the report.
    generated_at : str
        ISO timestamp of generation.
    advisory : bool
        Always ``True`` for AI-generated reports in Phase 33.
    content : str, optional
        Full report content (Markdown, JSON string).  Not set for
        binary formats (PPTX).
    content_path : str, optional
        File path or URL to the full report (PPTX, Web).
    research_conclusion : ResearchConclusionSummary, optional
        Key research conclusion if available.
    citations : list[str]
        List of data source citations.
    metadata : dict
        Extensible metadata (model, prompt version, runtime profile,
        source, etc.).
    """

    report_id: str = ""
    report_type: ReportFormat = ReportFormat.JSON
    symbol: str = ""
    title: str = ""
    summary: str = ""
    generated_at: str = ""
    advisory: bool = True
    content: Optional[str] = None
    content_path: Optional[str] = None
    research_conclusion: Optional[ResearchConclusionSummary] = None
    citations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReportArchive(BaseModel):
    """Collection of archived reports — the report centre data model.

    Supports retrieval, comparison, and search across report formats.

    Attributes
    ----------
    symbol : str
        Target stock symbol (empty for portfolio-wide archives).
    reports : list[ReportItem]
        Ordered list of reports (newest first).
    total_count : int
        Total number of reports in the archive.
    last_updated : str
        ISO timestamp of the last archive update.
    """

    symbol: str = ""
    reports: list[ReportItem] = Field(default_factory=list)
    total_count: int = 0
    last_updated: str = ""

    def add_report(self, report: ReportItem) -> None:
        """Add a report and update counters."""
        self.reports.append(report)
        self.total_count = len(self.reports)
        self.last_updated = datetime.now().isoformat()

    @classmethod
    def from_report_data_dict(
        cls,
        symbol: str,
        report_data: dict[str, Any],
        report_id: str | None = None,
    ) -> ReportItem:
        """Build a ``ReportItem`` from the ad-hoc ``report_data`` dict
        used by ``routes_reports.py``.

        Parameters
        ----------
        symbol : str
            Target stock symbol.
        report_data : dict
            The ad-hoc dict with keys like ``summary``,
            ``research_conclusion``, ``investment_plan``, etc.
        report_id : str, optional
            Override report ID (auto-generated if not provided).
        """
        if not report_id:
            import uuid

            report_id = f"rpt-{uuid.uuid4().hex[:12]}"

        conclusion_raw = report_data.get("research_conclusion") or {}
        conclusion = ResearchConclusionSummary(
            recommendation=str(conclusion_raw.get("recommendation", "N/A")),
            confidence=str(conclusion_raw.get("confidence", "N/A")),
            summary=str(conclusion_raw.get("summary", "")),
        )

        metadata = {
            "source": report_data.get("source", "api"),
            "status": report_data.get("status", ""),
            "runtime_profile": str(report_data.get("runtime_profile", "")),
            "investment_plan": str(report_data.get("investment_plan", "")),
        }

        return ReportItem(
            report_id=report_id,
            report_type=ReportFormat.JSON,
            symbol=symbol,
            title=f"{symbol} Research Report",
            summary=str(report_data.get("summary", "")),
            generated_at=datetime.now().isoformat(),
            advisory=True,
            content=None,  # Full content stored separately
            research_conclusion=conclusion,
            metadata=metadata,
        )


__all__ = [
    "ReportFormat",
    "ResearchConclusionSummary",
    "ReportItem",
    "ReportArchive",
]
