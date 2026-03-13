"use client";

import type { ReactNode } from "react";
import { LocaleProvider } from "@/contexts/LocaleContext";
import { Sidebar } from "@/components/sidebar";
import { Header } from "@/components/header";

export function ClientProviders({ children }: { children: ReactNode }) {
  return (
    <LocaleProvider>
      <Sidebar />
      <Header />
      <main
        id="main-content"
        className="min-h-screen px-6 pb-6 pt-[88px] transition-[margin-left] duration-200 ml-[240px]"
      >
        {children}
      </main>
    </LocaleProvider>
  );
}
