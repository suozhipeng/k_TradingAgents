import json
import unittest
from contextlib import contextmanager
from dataclasses import asdict
from unittest import mock

import pytest

from tradingagents.astock import AStockGraphReport
from tradingagents.ui.astock_views import (
    ASTOCK_SECTION_ORDER,
    build_astock_ui_model,
    is_astock_report_payload,
    render_astock_report_page,
    render_report_page,
)
from tradingagents.ui import streamlit_app


class FakeExpander:
    def __init__(self, label, expanded=False):
        self.label = label
        self.expanded = expanded

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeColumn:
    def __init__(self, owner, idx):
        self.owner = owner
        self.idx = idx

    def metric(self, label, value):
        self.owner.metrics.append((self.idx, label, value))


class FakeSidebar:
    def __init__(self, mode="Live A 股 runtime", live_button=True, symbol="600519.SH", trade_date="2026-06-10", json_text=""):
        self.mode = mode
        self.live_button = live_button
        self.symbol = symbol
        self.trade_date = trade_date
        self.json_text = json_text
        self.upload = None

    def selectbox(self, label, options):
        return self.mode

    def text_input(self, label, value=""):
        if "Symbol" in label:
            return self.symbol
        if "Trade date" in label:
            return self.trade_date
        return value

    def button(self, label):
        return self.live_button

    def file_uploader(self, label, type=None):
        return self.upload

    def text_area(self, label, height=240):
        return self.json_text


class FakeStreamlit:
    def __init__(self, sidebar: FakeSidebar | None = None):
        self.sidebar = sidebar or FakeSidebar()
        self.calls = []
        self.metrics = []
        self.tables = []
        self.warnings = []
        self.infos = []
        self.json_payloads = []
        self.titles = []
        self.captions = []
        self.subheaders = []
        self.markdowns = []
        self.writes = []

    def set_page_config(self, **kwargs):
        self.calls.append(("set_page_config", kwargs))

    def title(self, value):
        self.titles.append(value)

    def caption(self, value):
        self.captions.append(value)

    def subheader(self, value):
        self.subheaders.append(value)

    def table(self, value):
        self.tables.append(value)

    def markdown(self, value):
        self.markdowns.append(value)

    def write(self, value):
        self.writes.append(value)

    def warning(self, value):
        self.warnings.append(value)

    def info(self, value):
        self.infos.append(value)

    def json(self, value):
        self.json_payloads.append(value)

    def columns(self, count):
        return [FakeColumn(self, idx) for idx in range(count)]

    def expander(self, label, expanded=False):
        self.calls.append(("expander", label, expanded))
        return FakeExpander(label, expanded)


@pytest.mark.unit
class TestAStockUiViews(unittest.TestCase):
    def _make_report(self, status="partial", missing_research=True):
        return AStockGraphReport(
            symbol="600519.SH",
            normalized_symbol="600519.SH",
            trade_date="2026-06-10",
            source="ui",
            sections_requested=ASTOCK_SECTION_ORDER,
            astock_analysis={
                "symbol": "600519.SH",
                "normalized_symbol": "600519.SH",
                "summary": "A-share payload ready for UI",
                "missing_sections": ["research"] if missing_research else [],
            },
            astock_sections={
                "market": {"status": "ok", "source": "market", "summary": "market ok", "data": [1]},
                "news": {"status": "ok", "source": "news", "summary": "news ok", "data": [1]},
                "fundamentals": {"status": "ok", "source": "fundamentals", "summary": "fundamentals ok", "data": {"fields": 37}},
                "announcements": {"status": "error", "source": "cninfo", "summary": "cninfo unavailable", "error": "missing"},
                "research": {"status": "empty", "source": "iwencai", "summary": "cookie missing", "error": "ASTOCK_IWENCAI_COOKIE not configured"},
            },
            section_results={
                "market": {"status": "ok", "source": "market", "summary": "market ok", "has_data": True},
                "news": {"status": "ok", "source": "news", "summary": "news ok", "has_data": True},
                "fundamentals": {"status": "ok", "source": "fundamentals", "summary": "fundamentals ok", "has_data": True},
                "announcements": {"status": "error", "source": "cninfo", "summary": "cninfo unavailable", "has_data": False},
                "research": {"status": "empty", "source": "iwencai", "summary": "cookie missing", "has_data": False},
            },
            bull_view="Bull: positive cash flow and scale.",
            bear_view="Bear: policy and margin risk.",
            research_manager_conclusion="**Recommendation**: Hold",
            provider_coverage={
                "market": {"source": "market", "status": "ok", "available": True},
                "news": {"source": "news", "status": "ok", "available": True},
                "fundamentals": {"source": "fundamentals", "status": "ok", "available": True},
                "announcements": {"source": "cninfo", "status": "error", "available": False},
                "research": {"source": "iwencai", "status": "empty", "available": False},
            },
            missing_data_notes=["research: ASTOCK_IWENCAI_COOKIE not configured"],
            degradation_notes=["research [empty]: ASTOCK_IWENCAI_COOKIE not configured"],
            bull_output={"investment_debate_state": {"bull_history": "Bull: positive cash flow and scale."}},
            bear_output={"investment_debate_state": {"bear_history": "Bear: policy and margin risk."}},
            research_manager_output={"investment_plan": "**Recommendation**: Hold"},
            investment_plan="**Recommendation**: Hold",
            runtime_trace=("AStock Analyst", "Bull Researcher", "Bear Researcher", "Research Manager"),
            llm_prompts={"bull": ["bull prompt"], "bear": ["bear prompt"], "research_manager": ["mgr prompt"]},
            summary="A-share payload ready for UI",
            status=status,
            metadata={"bridge_mode": "astock_research_bridge"},
        )

    def test_build_astock_ui_model_preserves_display_schema(self):
        report = self._make_report()
        model = build_astock_ui_model(report)

        self.assertEqual(model.ticker, "600519.SH")
        self.assertEqual(model.runtime_mode, "astock_research_bridge")
        self.assertEqual(model.status, "partial")
        self.assertEqual(len(model.section_rows), len(ASTOCK_SECTION_ORDER))
        self.assertEqual(model.section_rows[0].name, "market")
        self.assertTrue(model.section_rows[0].has_data)
        self.assertEqual(model.provider_rows[-1]["section"], "research")
        self.assertIn("ASTOCK_IWENCAI_COOKIE", model.missing_data_notes[0])
        self.assertEqual(model.analyst_summary, "A-share payload ready for UI")

    def test_render_astock_report_page_renders_read_only_sections(self):
        report = self._make_report()
        st = FakeStreamlit()

        model = render_astock_report_page(st, report)
        self.assertEqual(model.ticker, "600519.SH")
        self.assertIn("A 股 Analysis Report · 600519.SH", st.titles)
        self.assertIn("Five-layer Section Status", st.subheaders)
        self.assertGreaterEqual(len(st.tables), 2)
        self.assertIn((0, "Ticker", "600519.SH"), st.metrics)
        self.assertIn("A-share payload ready for UI", st.markdowns)
        self.assertIn("Bull: positive cash flow and scale.", st.markdowns)
        self.assertIn("Bear: policy and margin risk.", st.markdowns)
        self.assertIn("**Recommendation**: Hold", st.markdowns)
        self.assertTrue(any("ASTOCK_IWENCAI_COOKIE" in item for item in st.warnings))
        self.assertTrue(st.json_payloads)
        self.assertEqual(st.json_payloads[0]["ticker"], "600519.SH")

    def test_render_report_page_dispatches_astock_and_legacy(self):
        report = self._make_report()
        st = FakeStreamlit()
        legacy_renderer = mock.Mock(return_value={"mode": "legacy"})

        astock_result = render_report_page(st, report, legacy_renderer=legacy_renderer)
        self.assertEqual(astock_result.ticker, "600519.SH")
        legacy_renderer.assert_not_called()

        legacy_payload = {"mode": "global", "summary": "legacy"}
        legacy_result = render_report_page(st, legacy_payload, legacy_renderer=legacy_renderer)
        self.assertEqual(legacy_result, {"mode": "legacy"})
        legacy_renderer.assert_called_once_with(st, legacy_payload)

    def test_streamlit_main_live_runtime_and_json_payload(self):
        fake_report = self._make_report()
        live_sidebar = FakeSidebar(mode="Live A 股 runtime", live_button=True)
        live_st = FakeStreamlit(sidebar=live_sidebar)

        with mock.patch.object(streamlit_app, "AStockGraphRuntime") as runtime_cls, \
             mock.patch.object(streamlit_app, "render_report_page") as render_page:
            runtime = mock.Mock()
            runtime.run.return_value = fake_report
            runtime_cls.return_value = runtime
            render_page.return_value = None
            streamlit_app.main(st=live_st)

        runtime_cls.assert_called_once_with(symbol="600519.SH", trade_date="2026-06-10", source="ui")
        render_page.assert_called_once()
        self.assertEqual(render_page.call_args.args[1].ticker, "600519.SH")

        json_payload = json.dumps(fake_report.to_dict(), ensure_ascii=False)
        json_sidebar = FakeSidebar(mode="JSON payload", json_text=json_payload)
        json_st = FakeStreamlit(sidebar=json_sidebar)
        with mock.patch.object(streamlit_app, "render_report_page") as render_page_json:
            render_page_json.return_value = None
            streamlit_app.main(st=json_st)

        render_page_json.assert_called_once()
        self.assertEqual(render_page_json.call_args.args[1]["ticker"], "600519.SH")

    def test_is_astock_report_payload_detects_mode(self):
        self.assertTrue(is_astock_report_payload(self._make_report()))
        self.assertTrue(is_astock_report_payload({"mode": "astock_research_bridge"}))
        self.assertFalse(is_astock_report_payload({"mode": "global"}))


if __name__ == "__main__":
    unittest.main()
