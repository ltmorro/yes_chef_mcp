import { StrictMode, useState, useCallback } from "react";
import { createRoot } from "react-dom/client";
import { AppShell } from "../components";
import type { Page } from "../components";
import {
  MacroSetterPage,
  RecipeSelectorPage,
  WeeklyCalendarPage,
  GroceryListPage,
} from "../pages";
import "../global.css";

/* ── Page Router ──────────────────────────────────────────────────────── */

function PageContent({ page }: { page: Page }) {
  switch (page) {
    case "macros":
      return <MacroSetterPage />;
    case "recipes":
      return <RecipeSelectorPage />;
    case "calendar":
      return <WeeklyCalendarPage />;
    case "grocery":
      return <GroceryListPage />;
  }
}

/* ── App ──────────────────────────────────────────────────────────────── */

function App() {
  const [activePage, setActivePage] = useState<Page>("macros");
  const [sidebarExpanded, setSidebarExpanded] = useState(false);

  const handleToggleSidebar = useCallback(() => {
    setSidebarExpanded((prev) => !prev);
  }, []);

  return (
    <AppShell
      activePage={activePage}
      onNavigate={setActivePage}
      sidebarExpanded={sidebarExpanded}
      onToggleSidebar={handleToggleSidebar}
    >
      <PageContent page={activePage} />
    </AppShell>
  );
}

/* ── Mount ─────────────────────────────────────────────────────────────── */

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
