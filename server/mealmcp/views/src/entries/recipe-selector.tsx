import { StrictMode, useState, useMemo } from "react";
import { createRoot } from "react-dom/client";
import { getViewData, sendResult } from "../bridge";
import { Button, Card, MacroBadgeRow } from "../components";
import { colors, radius, spacing } from "../theme";
import type { RecipeHit, RecipeSelectorData } from "../types";
import "../global.css";

/* ── Category Pill ──────────────────────────────────────────────────── */

const CATEGORY_COLORS: Record<string, string> = {
  main: colors.primary,
  side: colors.success,
  snack: colors.warning,
  dessert: colors.fat,
  breakfast: colors.carbs,
};

function CategoryPill({ category }: { category: string | null }) {
  if (!category) return null;
  const color = CATEGORY_COLORS[category] ?? colors.textMuted;

  return (
    <span
      style={{
        fontSize: "0.7rem",
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        color,
        background: `${color}18`,
        padding: `2px ${spacing.sm}`,
        borderRadius: radius.full,
      }}
    >
      {category}
    </span>
  );
}

/* ── Time Badge ─────────────────────────────────────────────────────── */

function TimeBadge({
  prepMinutes,
  cookMinutes,
}: {
  prepMinutes: number | null;
  cookMinutes: number | null;
}) {
  const total = (prepMinutes ?? 0) + (cookMinutes ?? 0);
  if (total === 0) return null;

  return (
    <span style={{ fontSize: "0.75rem", color: colors.textMuted }}>
      {"\u23F1"} {total} min
    </span>
  );
}

/* ── Recipe Card ────────────────────────────────────────────────────── */

function RecipeCard({
  recipe,
  isSelected,
  onSelect,
}: {
  recipe: RecipeHit;
  isSelected: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <Card
      onClick={() => onSelect(recipe.id)}
      style={{
        cursor: "pointer",
        borderColor: isSelected ? colors.primary : colors.border,
        background: isSelected ? colors.primaryBg : colors.surface,
        transition: "all 0.15s ease",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: spacing.sm,
        }}
      >
        <div>
          <h3
            style={{
              fontSize: "0.95rem",
              fontWeight: 600,
              color: colors.text,
              marginBottom: "4px",
            }}
          >
            {recipe.name}
          </h3>
          <div style={{ display: "flex", gap: spacing.sm, alignItems: "center" }}>
            <CategoryPill category={recipe.category} />
            <TimeBadge prepMinutes={recipe.prep_minutes} cookMinutes={recipe.cook_minutes} />
          </div>
        </div>
        {isSelected && (
          <div
            style={{
              width: 24,
              height: 24,
              borderRadius: "50%",
              background: colors.primary,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "14px",
              color: "#fff",
              flexShrink: 0,
            }}
          >
            {"\u2713"}
          </div>
        )}
      </div>

      {recipe.tags.length > 0 && (
        <div
          style={{
            display: "flex",
            gap: "4px",
            flexWrap: "wrap",
            marginBottom: spacing.sm,
          }}
        >
          {recipe.tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              style={{
                fontSize: "0.7rem",
                color: colors.textDim,
                background: colors.surfaceHover,
                padding: `2px ${spacing.xs}`,
                borderRadius: radius.sm,
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {recipe.macro_summary && (
        <MacroBadgeRow macros={recipe.macro_summary} style={{ marginTop: spacing.sm }} />
      )}
    </Card>
  );
}

/* ── Filter Bar ─────────────────────────────────────────────────────── */

function FilterBar({
  categories,
  selected,
  onChange,
}: {
  categories: string[];
  selected: string | null;
  onChange: (cat: string | null) => void;
}) {
  return (
    <div style={{ display: "flex", gap: spacing.sm, marginBottom: spacing.lg, flexWrap: "wrap" }}>
      <Button
        variant={!selected ? "primary" : "secondary"}
        onClick={() => onChange(null)}
        style={{ padding: `6px ${spacing.md}`, fontSize: "0.8rem" }}
      >
        All
      </Button>
      {categories.map((cat) => (
        <Button
          key={cat}
          variant={selected === cat ? "primary" : "secondary"}
          onClick={() => onChange(cat)}
          style={{ padding: `6px ${spacing.md}`, fontSize: "0.8rem" }}
        >
          {cat.charAt(0).toUpperCase() + cat.slice(1)}
        </Button>
      ))}
    </div>
  );
}

/* ── Main App ───────────────────────────────────────────────────────── */

function RecipeSelectorApp() {
  const data = getViewData<RecipeSelectorData>();
  const recipes = data.recipes ?? [];

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

  const categories = useMemo(() => {
    const cats = new Set(recipes.map((r) => r.category).filter(Boolean) as string[]);
    return [...cats].sort();
  }, [recipes]);

  const filtered = useMemo(
    () => (categoryFilter ? recipes.filter((r) => r.category === categoryFilter) : recipes),
    [recipes, categoryFilter],
  );

  const handleConfirm = () => {
    if (!selectedId) return;
    const recipe = recipes.find((r) => r.id === selectedId);
    sendResult({
      action: "select_recipe",
      recipe_id: selectedId,
      recipe_name: recipe?.name ?? "",
    });
  };

  return (
    <div className="view-container">
      <div className="view-header">
        <h1>Select a Recipe</h1>
        <p>
          {recipes.length} recipe{recipes.length !== 1 ? "s" : ""} found — tap to select.
        </p>
      </div>

      {categories.length > 1 && (
        <FilterBar categories={categories} selected={categoryFilter} onChange={setCategoryFilter} />
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: spacing.md,
        }}
      >
        {filtered.map((recipe) => (
          <RecipeCard
            key={recipe.id}
            recipe={recipe}
            isSelected={selectedId === recipe.id}
            onSelect={setSelectedId}
          />
        ))}
      </div>

      {filtered.length === 0 && (
        <div style={{ textAlign: "center", padding: spacing.xl, color: colors.textMuted }}>
          No recipes match the current filter.
        </div>
      )}

      <div
        style={{
          marginTop: spacing.xl,
          display: "flex",
          justifyContent: "flex-end",
          gap: spacing.md,
          position: "sticky",
          bottom: spacing.lg,
          background: colors.bg,
          padding: `${spacing.md} 0`,
        }}
      >
        <Button variant="secondary" onClick={() => setSelectedId(null)}>
          Clear
        </Button>
        <Button onClick={handleConfirm} disabled={!selectedId}>
          View Recipe Details
        </Button>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RecipeSelectorApp />
  </StrictMode>,
);
