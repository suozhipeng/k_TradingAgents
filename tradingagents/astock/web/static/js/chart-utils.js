const ChartUtils = {
  historyPayloadToBars(data) {
    if (!data || data.s !== 'ok' || !Array.isArray(data.t)) return [];
    const bars = [];
    for (let i = 0; i < data.t.length; i += 1) {
      bars.push({
        timestamp: data.t[i] * 1000,
        open: data.o[i],
        high: data.h[i],
        low: data.l[i],
        close: data.c[i],
        volume: data.v[i],
      });
    }
    return bars;
  },

  sortBars(bars) {
    return [...bars].sort((left, right) => left.timestamp - right.timestamp);
  },
};

window.ChartUtils = ChartUtils;
