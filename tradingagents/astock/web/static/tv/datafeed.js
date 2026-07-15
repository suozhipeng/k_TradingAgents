/* TradingView Charting Library Datafeed Adapter
 *
 * Bridges TradingView ↔ our Flask API (/api/v1/tv/* endpoints).
 * The charting_library files must be placed in
 *   tradingagents/astock/web/static/tv/charting_library/
 * by the user (download from TradingView).
 */

class AStockTVDatafeed {
    constructor() {
        this._ready = false;
        this._symbolInfoCache = {};
    }

    /* ── IDatafeedAsync ── */

    onReady(callback) {
        setTimeout(() => {
            this._ready = true;
            callback({
                supports_marks: false,
                supports_timescale_marks: false,
                supports_time: true,
                supported_resolutions: ['1', '5', '15', '30', '60', '240', 'D', 'W', 'M'],
            });
        }, 0);
    }

    async resolveSymbol(symbolName, onSymbolResolved, onResolveError) {
        try {
            const url = `/api/v1/tv/symbols?symbol=${encodeURIComponent(symbolName)}`;
            const res = await fetch(url);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = APIClient.unwrap(await res.json());
            onSymbolResolved(data);
        } catch (e) {
            onResolveError(`Cannot resolve symbol: ${e.message}`);
        }
    }

    async getBars(symbolInfo, resolution, periodParams, onHistoryCallback, onErrorCallback) {
        const { from, to, countBack } = periodParams;
        try {
            const url = `/api/v1/tv/history?symbol=${encodeURIComponent(symbolInfo.symbol)}`
                + `&resolution=${encodeURIComponent(resolution)}`
                + `&from=${from}&to=${to}`;
            const res = await fetch(url);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = APIClient.unwrap(await res.json());

            if (data.s === 'no_data') {
                onHistoryCallback([], { noData: true });
                return;
            }
            if (data.s === 'error') {
                onErrorCallback(data.errmsg);
                return;
            }

            const bars = [];
            for (let i = 0; i < data.t.length; i++) {
                bars.push({
                    time: data.t[i] * 1000,   // TV expects ms
                    open: data.o[i],
                    high: data.h[i],
                    low: data.l[i],
                    close: data.c[i],
                    volume: data.v[i],
                });
            }
            onHistoryCallback(bars, { noData: bars.length === 0 });
        } catch (e) {
            onErrorCallback(e.message);
        }
    }

    subscribeBars(symbolInfo, resolution, onRealtimeCallback, subscriberUID, onResetCacheNeeded) {
        // Real-time updates: poll every 30s for latest minute data
        this._realtimeInterval = setInterval(async () => {
            try {
                const now = Math.floor(Date.now() / 1000);
                const url = `/api/v1/tv/history?symbol=${encodeURIComponent(symbolInfo.symbol)}`
                    + `&resolution=1&from=${now - 7200}&to=${now}`;
                const res = await fetch(url);
                if (!res.ok) return;
                const data = APIClient.unwrap(await res.json());
                if (data.s === 'ok' && data.t && data.t.length > 0) {
                    const lastIdx = data.t.length - 1;
                    onRealtimeCallback({
                        time: data.t[lastIdx] * 1000,
                        open: data.o[lastIdx],
                        high: data.h[lastIdx],
                        low: data.l[lastIdx],
                        close: data.c[lastIdx],
                        volume: data.v[lastIdx],
                    });
                }
            } catch (_) { /* silent */ }
        }, 30000);
    }

    unsubscribeBars(subscriberUID) {
        if (this._realtimeInterval) {
            clearInterval(this._realtimeInterval);
            this._realtimeInterval = null;
        }
    }

    /* Required stubs */
    searchSymbols(userInput, exchange, symbolType, onResultReadyCallback) {
        onResultReadyCallback([]);
    }

    getServerTime(callback) {
        callback(Math.floor(Date.now() / 1000));
    }
}
