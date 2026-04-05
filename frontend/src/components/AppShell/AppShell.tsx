import { type ReactNode } from "react";
import { TopBar } from "../TopBar";
import { Sidebar } from "../Sidebar";
import type { Page } from "../Sidebar";
import styles from "./AppShell.module.css";

interface AppShellProps {
  activePage: Page;
  onNavigate: (page: Page) => void;
  sidebarExpanded: boolean;
  onToggleSidebar: () => void;
  children: ReactNode;
}

export function AppShell({
  activePage,
  onNavigate,
  sidebarExpanded,
  onToggleSidebar,
  children,
}: AppShellProps) {
  return (
    <div className={styles.shell}>
      <TopBar onToggleSidebar={onToggleSidebar} />
      <Sidebar
        activePage={activePage}
        onNavigate={onNavigate}
        isExpanded={sidebarExpanded}
      />
      <main
        className={`${styles.content} ${sidebarExpanded ? styles.contentExpanded : styles.contentCollapsed}`}
      >
        <div className={styles.contentInner}>
          {children}
        </div>
      </main>
    </div>
  );
}
