/**
 * System health check component — shows backend connectivity, version,
 * and a quick status indicator.
 */

import { useEffect, useState } from "react";
import { useApi } from "../hooks/useApi";

interface HealthResult {
  status: string;
  version: string;
}

export default function HealthCheck() {
  const api = useApi();
  const [health, setHealth] = useState<HealthResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .health()
      .then((res) => {
        if (!cancelled) {
          setHealth(res as unknown as HealthResult);
          setError(null);
        }
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [api]);

  const isConnected = !!health && !error;

  return (
    <div className="flex items-center gap-2 text-xs">
      <span
        className={`inline-block h-2 w-2 rounded-full ${
          loading ? "bg-yellow-400 animate-pulse"
            : isConnected ? "bg-emerald-400"
            : "bg-rose-400"
        }`}
      />
      {loading ? (
        <span className="text-slate-400">Checking...</span>
      ) : isConnected ? (
        <span className="text-slate-300">
          v{health.version}
        </span>
      ) : (
        <span className="text-rose-300" title={error ?? undefined}>
          Offline
        </span>
      )}
    </div>
  );
}
