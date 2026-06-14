import { useTranslation } from "../hooks/useTranslation";

/** Circular language switch button ("中" / "EN"), shown in the header nav area */
export default function LangSwitch() {
  const { locale, toggleLocale } = useTranslation();

  return (
    <button
      type="button"
      onClick={toggleLocale}
      title={locale === "zh" ? "Switch to English" : "切换到中文"}
      className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-sm font-semibold text-slate-200 transition hover:border-cyan-200/40 hover:bg-cyan-300/10 hover:text-white"
    >
      {locale === "zh" ? "中" : "EN"}
    </button>
  );
}
