import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { MarketType } from "../types";
import { useTranslation } from "../hooks/useTranslation";

const STORAGE_KEY = "tradingagents_market";
const DEFAULT_MARKET: MarketType = "us";

function getInitialMarket(): MarketType {
  if (typeof window === "undefined") return DEFAULT_MARKET;
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "us" || stored === "astock") return stored;
  return DEFAULT_MARKET;
}

export type MarketContextValue = {
  market: MarketType;
  setMarket: (m: MarketType) => void;
};

export const MarketContext = createContext<MarketContextValue>({
  market: DEFAULT_MARKET,
  setMarket: () => {},
});

export function useMarket() {
  const { market, setMarket } = useContext(MarketContext);

  const toggleMarket = useCallback(() => {
    const next: MarketType = market === "us" ? "astock" : "us";
    setMarket(next);
    localStorage.setItem(STORAGE_KEY, next);
  }, [market, setMarket]);

  return { market, setMarket, toggleMarket };
}

export function MarketProvider({ children }: { children: React.ReactNode }) {
  const [market, setMarket] = useState<MarketType>(getInitialMarket);

  const value = useMemo(() => ({ market, setMarket }), [market]);

  return (
    <MarketContext.Provider value={value}>
      {children}
    </MarketContext.Provider>
  );
}

/** Market switch component, displayed in the header next to LangSwitch */
export default function MarketSwitch() {
  const { market, setMarket } = useMarket();
  const { t } = useTranslation();

  return (
    <div className="flex items-center gap-1 rounded-full border border-white/10 bg-white/5 p-0.5">
      <button
        type="button"
        onClick={() => setMarket("us")}
        className={`rounded-full px-3 py-1.5 text-xs transition ${
          market === "us"
            ? "bg-cyan-300 text-slate-950 font-semibold"
            : "text-slate-400 hover:text-slate-200"
        }`}
      >
        {t("market.us")}
      </button>
      <button
        type="button"
        onClick={() => setMarket("astock")}
        className={`rounded-full px-3 py-1.5 text-xs transition ${
          market === "astock"
            ? "bg-cyan-300 text-slate-950 font-semibold"
            : "text-slate-400 hover:text-slate-200"
        }`}
      >
        {t("market.astock")}
      </button>
    </div>
  );
}
