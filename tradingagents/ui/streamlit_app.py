from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from tradingagents.astock import AStockGraphRuntime

from .dispatcher import render_report_page


def _load_json_payload(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(st: Any | None = None) -> None:
    """Launch the read-only report viewer.

    This entrypoint is intentionally display-only: it can load an existing
    `AStockGraphReport` payload from JSON or materialize one through the
    read-only A 股 runtime, then hand the stable schema to the shared
    renderer.
    """
    if st is None:
        try:
            import streamlit as st  # type: ignore[no-redef]
        except Exception as exc:  # pragma: no cover - optional dependency boundary
            raise RuntimeError(
                "streamlit is not installed. Install the optional 'ui' extra to run the web viewer."
            ) from exc

    st.set_page_config(page_title="TradingAgents Multi-Market Viewer", layout="wide")
    st.title("TradingAgents Multi-Market Viewer")
    st.caption("Read-only display layer for AStockGraphReport and legacy TradingAgents outputs")

    source_mode = st.sidebar.selectbox("Report source", ["Live A 股 runtime", "JSON payload (A 股 or legacy)"])
    payload = None

    if source_mode == "Live A 股 runtime":
        symbol = st.sidebar.text_input("Symbol", value="600519.SH")
        trade_date = st.sidebar.text_input("Trade date", value=date.today().isoformat())
        if st.sidebar.button("Generate report"):
            runtime = AStockGraphRuntime(symbol=symbol, trade_date=trade_date, source="ui")
            payload = runtime.run()
        else:
            st.info("Click Generate report to load the read-only A 股 view.")
            return
    else:
        upload = st.sidebar.file_uploader("Upload A 股 report JSON", type=["json"])
        if upload is not None:
            payload = json.loads(upload.read().decode("utf-8"))
        else:
            text = st.sidebar.text_area("Paste report JSON", height=240)
            if text.strip():
                payload = json.loads(text)
            else:
                st.info("Upload or paste an AStockGraphReport JSON payload.")
                return

    render_report_page(st, payload)


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    main()
