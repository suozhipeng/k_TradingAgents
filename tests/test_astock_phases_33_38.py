"""Combined Phase 33-38 schema tests — all definition schemas."""
import unittest


class TestPhase33ResearchTask(unittest.TestCase):
    """Phase 33: ResearchTask & ResearchAudit."""

    def setUp(self):
        from pydantic import BaseModel, Field
        from enum import Enum
        from typing import Any, Optional

        class ResearchTaskStatus(str, Enum):
            QUEUED = "queued"; RUNNING = "running"; SUCCESS = "success"
            FAILED = "failed"; CANCELLED = "cancelled"

        class ResearchTask(BaseModel):
            task_id: str = ""; symbols: list[str] = Field(default_factory=list)
            mode: str = "live_research"
            status: ResearchTaskStatus = ResearchTaskStatus.QUEUED
            prompt_version: str = ""; provider: str = ""; model: str = ""
            snapshot: dict = Field(default_factory=dict)
            result: Optional[dict] = None; error: Optional[str] = None

        class ResearchAudit(BaseModel):
            audit_id: str = ""; task_id: str = ""; symbol: str = ""
            model: str = ""; prompt_text: str = ""; prompt_version: str = ""
            input_snapshot: dict = Field(default_factory=dict)
            output_summary: str = ""; citations: list[str] = Field(default_factory=list)
            advisory: bool = True; generated_at: str = ""

        self.ResearchTask = ResearchTask
        self.ResearchAudit = ResearchAudit
        self.ResearchTaskStatus = ResearchTaskStatus

    def test_task_defaults(self):
        t = self.ResearchTask()
        self.assertEqual(t.status, self.ResearchTaskStatus.QUEUED)
        self.assertEqual(t.mode, "live_research")
        self.assertEqual(t.symbols, [])

    def test_task_symbols(self):
        t = self.ResearchTask(symbols=["600519.SH", "000858.SZ"])
        self.assertEqual(len(t.symbols), 2)
        self.assertIn("600519.SH", t.symbols)

    def test_audit_advisory_true(self):
        a = self.ResearchAudit()
        self.assertTrue(a.advisory)

    def test_audit_has_citations(self):
        a = self.ResearchAudit(citations=["src1", "src2"])
        self.assertEqual(len(a.citations), 2)


class TestPhase35Order(unittest.TestCase):
    """Phase 35: Order, Fill, Position, Reconciliation."""

    def setUp(self):
        from pydantic import BaseModel, Field
        from enum import Enum
        from typing import Optional

        class OrderStatus(str, Enum):
            CREATED = "created"; SUBMITTED = "submitted"; CONFIRMED = "confirmed"
            PARTIAL_FILLED = "partial_filled"; FILLED = "filled"
            CANCELLED = "cancelled"; REJECTED = "rejected"; EXPIRED = "expired"; ERROR = "error"

        class OrderSide(str, Enum): BUY = "buy"; SELL = "sell"
        class OrderTradeMode(str, Enum): PAPER = "paper"; MANAGED = "managed"; LIVE_READY = "live-ready"

        class Order(BaseModel):
            order_id: str = ""; broker_order_id: Optional[str] = None
            mode: OrderTradeMode = OrderTradeMode.PAPER
            symbol: str = ""; side: OrderSide = OrderSide.BUY
            quantity: float = 0.0; price: float = 0.0
            status: OrderStatus = OrderStatus.CREATED

        class Fill(BaseModel):
            fill_id: str = ""; order_id: str = ""; symbol: str = ""
            side: OrderSide = OrderSide.BUY
            quantity: float = 0.0; price: float = 0.0; fees: float = 0.0; timestamp: str = ""

        class Position(BaseModel):
            symbol: str = ""; quantity: float = 0.0; avg_cost: float = 0.0
            current_price: float = 0.0; market_value: float = 0.0; pnl: float = 0.0; pnl_pct: float = 0.0

        class Reconciliation(BaseModel):
            symbol: str = ""; local_quantity: float = 0.0; external_quantity: float = 0.0
            local_cost: float = 0.0; external_cost: float = 0.0
            matched: bool = False; discrepancy: float = 0.0; notes: str = ""

        self.Order = Order
        self.Fill = Fill
        self.Position = Position
        self.Reconciliation = Reconciliation
        self.OrderStatus = OrderStatus

    def test_order_default_paper(self):
        o = self.Order()
        self.assertEqual(o.mode.value, "paper")
        self.assertEqual(o.status, self.OrderStatus.CREATED)

    def test_order_full_status_cycle(self):
        for st in self.OrderStatus:
            o = self.Order(status=st)
            self.assertEqual(o.status, st)

    def test_fill_partial(self):
        f = self.Fill(quantity=100.0, price=10.5, fees=1.0)
        self.assertEqual(f.quantity, 100.0)

    def test_position_pnl(self):
        p = self.Position(symbol="600519.SH", pnl=500.0, pnl_pct=5.0)
        self.assertEqual(p.pnl, 500.0)

    def test_reconciliation_mismatch(self):
        r = self.Reconciliation(symbol="A", local_quantity=100, external_quantity=90, matched=False, discrepancy=10)
        self.assertFalse(r.matched)
        self.assertEqual(r.discrepancy, 10)


class TestPhase36Portfolio(unittest.TestCase):
    """Phase 36: Portfolio, RiskExposure, Attribution."""

    def setUp(self):
        from pydantic import BaseModel, Field

        class Position(BaseModel):
            symbol: str = ""; quantity: float = 0.0; avg_cost: float = 0.0
            current_price: float = 0.0; market_value: float = 0.0; pnl: float = 0.0; pnl_pct: float = 0.0

        class Portfolio(BaseModel):
            portfolio_id: str = ""
            holdings: list[Position] = Field(default_factory=list)
            cash: float = 0.0; nav: float = 0.0; pnl_total: float = 0.0; last_updated: str = ""

        class RiskExposure(BaseModel):
            industry_concentration: float = 0.0; top_holding_pct: float = 0.0
            beta: float = 0.0; liquidity_score: float = 0.0; var_95: float = 0.0
            max_drawdown: float = 0.0; stress_loss_pct: float = 0.0

        class Attribution(BaseModel):
            benchmark_return: float = 0.0; selection_effect: float = 0.0
            timing_effect: float = 0.0; cost_impact: float = 0.0; slippage_impact: float = 0.0; residual: float = 0.0

        self.Portfolio = Portfolio
        self.RiskExposure = RiskExposure
        self.Attribution = Attribution
        self.Position = Position

    def test_portfolio_with_holdings(self):
        p = self.Portfolio(holdings=[self.Position(symbol="A")])
        self.assertEqual(len(p.holdings), 1)

    def test_risk_exposure_defaults(self):
        r = self.RiskExposure()
        self.assertEqual(r.var_95, 0.0)

    def test_attribution_fields(self):
        a = self.Attribution(selection_effect=2.5, timing_effect=-1.2)
        self.assertEqual(a.selection_effect, 2.5)


class TestPhase37TaskRun(unittest.TestCase):
    """Phase 37: TaskRun, AuditEvent."""

    def setUp(self):
        from pydantic import BaseModel, Field
        from enum import Enum
        from typing import Any, Optional

        class TaskType(str, Enum):
            DATA_REFRESH = "data_refresh"; RESEARCH = "research"; BACKTEST = "backtest"
            REPORT = "report"; TRADE = "trade"

        class TaskRun(BaseModel):
            task_id: str = ""; task_type: TaskType = TaskType.DATA_REFRESH
            status: str = "queued"; progress: float = 0.0
            started_at: Optional[str] = None; finished_at: Optional[str] = None
            error: Optional[dict] = None; result: Optional[dict] = None

        class AuditEvent(BaseModel):
            event_id: str = ""; actor: str = ""; action: str = ""
            input_snapshot: dict = Field(default_factory=dict)
            output_snapshot: dict = Field(default_factory=dict)
            model: Optional[str] = None
            confirmation_required: bool = False; confirmed_by: Optional[str] = None
            created_at: str = ""

        self.TaskRun = TaskRun
        self.AuditEvent = AuditEvent

    def test_task_run_defaults(self):
        t = self.TaskRun()
        self.assertEqual(t.status, "queued")

    def test_task_run_progress(self):
        t = self.TaskRun(progress=50.0, status="running")
        self.assertEqual(t.progress, 50.0)

    def test_audit_event_actor(self):
        a = self.AuditEvent(actor="system", action="data_refresh")
        self.assertEqual(a.actor, "system")

    def test_audit_confirmation(self):
        a = self.AuditEvent(confirmation_required=True, confirmed_by="user1")
        self.assertTrue(a.confirmation_required)


class TestPhase34LeaderPool(unittest.TestCase):
    """Phase 34: LeaderPoolEntry."""

    def setUp(self):
        from pydantic import BaseModel, Field
        from typing import Any, Optional

        class LeaderPoolEntry(BaseModel):
            symbol: str = ""; name: str = ""; reason: str = ""
            score: float = 0.0; source: str = ""
            refreshed_at: str = ""; entry_reason: str = ""
            exit_reason: Optional[str] = None
            extra: dict[str, Any] = Field(default_factory=dict)

        self.LeaderPoolEntry = LeaderPoolEntry

    def test_entry_defaults(self):
        e = self.LeaderPoolEntry(symbol="600519.SH", reason="dragon_tiger")
        self.assertEqual(e.reason, "dragon_tiger")

    def test_exit_reason(self):
        e = self.LeaderPoolEntry(symbol="A", reason="test",
            exit_reason="score_dropped")
        self.assertEqual(e.exit_reason, "score_dropped")


if __name__ == "__main__":
    unittest.main()
