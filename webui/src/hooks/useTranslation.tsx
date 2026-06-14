import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { en, zh } from "../i18n";

export type Locale = "en" | "zh";

const STORAGE_KEY = "tradingagents_locale";
const DEFAULT_LOCALE: Locale = "zh";

function getInitialLocale(): Locale {
  if (typeof window === "undefined") return DEFAULT_LOCALE;
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "en" || stored === "zh") return stored;
  return DEFAULT_LOCALE;
}

const locales: Record<Locale, Record<string, string>> = { en, zh };

export type LocaleContextValue = {
  locale: Locale;
  setLocale: (l: Locale) => void;
};

export const LocaleContext = createContext<LocaleContextValue>({
  locale: DEFAULT_LOCALE,
  setLocale: () => {},
});

export function useTranslation() {
  const { locale, setLocale } = useContext(LocaleContext);

  const t = useCallback(
    (key: string, params?: Record<string, string>): string => {
      const dict = locales[locale] ?? en;
      let msg = dict[key];
      if (msg === undefined) {
        // fallback to English
        msg = en[key];
      }
      if (msg === undefined) {
        return key;
      }
      if (params) {
        for (const [k, v] of Object.entries(params)) {
          msg = msg.replace(`{${k}}`, v);
        }
      }
      return msg;
    },
    [locale],
  );

  const toggleLocale = useCallback(() => {
    const next: Locale = locale === "en" ? "zh" : "en";
    setLocale(next);
    localStorage.setItem(STORAGE_KEY, next);
  }, [locale, setLocale]);

  const isChinese = locale === "zh";

  return { t, locale, setLocale, toggleLocale, isChinese };
}

/** Provider component that wraps the app with locale state */
export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocale] = useState<Locale>(getInitialLocale);

  const value = useMemo(() => ({ locale, setLocale }), [locale]);

  return (
    <LocaleContext.Provider value={value}>
      {children}
    </LocaleContext.Provider>
  );
}
