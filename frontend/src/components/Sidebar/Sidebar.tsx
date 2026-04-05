import { type ReactNode } from "react";
import { Button } from "react-aria-components";
import styles from "./Sidebar.module.css";

/* ── Page Type ────────────────────────────────────────────────────────── */

export type Page = "macros" | "recipes" | "calendar" | "grocery";

/* ── SVG Icons ────────────────────────────────────────────────────────── */

function TargetIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </svg>
  );
}

function BookIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      <line x1="8" y1="7" x2="16" y2="7" />
      <line x1="8" y1="11" x2="13" y2="11" />
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="0" ry="0" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

function CartIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9" cy="21" r="1" />
      <circle cx="20" cy="21" r="1" />
      <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
    </svg>
  );
}

/* ── Nav Items ────────────────────────────────────────────────────────── */

interface NavItem {
  page: Page;
  label: string;
  icon: ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { page: "macros", label: "Macros", icon: <TargetIcon /> },
  { page: "recipes", label: "Recipes", icon: <BookIcon /> },
  { page: "calendar", label: "Calendar", icon: <CalendarIcon /> },
  { page: "grocery", label: "Grocery", icon: <CartIcon /> },
];

/* ── Sidebar ──────────────────────────────────────────────────────────── */

interface SidebarProps {
  activePage: Page;
  onNavigate: (page: Page) => void;
  isExpanded: boolean;
}

export function Sidebar({ activePage, onNavigate, isExpanded }: SidebarProps) {
  return (
    <nav
      className={`${styles.sidebar} ${isExpanded ? styles.expanded : styles.collapsed}`}
      aria-label="Main navigation"
    >
      <ul className={styles.navList}>
        {NAV_ITEMS.map(({ page, label, icon }) => {
          const isActive = activePage === page;
          return (
            <li key={page}>
              <Button
                className={`${styles.navItem} ${isActive ? styles.navItemActive : ""}`}
                onPress={() => onNavigate(page)}
                aria-current={isActive ? "page" : undefined}
              >
                <span className={styles.navIcon}>{icon}</span>
                <span className={styles.navLabel}>{label}</span>
              </Button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
