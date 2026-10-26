import { StrictMode, useState, useCallback } from "react";
import { createRoot } from "react-dom/client";
import { AppShell } from "../components";
import type { Page } from "../components";
import {
  MacroSetterPage,
  RecipeSelectorPage,
  WeeklyCalendarPage,
  GroceryListPage,
  useRestMacroSetterSource,
  useRestRecipeSelectorSource,
  useRestWeeklyCalendarSource,
  useRestGroceryListSource,
} from "../pages";
import "../global.css";

/* ── REST-backed pages ────────────────────────────────────────────────── */
// The same page components the MCP views use, fed from the REST API.

function MacrosRoute() {
  return <MacroSetterPage source={useRestMacroSetterSource()} />;
}

function RecipesRoute() {
  return <RecipeSelectorPage source={useRestRecipeSelectorSource()} />;
}

function CalendarRoute() {
  return <WeeklyCalendarPage source={useRestWeeklyCalendarSource()} />;
}

function GroceryRoute() {
  return <GroceryListPage source={useRestGroceryListSource()} />;
}

/* ── Page Router ──────────────────────────────────────────────────────── */

interface PageContentProps {
  page: Page;
}

function PageContent({ page }: PageContentProps) {
  switch (page) {
    case "macros":
      return <MacrosRoute />;
    case "recipes":
      return <RecipesRoute />;
    case "calendar":
      return <CalendarRoute />;
    case "grocery":
      return <GroceryRoute />;
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
