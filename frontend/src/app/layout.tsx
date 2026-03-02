"use client";

import "./globals.css";
import { Inter } from "next/font/google";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Settings, FlaskConical, Sun, Moon } from "lucide-react";
import { useState, useEffect } from "react";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/settings", label: "Settings", icon: Settings },
];

function Sidebar() {
  const pathname = usePathname();
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const saved = localStorage.getItem("aide-theme") as "dark" | "light" | null;
    if (saved) setTheme(saved);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("aide-theme", theme);
  }, [theme]);

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-56 flex-col border-r border-aide-border bg-aide-bg-secondary">
      <div className="flex h-14 items-center gap-2.5 border-b border-aide-border px-5">
        <FlaskConical className="h-5 w-5 text-aide-accent-blue" />
        <span className="text-lg font-semibold tracking-tight text-aide-text-primary">
          AIDE
        </span>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-aide-accent-blue/10 text-aide-accent-blue"
                  : "text-aide-text-secondary hover:bg-aide-bg-tertiary hover:text-aide-text-primary"
              }`}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-aide-border px-4 py-3 flex items-center justify-between">
        <p className="text-xs text-aide-text-muted">
          AI for Discovery &amp; Exploration
        </p>
        <button
          onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
          className="rounded-md p-1.5 text-aide-text-muted hover:bg-aide-bg-tertiary hover:text-aide-text-primary transition-colors"
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>
    </aside>
  );
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="bg-aide-bg-primary">
        <Sidebar />
        <main className="ml-56 min-h-screen p-6">{children}</main>
      </body>
    </html>
  );
}
