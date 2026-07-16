"""Paper trade scheduler — APScheduler-based periodic cycle executor.

Replaces the earlier threading.Timer implementation with APScheduler
for richer lifecycle management (pause/resume, cron expressions, misfire
grace time).

Public API
----------
- start() / stop() / pause() / resume()
- running / paused / cycle_count properties
- add_cron_job(hour, minute, ...) for user-configurable schedules
- add_interval_job() / remove_job() / list_jobs() for full job CRUD

Configuration (via environment variables or app config)
-------------------------------------------------------
- ASTOCK_SCHEDULER_ENABLED      — "true"/"false" (default: true)
- ASTOCK_SCHEDULER_INTERVAL_MIN — interval in minutes (default: 30)
- ASTOCK_SCHEDULER_SYMBOLS      — comma-separated symbols
- ASTOCK_SCHEDULER_STRATEGIES   — comma-separated strategy names
"""

from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime
from typing import Any, Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from tradingagents.astock.time_utils import utc_now_iso

from ..infrastructure.event_bus import EventBus
from ..paper_trader import PaperTrader
from ..strategy_base import StrategyBase
from .tasks import _bool_env, _int_env, _list_env, _scheduler_instance

logger = logging.getLogger(__name__)


class JobRecord:
    """Persistent record of a scheduled job."""

    def __init__(
        self,
        job_id: str,
        job_type: str,
        func_name: str,
        trigger_type: str,
        trigger_args: dict[str, Any],
        enabled: bool = True,
    ) -> None:
        self.job_id = job_id
        self.job_type = job_type  # "main" | "cron" | "interval"
        self.func_name = func_name
        self.trigger_type = trigger_type
        self.trigger_args = trigger_args
        self.enabled = enabled

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "func_name": self.func_name,
            "trigger_type": self.trigger_type,
            "trigger_args": self.trigger_args,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobRecord":
        return cls(
            job_id=data["job_id"],
            job_type=data.get("job_type", "cron"),
            func_name=data.get("func_name", ""),
            trigger_type=data.get("trigger_type", "cron"),
            trigger_args=data.get("trigger_args", {}),
            enabled=data.get("enabled", True),
        )


class PaperTradeScheduler:
    """APScheduler-based paper trading scheduler.

    Parameters
    ----------
    paper_trader : PaperTrader
        The paper trading engine to execute signals through.
    store : AStockStore
        DuckDB-backed store used to fetch kline data and persist jobs.
    interval_minutes : int
        Interval between scheduled cycles (default ``30``, overridable via
        ``ASTOCK_SCHEDULER_INTERVAL_MIN`` env var).
    strategies : list[StrategyBase] or None
        Strategies to evaluate each cycle.  If ``None``, uses a default
        set of all available strategies.
    symbols : list[str] or None
        Symbols to monitor.  If ``None``, uses a small default set.
    enabled : bool
        Whether to auto-start the scheduler.  Defaults to ``True`` but can
        be disabled via ``ASTOCK_SCHEDULER_ENABLED=false``.
    """

    def __init__(
        self,
        paper_trader: PaperTrader,
        store: Any,
        interval_minutes: int | None = None,
        strategies: list[StrategyBase] | None = None,
        symbols: list[str] | None = None,
        enabled: bool | None = None,
    ) -> None:
        self._trader = paper_trader
        self._store = store

        # Configuration with env-var overrides
        self._enabled = enabled if enabled is not None else _bool_env("ASTOCK_SCHEDULER_ENABLED", True)
        self._interval_minutes = max(
            1,
            interval_minutes
            or _int_env("ASTOCK_SCHEDULER_INTERVAL_MIN", 30),
        )
        self._strategies = strategies or self._default_strategies()
        self._symbols = symbols or _list_env(
            "ASTOCK_SCHEDULER_SYMBOLS",
            ["000300.SH", "000001.SH", "399001.SZ", "600519.SH", "000858.SZ"],
        )
        self._cycle_count = 0
        # Thread safety: protect _cycle_count and _persistent_jobs from
        # concurrent access (scheduler threads + API request threads).
        self._state_lock = threading.Lock()
        # Keep a bounded worker pool for the scheduler lifetime.  A timed-out
        # Python future cannot stop a running provider call, but reusing this
        # pool prevents every timeout from creating another orphan thread.
        self._symbol_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="astock-scheduler")

        self._scheduler = BackgroundScheduler(daemon=True)
        self._job_id = "paper_trade_cycle"
        self._job: Any = None

        # Persistent jobs registry: job_id -> JobRecord
        self._persistent_jobs: dict[str, JobRecord] = {}

        from .tasks import _scheduler_instance, get_scheduler, set_scheduler

        # Update the singleton
        set_scheduler(self)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the scheduler loop."""
        if not self._enabled:
            logger.info("PaperTradeScheduler disabled via config")
            return
        if self._scheduler.running:
            logger.warning("PaperTradeScheduler is already running")
            return

        # Load persistent jobs from DB
        self._load_jobs_from_db()

        # Add the main interval job
        self._job = self._scheduler.add_job(
            self._execute_scheduled_cycle,
            trigger=IntervalTrigger(minutes=self._interval_minutes),
            id=self._job_id,
            name="PaperTradeCycle",
            replace_existing=True,
            misfire_grace_time=60,
        )

        # Restore user cron jobs
        for job_id, record in self._persistent_jobs.items():
            if record.enabled and job_id != self._job_id:
                self._restore_job(record)

        self._scheduler.start()
        logger.info(
            "PaperTradeScheduler started (interval=%dmin, symbols=%s, strategies=%d, enabled=%s)",
            self._interval_minutes,
            self._symbols,
            len(self._strategies),
            self._enabled,
        )

    def stop(self) -> None:
        """Stop the scheduler loop and persist all jobs."""
        self._persist_all_jobs()
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        # Shut down the symbol worker pool to prevent orphan threads.
        self._symbol_executor.shutdown(wait=False, cancel_futures=True)
        logger.info("PaperTradeScheduler stopped (cycles=%d)", self._cycle_count)

    def pause(self) -> None:
        """Pause the scheduler (jobs remain registered)."""
        if self._job:
            self._job.pause()
        logger.info("PaperTradeScheduler paused")

    def resume(self) -> None:
        """Resume the scheduler after pause."""
        if self._job:
            self._job.resume()
        logger.info("PaperTradeScheduler resumed")

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def running(self) -> bool:
        return self._scheduler.running and self._job is not None and self._job.next_run_time is not None

    @property
    def paused(self) -> bool:
        return self._job is not None and self._job.next_run_time is None

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def next_run_time(self) -> str | None:
        if self._job and self._job.next_run_time:
            return self._job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
        return None

    # ------------------------------------------------------------------
    # Job management (CRUD + persistence)
    # ------------------------------------------------------------------

    def add_cron_job(
        self,
        func: Callable[[], None] | None = None,
        *,
        job_id: str = "user_cron",
        hour: str = "*",
        minute: str = "0",
        day_of_week: str = "*",
        enabled: bool = True,
    ) -> None:
        """Add a user-defined cron job.

        Parameters
        ----------
        func : callable or None
            Function to execute.  If None, runs the default cycle.
        hour, minute, day_of_week : str
            Cron expression fields (standard cron syntax).
        enabled : bool
            Whether the job is active immediately.
        """
        target = func or self._execute_scheduled_cycle
        aps_trigger = CronTrigger(hour=hour, minute=minute, day_of_week=day_of_week)
        aps_job = self._scheduler.add_job(
            target,
            trigger=aps_trigger,
            id=job_id,
            name=f"Cron:{job_id}",
            replace_existing=True,
            misfire_grace_time=120,
        )

        record = JobRecord(
            job_id=job_id,
            job_type="cron",
            func_name=getattr(func, "__name__", "<cycle>"),
            trigger_type="cron",
            trigger_args={"hour": hour, "minute": minute, "day_of_week": day_of_week},
            enabled=enabled,
        )
        with self._state_lock:
            self._persistent_jobs[job_id] = record
        self._persist_job(record)

        if not enabled:
            aps_job.pause()
        logger.info("Cron job added: %s at %s:%s (enabled=%s)", job_id, hour, minute, enabled)

    def add_interval_job(
        self,
        func: Callable[[], None] | None = None,
        *,
        job_id: str = "user_interval",
        minutes: int = 5,
        enabled: bool = True,
    ) -> None:
        """Add a user-defined interval job.

        Parameters
        ----------
        func : callable or None
            Function to execute.  If None, runs the default cycle.
        minutes : int
            Interval in minutes.
        enabled : bool
            Whether the job is active immediately.
        """
        target = func or self._execute_scheduled_cycle
        aps_job = self._scheduler.add_job(
            target,
            trigger=IntervalTrigger(minutes=max(1, minutes)),
            id=job_id,
            name=f"Interval:{job_id}",
            replace_existing=True,
            misfire_grace_time=60,
        )

        record = JobRecord(
            job_id=job_id,
            job_type="interval",
            func_name=getattr(func, "__name__", "<cycle>"),
            trigger_type="interval",
            trigger_args={"minutes": minutes},
            enabled=enabled,
        )
        with self._state_lock:
            self._persistent_jobs[job_id] = record
        self._persist_job(record)

        if not enabled:
            aps_job.pause()
        logger.info("Interval job added: %s every %dmin (enabled=%s)", job_id, minutes, enabled)

    def remove_job(self, job_id: str) -> bool:
        """Remove a job by ID. Returns True if found and removed."""
        # Remove from APScheduler
        try:
            aps_job = self._scheduler.get_job(job_id)
            if aps_job:
                aps_job.remove()
        except Exception:
            logger.warning("Failed to remove APScheduler job: %s", job_id)

        # Remove from persistent registry
        with self._state_lock:
            record = self._persistent_jobs.pop(job_id, None)
        if record:
            self._delete_job_from_db(job_id)
            logger.info("Job removed: %s", job_id)
            return True
        return False

    def list_jobs(self) -> list[dict[str, Any]]:
        """List all jobs (registered + persistent)."""
        jobs = []
        # Active APScheduler jobs
        for aps_job in self._scheduler.get_jobs():
            jobs.append({
                "job_id": aps_job.id,
                "name": aps_job.name,
                "next_run_time": aps_job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if aps_job.next_run_time else None,
                "paused": aps_job.next_run_time is None,
                "source": "apscheduler",
            })
        # Persistent jobs not in APScheduler (e.g., scheduler not started yet)
        for job_id, record in self._persistent_jobs.items():
            if not any(j["job_id"] == job_id for j in jobs):
                jobs.append({
                    "job_id": job_id,
                    "job_type": record.job_type,
                    "trigger_args": record.trigger_args,
                    "enabled": record.enabled,
                    "source": "persistent",
                })
        return jobs

    def toggle_job(self, job_id: str, enabled: bool) -> bool:
        """Enable or disable a job. Returns True if found."""
        record = self._persistent_jobs.get(job_id)
        if not record:
            return False
        record.enabled = enabled
        self._persist_job(record)

        try:
            aps_job = self._scheduler.get_job(job_id)
            if aps_job:
                if enabled:
                    aps_job.resume()
                else:
                    aps_job.pause()
        except Exception:
            logger.warning("Failed to toggle job %s (enabled=%s)", job_id, enabled)
        logger.info("Job toggled: %s -> enabled=%s", job_id, enabled)
        return True

    # ------------------------------------------------------------------
    # Persistence (DuckDB)
    # ------------------------------------------------------------------

    def _ensure_jobs_table(self) -> None:
        """Create the scheduled_jobs table if it doesn't exist."""
        if self._store is None:
            return
        try:
            self._store.conn.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_jobs (
                    job_id VARCHAR PRIMARY KEY,
                    job_type VARCHAR NOT NULL DEFAULT 'cron',
                    func_name VARCHAR,
                    trigger_type VARCHAR,
                    trigger_args VARCHAR,
                    enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        except Exception as exc:
            logger.warning("Failed to create scheduled_jobs table: %s", exc)

    def _load_jobs_from_db(self) -> None:
        """Load persistent jobs from DuckDB on startup."""
        if self._store is None:
            return
        self._ensure_jobs_table()
        try:
            df = self._store.conn.execute(
                "SELECT job_id, job_type, func_name, trigger_type, trigger_args, enabled FROM scheduled_jobs"
            ).fetchdf()
            for _, row in df.iterrows():
                record = JobRecord(
                    job_id=str(row["job_id"]),
                    job_type=str(row.get("job_type", "cron")),
                    func_name=str(row.get("func_name", "")),
                    trigger_type=str(row.get("trigger_type", "cron")),
                    trigger_args=json.loads(str(row.get("trigger_args", "{}"))) if row.get("trigger_args") else {},
                    enabled=bool(row.get("enabled", True)),
                )
                with self._state_lock:
                    self._persistent_jobs[record.job_id] = record
            logger.info("Loaded %d persistent jobs from DB", len(self._persistent_jobs))
        except Exception as exc:
            logger.warning("Failed to load scheduled jobs from DB: %s", exc)

    def _persist_job(self, record: JobRecord) -> None:
        """Persist a single job to DuckDB."""
        if self._store is None:
            return
        self._ensure_jobs_table()
        try:
            trigger_args_json = json.dumps(record.trigger_args, ensure_ascii=False)
            now = utc_now_iso()
            self._store.conn.execute(
                """INSERT INTO scheduled_jobs (job_id, job_type, func_name, trigger_type, trigger_args, enabled, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(job_id) DO UPDATE SET
                       job_type=excluded.job_type, func_name=excluded.func_name,
                       trigger_type=excluded.trigger_type, trigger_args=excluded.trigger_args,
                       enabled=excluded.enabled, updated_at=excluded.updated_at""",
                [
                    record.job_id,
                    record.job_type,
                    record.func_name,
                    record.trigger_type,
                    trigger_args_json,
                    record.enabled,
                    now,
                ],
            )
        except Exception as exc:
            logger.warning("Failed to persist job %s: %s", record.job_id, exc)

    def _persist_all_jobs(self) -> None:
        """Persist all jobs to DB (called on shutdown)."""
        for record in self._persistent_jobs.values():
            self._persist_job(record)

    def _delete_job_from_db(self, job_id: str) -> None:
        if self._store is None:
            return
        self._ensure_jobs_table()
        try:
            self._store.conn.execute("DELETE FROM scheduled_jobs WHERE job_id = ?", [job_id])
        except Exception as exc:
            logger.warning("Failed to delete job %s from DB: %s", job_id, exc)

    def _restore_job(self, record: JobRecord) -> None:
        """Re-create an APScheduler job from a persistent record."""
        try:
            args = record.trigger_args
            if record.trigger_type == "cron":
                trigger = CronTrigger(**args)
            elif record.trigger_type == "interval":
                trigger = IntervalTrigger(**args)
            else:
                trigger = CronTrigger(**args)

            self._scheduler.add_job(
                self._execute_scheduled_cycle,
                trigger=trigger,
                id=record.job_id,
                name=f"Restored:{record.job_id}",
                replace_existing=True,
            )
            logger.info("Restored job from persistence: %s", record.job_id)
        except Exception as exc:
            logger.warning("Failed to restore job %s: %s", record.job_id, exc)

    # ------------------------------------------------------------------
    # Cycle execution
    # ------------------------------------------------------------------

    # Per-symbol processing timeout (seconds) — prevents a single slow
    # kline fetch or strategy computation from blocking the entire cycle.
    SYMBOL_TIMEOUT: float = 30.0

    # Total cycle timeout (seconds) — prevents the entire cycle from
    # running forever even if individual symbol timeouts don't trigger.
    CYCLE_TIMEOUT: float = 300.0

    def _execute_scheduled_cycle(self) -> None:
        """Execute one full scheduled cycle.

        Thread-safe: uses a ThreadPoolExecutor with a timeout so that a
        single symbol's data fetch or strategy computation cannot block
        the entire cycle indefinitely.
        """
        with self._state_lock:
            self._cycle_count += 1
            cycle_id = self._cycle_count
        logger.info("Scheduled cycle #%d starting", cycle_id)

        EventBus.publish({
            "type": "cycle_start",
            "cycle": cycle_id,
            "timestamp": utc_now_iso(),
        })

        signals: dict[str, float] = {}
        prices: dict[str, float] = {}

        if not self._symbols:
            EventBus.publish({
                "type": "cycle_complete", "cycle": cycle_id,
                "total_value": 0.0, "cash": 0.0, "trade_count": 0,
                "symbol_count": 0, "note": "no_symbols",
                "timestamp": utc_now_iso(),
            })
            logger.info("Cycle #%d skipped: no symbols configured", cycle_id)
            return

        # Process each symbol in a thread pool so we can enforce a timeout
        # per symbol.  If one symbol hangs, the others still proceed.
        # We manually manage the pool so we can call shutdown(wait=False)
        # to avoid blocking on timed-out threads.
        pool = self._symbol_executor
        try:
            futures = {}
            for symbol in self._symbols:
                futures[pool.submit(self._process_symbol, symbol)] = symbol

            submitted_at = {future: time.monotonic() for future in futures}
            pending = set(futures)
            cycle_deadline = time.monotonic() + self.CYCLE_TIMEOUT
            while pending and time.monotonic() < cycle_deadline:
                done, pending = wait(
                    pending,
                    timeout=min(0.25, max(0.0, cycle_deadline - time.monotonic())),
                    return_when=FIRST_COMPLETED,
                )
                for future in done:
                    symbol = futures[future]
                    try:
                        result = future.result()
                        if result is not None:
                            sym_price, sym_signal = result
                            prices[symbol] = sym_price
                            signals[symbol] = sym_signal
                    except Exception as exc:
                        logger.warning("Error processing symbol %s: %s", symbol, exc)
                        EventBus.publish({
                            "type": "cycle_error", "cycle": cycle_id, "symbol": symbol,
                            "message": str(exc), "timestamp": utc_now_iso(),
                        })
                now = time.monotonic()
                expired = [future for future in pending if now - submitted_at[future] >= self.SYMBOL_TIMEOUT]
                for future in expired:
                    pending.remove(future)
                    symbol = futures[future]
                    self._interrupt_store_query(symbol)
                    future.cancel()
                    logger.warning("Symbol %s processing timed out after %ds", symbol, self.SYMBOL_TIMEOUT)
                    EventBus.publish({
                        "type": "cycle_error", "cycle": cycle_id, "symbol": symbol,
                        "message": f"processing timed out after {self.SYMBOL_TIMEOUT}s",
                        "timestamp": utc_now_iso(),
                    })
            for future in pending:
                symbol = futures[future]
                future.cancel()
                EventBus.publish({
                    "type": "cycle_error", "cycle": cycle_id, "symbol": symbol,
                    "message": f"cycle deadline exceeded after {self.CYCLE_TIMEOUT}s",
                    "timestamp": utc_now_iso(),
                })
        finally:
            # DuckDB queries are interrupted above before a Future is removed.
            # ``cancel`` still handles work that has not started yet.
            pass

        if signals:
            try:
                state = self._trader.execute_cycle(signals, prices)
                trade_count = len(state.trades)
                for trade in state.trades[-5:]:
                    EventBus.publish({
                        "type": "trade",
                        "cycle": cycle_id,
                        "symbol": trade.get("symbol", ""),
                        "direction": trade.get("type", ""),
                        "price": trade.get("price", 0.0),
                        "volume": trade.get("shares", 0.0),
                        "timestamp": utc_now_iso(),
                    })
                EventBus.publish({
                    "type": "cycle_complete",
                    "cycle": cycle_id,
                    "total_value": state.total_value,
                    "cash": state.cash,
                    "trade_count": trade_count,
                    "symbol_count": len(signals),
                    "timestamp": utc_now_iso(),
                })
                logger.info(
                    "Cycle #%d done: %d symbols, %d trades, total_value=%.2f",
                    cycle_id, len(signals), trade_count, state.total_value,
                )
            except Exception as exc:
                logger.error("Cycle #%d execution failed: %s", cycle_id, exc)
                EventBus.publish({
                    "type": "cycle_error",
                    "cycle": cycle_id,
                    "message": str(exc),
                    "timestamp": utc_now_iso(),
                })
        else:
            EventBus.publish({
                "type": "cycle_complete", "cycle": cycle_id,
                "total_value": 0.0, "cash": 0.0,
                "trade_count": 0, "symbol_count": 0,
                "note": "no_signals",
                "timestamp": utc_now_iso(),
            })
            logger.info("Cycle #%d done: no signals generated", cycle_id)

    def _process_symbol(self, symbol: str) -> tuple[float, float] | None:
        """Process a single symbol: fetch kline, run strategies, return signal.

        Returns ``(price, signal)`` or ``None`` if no data/signals.
        This method is designed to run inside a ThreadPoolExecutor so that
        a long-running fetch or strategy computation can be cancelled via
        ``future.result(timeout=...)``.

        Raises
        ------
        Exception
            Any error during processing is propagated so the caller can
            publish a ``cycle_error`` event without breaking other symbols.
        """
        df = self._fetch_latest(symbol)
        if df is None or df.empty:
            return None

        price = float(df["close"].iloc[-1])

        symbol_signals: list[int] = []
        for strategy in self._strategies:
            sig_series = strategy.generate_signals(df)
            non_zero = sig_series[sig_series != 0]
            sig = int(non_zero.iloc[-1]) if not non_zero.empty else 0
            symbol_signals.append(sig)

        total_sig = sum(symbol_signals)
        if total_sig > 0:
            signal = 1.0
        elif total_sig < 0:
            signal = -1.0
        else:
            signal = 0.0

        return (price, signal)

    def _interrupt_store_query(self, symbol: str) -> None:
        """Ask the active database connection to stop a timed-out query.

        The scheduler only reads local kline data; it must not leave a blocked
        DuckDB query behind and pretend that ``Future.cancel`` stopped it.
        DuckDB exposes ``interrupt`` on the connection in supported versions.
        Other stores simply do not provide this best-effort hook.
        """
        for candidate in (self._store, getattr(self._store, "conn", None)):
            interrupt = getattr(candidate, "interrupt", None)
            if callable(interrupt):
                try:
                    interrupt()
                    logger.warning("Interrupted timed-out kline query for %s", symbol)
                    return
                except Exception as exc:
                    logger.warning("Failed to interrupt timed-out query for %s: %s", symbol, exc)

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _fetch_latest(self, symbol: str, lookback: int = 100) -> Any:
        """Fetch the most recent *lookback* kline bars from DuckDB."""
        import pandas as pd

        if not hasattr(self._store, "query_kline"):
            return pd.DataFrame()
        try:
            df = self._store.query_kline(symbol=symbol, interval="1d", limit=lookback)
            if not isinstance(df, pd.DataFrame) or df.empty:
                return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
            df = df.copy()
            if "trade_date" in df.columns and "date" not in df.columns:
                df["date"] = pd.to_datetime(df["trade_date"])
            if "date" in df.columns:
                df = df.set_index("date").sort_index()
            for col in ("open", "high", "low", "close", "volume"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if len(df) > lookback:
                df = df.iloc[-lookback:]
            return df
        except Exception:
            logger.debug("Failed to load historical kline for %s", symbol)
            import pandas as pd

            return pd.DataFrame()

    @staticmethod
    def _default_strategies() -> list[StrategyBase]:
        from ..strategy_base import (
            BullTrendStrategy,
            MeanReversionStrategy,
            MovingAverageTrendStrategy,
            RSIRangeStrategy,
        )
        return [
            MovingAverageTrendStrategy(),
            BullTrendStrategy(),
            MeanReversionStrategy(),
            RSIRangeStrategy(),
        ]


# Public alias for backward compatibility with tests and external callers
PaperTradeScheduler.execute_scheduled_cycle = PaperTradeScheduler._execute_scheduled_cycle
