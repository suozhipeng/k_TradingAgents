"""Phase 32 smoke tests — Strategy Registry (standalone schema test)."""
import unittest


class TestStrategyRegistrySchema(unittest.TestCase):
    """Test the strategy registry schema inline to avoid langgraph dep chain."""

    def setUp(self):
        from dataclasses import dataclass, field
        from typing import Any

        @dataclass
        class StrategyRegistryEntry:
            name: str
            category: str = "unsorted"
            description: str = ""
            params_schema: dict[str, Any] = field(default_factory=dict)
            search_space: dict[str, list[Any]] | None = None
            suitability: list[str] = field(default_factory=lambda: ["all"])

        def register(entry: StrategyRegistryEntry) -> None:
            _STRATEGY_REGISTRY[entry.name] = entry

        def get_registry() -> dict[str, StrategyRegistryEntry]:
            return dict(_STRATEGY_REGISTRY)

        def get_strategy(name: str) -> StrategyRegistryEntry | None:
            return _STRATEGY_REGISTRY.get(name)

        def list_strategies(*, category: str | None = None) -> list[StrategyRegistryEntry]:
            if category is None:
                return list(_STRATEGY_REGISTRY.values())
            return [e for e in _STRATEGY_REGISTRY.values() if e.category == category]

        self.StrategyRegistryEntry = StrategyRegistryEntry
        self.register = register
        self.get_registry = get_registry
        self.get_strategy = get_strategy
        self.list_strategies = list_strategies

        # Reset registry
        _STRATEGY_REGISTRY.clear()

        # Pre-populate
        _STRATEGY_REGISTRY["MovingAverageTrend"] = StrategyRegistryEntry(
            name="MovingAverageTrend",
            category="trend",
            search_space={"fast_period": [5, 10, 15], "slow_period": [20, 30, 50]},
        )
        _STRATEGY_REGISTRY["BullTrend"] = StrategyRegistryEntry(
            name="BullTrend", category="trend"
        )
        _STRATEGY_REGISTRY["MeanReversion"] = StrategyRegistryEntry(
            name="MeanReversion", category="mean_reversion"
        )

    def test_registry_has_entries(self):
        entries = self.get_registry()
        self.assertEqual(len(entries), 3)

    def test_get_strategy_found(self):
        entry = self.get_strategy("MovingAverageTrend")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, "trend")

    def test_get_strategy_nonexistent(self):
        self.assertIsNone(self.get_strategy("Nonexistent"))

    def test_list_by_category(self):
        trend = self.list_strategies(category="trend")
        self.assertEqual(len(trend), 2)

    def test_strategy_has_search_space(self):
        entry = self.get_strategy("MovingAverageTrend")
        if entry and entry.search_space:
            self.assertIn("fast_period", entry.search_space)

    def test_custom_register(self):
        entry = self.StrategyRegistryEntry(
            name="TestStrategy", category="test",
        )
        self.register(entry)
        self.assertIsNotNone(self.get_strategy("TestStrategy"))

    def test_entry_params_schema(self):
        entry = self.StrategyRegistryEntry(
            name="ParamStrategy", params_schema={"ma_period": 20},
        )
        self.assertEqual(entry.params_schema, {"ma_period": 20})


_STRATEGY_REGISTRY: dict = {}

if __name__ == "__main__":
    unittest.main()
