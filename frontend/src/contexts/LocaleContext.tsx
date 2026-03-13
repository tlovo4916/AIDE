"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  type Locale,
  type I18nKey,
  t as translate,
  getLocaleFromStorage,
  setLocaleToStorage,
} from "@/lib/i18n";

interface LocaleContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: I18nKey, params?: Record<string, string | number>) => string;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("zh");

  useEffect(() => {
    setLocaleState(getLocaleFromStorage());
  }, []);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    setLocaleToStorage(l);
  }, []);

  const t = useCallback(
    (key: I18nKey, params?: Record<string, string | number>) =>
      translate(key, locale, params),
    [locale],
  );

  return (
    <LocaleContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </LocaleContext.Provider>
  );
}

export function useLocale() {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used within LocaleProvider");
  return ctx;
}
