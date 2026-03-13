"use client";

import { useState, useEffect } from "react";
import { Search, Sun, Moon, Languages } from "lucide-react";
import { useLocale } from "@/contexts/LocaleContext";

export function Header() {
  const { locale, setLocale, t } = useLocale();
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    const saved = localStorage.getItem("aide-theme") as "light" | "dark" | null;
    if (saved) setTheme(saved);
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("aide-theme", next);
  };

  return (
    <header
      id="app-header"
      className="fixed top-0 right-0 z-30 flex h-16 items-center justify-between border-b border-aide-border bg-aide-bg-secondary/80 px-6 backdrop-blur-md transition-[left] duration-200"
    >
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-aide-text-muted" />
        <input
          className="h-9 w-72 rounded-lg border border-aide-border bg-aide-bg-primary pl-9 pr-3 text-sm text-aide-text-primary placeholder-aide-text-muted outline-none transition-all input-focus-ring focus:border-aide-border-focus"
          placeholder={t("form.searchProjects")}
        />
      </div>

      {/* Right: Locale + Theme + Avatar */}
      <div className="flex items-center gap-1">
        <button
          onClick={() => setLocale(locale === "zh" ? "en" : "zh")}
          className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs font-medium text-aide-text-muted transition-colors hover:bg-aide-bg-tertiary hover:text-aide-text-primary"
          title={locale === "zh" ? "Switch to English" : "切换到中文"}
        >
          <Languages className="h-3.5 w-3.5" />
          <span>{locale === "zh" ? "中" : "EN"}</span>
        </button>

        <button
          onClick={toggleTheme}
          className="rounded-lg p-2 text-aide-text-muted transition-colors hover:bg-aide-bg-tertiary hover:text-aide-text-primary"
          title={theme === "dark" ? t("misc.switchToLight") : t("misc.switchToDark")}
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>

        <div
          className="ml-2 flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 text-xs font-bold text-white shadow-sm"
        >
          AI
        </div>
      </div>
    </header>
  );
}
