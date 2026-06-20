/**
 * Shared KLineChart data loader — dedup + caching + TTL auto-refresh.
 *
 * Usage:
 *   const dl = KCDataLoader.create('/api/v1/tv', { onRefresh(chart, bars) { ... } });
 *   chart.setDataLoader(dl.dataLoader);
 *   // dl.state: { barCache, barDataCache, loadGeneration, fetchControllers, subscribeInterval }
 */

const KCDataLoader = {
  create(apiBase, opts = {}) {
    const state = {
      loadGeneration: 0,
      fetchControllers: new Set(),
      subscribeInterval: null,
      refreshInterval: null,
      currentPeriod: null,
      currentSymbol: null,
      barCache: {},       // key: `${symbol}_${period}` → timestamps (ms), for dedup
      barDataCache: {},   // key: `${symbol}_${period}` → { bars: [...], fetchedAt: timestamp_ms }
    };

    // ── TTL: how old can cached data be before auto-refresh ──
    function ttlForPeriod(period) {
      if (period >= 43200) return 24 * 3600 * 1000;  // 月线: 1天
      if (period >= 10080) return 4 * 3600 * 1000;   // 周线: 4小时
      if (period >= 1440)  return 3600 * 1000;        // 日线: 1小时
      return 5 * 60 * 1000;                           // 分钟线: 5分钟
    }

    // ── Stale-while-revalidate: return cached, refresh in background ──
    async function refreshInBackground(cacheKey, symbol, period) {
      const tvPeriod = String(period);
      const now = Math.floor(Date.now() / 1000);
      const gen = state.loadGeneration;
      try {
        const res = await fetch(
          `${apiBase}/history?symbol=${symbol.symbol}&resolution=${tvPeriod}&from=0&to=${now}`
        );
        const data = await res.json();
        if (gen !== state.loadGeneration) return;
        if (data.s !== 'ok' || !data.t) return;

        const newBars = [];
        for (let i = 0; i < data.t.length; i++) {
          newBars.push({
            timestamp: data.t[i] * 1000,
            open: data.o[i], high: data.h[i], low: data.l[i],
            close: data.c[i], volume: data.v[i],
          });
        }
        state.barDataCache[cacheKey] = { bars: newBars, fetchedAt: Date.now() };

        // Notify the page so it can update the chart
        if (opts.onRefresh) opts.onRefresh(newBars, { symbol, period });
      } catch (_) {}
    }

    function getCacheTTL(cacheKey) {
      const raw = state.barDataCache[cacheKey];
      if (!raw) return -1;
      // Support both old format (array) and new format ({ bars, fetchedAt })
      const fetchedAt = raw.fetchedAt || (raw._fetchedAt) || 0;
      return Date.now() - fetchedAt;
    }

    const dataLoader = {
      async getBars(params) {
        const { symbol, period, timestamp, callback, type } = params;
        const cacheKey = `${symbol.symbol}_${period}`;
        const tvPeriod = String(period);
        const now = Math.floor(Date.now() / 1000);
        const requestGeneration = state.loadGeneration;

        // Track for auto-refresh timer
        state.currentSymbol = symbol.symbol;
        state.currentPeriod = period;

        // ── Fast path: init load from cache (with stale-while-revalidate) ──
        if (type === 'init' && !timestamp) {
          const raw = state.barDataCache[cacheKey];
          const cached = raw ? (raw.bars || raw) : null;
          if (cached && cached.length > 0) {
            const age = getCacheTTL(cacheKey);
            const ttl = ttlForPeriod(period);
            if (age > ttl) {
              // Stale: return cached immediately, refresh in background
              refreshInBackground(cacheKey, symbol, period);
            }
            callback(cached, true);
            return;
          }
        }

        // ── Determine fetch range ──
        let from, to;
        if (type === 'backward' && timestamp) {
          from = 0;
          to = Math.floor(timestamp / 1000);
        } else if (type === 'forward' && timestamp) {
          from = Math.floor(timestamp / 1000);
          to = now;
        } else {
          from = 0;
          to = now;
        }

        const controller = new AbortController();
        state.fetchControllers.add(controller);
        const signal = controller.signal;

        try {
          const url = `${apiBase}/history?symbol=${symbol.symbol}&resolution=${tvPeriod}&from=${from}&to=${to}`;
          const res = await fetch(url, { signal });
          const data = await res.json();
          if (requestGeneration !== state.loadGeneration || signal.aborted) return;

          if (data.s === 'ok' && data.t) {
            // ── Deduplicate against timestamp cache ──
            const seen = new Set(state.barCache[cacheKey] || []);
            const newBars = [];
            for (let i = 0; i < data.t.length; i++) {
              const ts = data.t[i] * 1000;
              if (!seen.has(ts)) {
                seen.add(ts);
                newBars.push({
                  timestamp: ts,
                  open: data.o[i], high: data.h[i], low: data.l[i],
                  close: data.c[i], volume: data.v[i],
                });
              }
            }
            // Update timestamp cache
            const sorted = Array.from(seen).sort((a, b) => a - b);
            state.barCache[cacheKey] = sorted.length > 50000
              ? sorted.slice(-50000)
              : sorted;

            // Store init data in bar cache with timestamp
            if (type === 'init' && newBars.length > 0) {
              state.barDataCache[cacheKey] = { bars: newBars, fetchedAt: Date.now() };
            }

            callback(newBars, data.t.length > 0);
          } else {
            callback([], false);
          }
        } catch (e) {
          if (e.name !== 'AbortError' && requestGeneration === state.loadGeneration) {
            callback([], false);
          }
        } finally {
          state.fetchControllers.delete(controller);
        }
      },

      subscribeBar(params) {
        if (state.subscribeInterval) clearInterval(state.subscribeInterval);
        state.subscribeInterval = setInterval(async () => {
          if (!chart) {
            clearInterval(state.subscribeInterval);
            state.subscribeInterval = null;
            return;
          }
          const now = Math.floor(Date.now() / 1000);
          const resolution = String(params.period || 1);
          try {
            const res = await fetch(
              `${apiBase}/history?symbol=${params.symbol.symbol}&resolution=${resolution}&from=${now - 7200}&to=${now}`
            );
            const data = await res.json();
            if (data.s === 'ok' && data.t && data.t.length > 0) {
              const i = data.t.length - 1;
              const newBar = {
                timestamp: data.t[i] * 1000,
                open: data.o[i], high: data.h[i], low: data.l[i],
                close: data.c[i], volume: data.v[i],
              };
              params.callback(newBar);
              // Update bar data cache
              const cacheKey = `${params.symbol.symbol}_${resolution}`;
              const raw = state.barDataCache[cacheKey];
              if (raw) {
                const bars = raw.bars || raw;
                bars.push(newBar);
                bars.sort((a, b) => a.timestamp - b.timestamp);
                state.barDataCache[cacheKey] = raw.bars
                  ? { bars, fetchedAt: raw.fetchedAt }
                  : bars;
              }
            }
          } catch (_) {}
        }, 30000);
      },

      unsubscribeBar() {
        if (state.subscribeInterval) {
          clearInterval(state.subscribeInterval);
          state.subscribeInterval = null;
        }
      },
    };

    return { dataLoader, state };
  },
};
