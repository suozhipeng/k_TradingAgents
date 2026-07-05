"""Portfolio risk calculation engine — VaR, exposure, attribution, summary.

Split from the original ``portfolio_risk.py`` into focused sub-modules:

- ``var`` — Parametric Value-at-Risk computation
- ``exposure`` — Industry exposure analysis
- ``attribution`` — Brinson-style performance attribution
- ``summary`` — Aggregate risk exposure summary
"""

from __future__ import annotations

from .var import calculate_var
from .exposure import calculate_industry_exposure
from .attribution import calculate_attribution
from .summary import calculate_risk_exposure

__all__ = [
    "calculate_var",
    "calculate_industry_exposure",
    "calculate_attribution",
    "calculate_risk_exposure",
]
