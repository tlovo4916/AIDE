"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

export type ProjectSection = "overview" | "blackboard" | "messages" | "knowledge" | "paper" | "evaluation";

interface ProjectSidebarContextValue {
  projectName: string;
  activeSection: ProjectSection;
  setActiveSection: (s: ProjectSection) => void;
  hasPaper: boolean;
}

const ProjectSidebarContext = createContext<ProjectSidebarContextValue | null>(null);

export function useProjectSidebar() {
  return useContext(ProjectSidebarContext);
}

interface ProjectSidebarProviderProps {
  projectName: string;
  hasPaper: boolean;
  children: ReactNode;
}

export function ProjectSidebarProvider({
  projectName,
  hasPaper,
  children,
}: ProjectSidebarProviderProps) {
  const [activeSection, setActiveSection] = useState<ProjectSection>("overview");

  return (
    <ProjectSidebarContext.Provider
      value={{ projectName, activeSection, setActiveSection, hasPaper }}
    >
      {children}
    </ProjectSidebarContext.Provider>
  );
}
