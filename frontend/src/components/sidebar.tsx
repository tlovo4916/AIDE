"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Settings,
  FlaskConical,
  PanelLeftClose,
  PanelLeftOpen,
  BarChart3,
  Kanban,
  MessageSquare,
  BookOpen,
  FileText,
  ChevronDown,
} from "lucide-react";
import { useState, useEffect } from "react";
import { useProjectSidebar, type ProjectSection } from "@/contexts/ProjectSidebarContext";
import { useLocale } from "@/contexts/LocaleContext";
import type { I18nKey } from "@/lib/i18n";

interface NavItem {
  href?: string;
  sectionKey?: ProjectSection;
  labelKey: I18nKey;
  icon: typeof LayoutDashboard;
}

interface NavGroup {
  labelKey: I18nKey;
  color: string;
  items: NavItem[];
}

const PROJECT_SECTIONS: { key: ProjectSection; labelKey: I18nKey; icon: typeof BarChart3 }[] = [
  { key: "overview", labelKey: "nav.overview", icon: BarChart3 },
  { key: "blackboard", labelKey: "nav.blackboard", icon: Kanban },
  { key: "messages", labelKey: "nav.messages", icon: MessageSquare },
  { key: "knowledge", labelKey: "nav.knowledge", icon: BookOpen },
  { key: "paper", labelKey: "nav.paper", icon: FileText },
];

export function Sidebar() {
  const pathname = usePathname();
  const { t } = useLocale();
  const [collapsed, setCollapsed] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
  const projectCtx = useProjectSidebar();

  const isProjectPage = /^\/projects\/[^/]+/.test(pathname);

  useEffect(() => {
    const savedCollapsed = localStorage.getItem("aide-sidebar-collapsed");
    if (savedCollapsed === "true") setCollapsed(true);
  }, []);

  useEffect(() => {
    document.body.setAttribute("data-sidebar", collapsed ? "collapsed" : "expanded");
    localStorage.setItem("aide-sidebar-collapsed", String(collapsed));
  }, [collapsed]);

  const toggleGroup = (label: string) => {
    setCollapsedGroups((prev) => ({ ...prev, [label]: !prev[label] }));
  };

  const WORKSPACE_GROUP: NavGroup = {
    labelKey: "nav.workspace",
    color: "text-amber-400",
    items: [{ href: "/", labelKey: "nav.projects", icon: LayoutDashboard }],
  };

  const SYSTEM_GROUP: NavGroup = {
    labelKey: "nav.system",
    color: "text-blue-400",
    items: [{ href: "/settings", labelKey: "nav.settings", icon: Settings }],
  };

  const groups: NavGroup[] = [WORKSPACE_GROUP];

  if (isProjectPage && projectCtx) {
    groups.push({
      labelKey: "nav.project",
      color: "text-emerald-400",
      items: PROJECT_SECTIONS
        .map((s) => ({ sectionKey: s.key, labelKey: s.labelKey, icon: s.icon })),
    });
  }

  groups.push(SYSTEM_GROUP);

  return (
    <aside
      className="fixed left-0 top-0 z-40 flex h-screen flex-col bg-aide-sidebar-bg transition-[width] duration-200"
      style={{ width: collapsed ? 64 : 240, borderRight: '1px solid var(--aide-sidebar-border)' }}
    >
      {/* Logo */}
      <div className="flex h-16 items-center px-4" style={{ borderBottom: '1px solid var(--aide-sidebar-border)' }}>
        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600">
          <FlaskConical className="h-4 w-4 text-white" />
        </div>
        {!collapsed && (
          <span className="ml-2.5 text-lg font-semibold tracking-tight text-aide-sidebar-text">
            AIDE
          </span>
        )}
      </div>

      {/* Grouped Navigation */}
      <nav className="flex-1 overflow-y-auto px-2 py-4 space-y-5">
        {groups.map((group) => {
          const groupLabel = t(group.labelKey);
          const isGroupCollapsed = collapsedGroups[groupLabel];
          return (
            <div key={group.labelKey}>
              {!collapsed && (
                <button
                  onClick={() => toggleGroup(groupLabel)}
                  className="mb-1.5 flex w-full items-center justify-between px-3"
                >
                  <span className={`text-[10px] font-bold uppercase tracking-widest ${group.color}`}>
                    {groupLabel}
                  </span>
                  <ChevronDown
                    className={`h-3 w-3 text-aide-sidebar-text-muted transition-transform ${
                      isGroupCollapsed ? "-rotate-90" : ""
                    }`}
                  />
                </button>
              )}

              {!isGroupCollapsed && (
                <div className={collapsed ? "space-y-0.5" : "ml-3 space-y-0.5 pl-2"} style={collapsed ? undefined : { borderLeft: '2px solid var(--aide-sidebar-border)' }}>
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    const label = t(item.labelKey);
                    const isActive = item.href
                      ? item.href === "/"
                        ? pathname === "/"
                        : pathname.startsWith(item.href)
                      : projectCtx?.activeSection === item.sectionKey;

                    const el = (
                      <div
                        className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors cursor-pointer ${
                          isActive
                            ? "bg-aide-sidebar-bg-active text-aide-sidebar-text-active"
                            : "text-aide-sidebar-text-muted hover:bg-aide-sidebar-bg-hover hover:text-aide-sidebar-text"
                        }`}
                        title={collapsed ? label : undefined}
                      >
                        <Icon className="h-4 w-4 flex-shrink-0" />
                        {!collapsed && <span>{label}</span>}
                      </div>
                    );

                    if (item.href) {
                      return (
                        <Link key={item.labelKey} href={item.href}>
                          {el}
                        </Link>
                      );
                    }

                    return (
                      <button
                        key={item.labelKey}
                        className="w-full text-left"
                        onClick={() => item.sectionKey && projectCtx?.setActiveSection(item.sectionKey)}
                      >
                        {el}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Bottom: Version + Collapse */}
      <div className="px-3 py-3 flex items-center justify-between" style={{ borderTop: '1px solid var(--aide-sidebar-border)' }}>
        {!collapsed && (
          <p className="text-xs text-aide-sidebar-text-muted truncate">AIDE v0.1</p>
        )}
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="rounded-lg p-1.5 text-aide-sidebar-text-muted transition-colors hover:bg-aide-sidebar-bg-hover hover:text-aide-sidebar-text ml-auto"
          title={collapsed ? t("nav.expandSidebar") : t("nav.collapseSidebar")}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </button>
      </div>
    </aside>
  );
}
