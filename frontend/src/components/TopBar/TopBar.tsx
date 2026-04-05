import { Button } from "react-aria-components";
import styles from "./TopBar.module.css";

/* ── Hamburger Icon ────────────────────────────────────��──────────────── */

function HamburgerIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  );
}

/* ���─ Logo Icon ────────────────────────────────────────────────────────── */

function LogoIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect width="32" height="32" rx="0" fill="var(--color-primary)" />
      <text
        x="16"
        y="22"
        textAnchor="middle"
        fill="var(--color-text-inverse)"
        fontFamily="var(--font-heading)"
        fontSize="18"
        fontWeight="700"
      >
        Y
      </text>
    </svg>
  );
}

/* ── User Icon ────────────────────────────────────────────────────────── */

function UserIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

/* ── TopBar ───────────────────────────────────────────────────────────── */

interface TopBarProps {
  onToggleSidebar: () => void;
}

export function TopBar({ onToggleSidebar }: TopBarProps) {
  return (
    <header className={styles.topBar}>
      <div className={styles.left}>
        <Button
          className={styles.hamburger}
          onPress={onToggleSidebar}
          aria-label="Toggle sidebar"
        >
          <HamburgerIcon />
        </Button>
        <div className={styles.brand}>
          <LogoIcon />
          <span className={styles.brandName}>Yes Chef</span>
        </div>
      </div>

      <div className={styles.right}>
        <Button className={styles.signIn}>
          <UserIcon />
          <span>Sign In</span>
        </Button>
      </div>
    </header>
  );
}
