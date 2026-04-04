import { StrictMode, useState, useMemo, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { connectApp, callTool, getViewData } from "../bridge";
import { Button, Card, MacroBadgeRow } from "../components";
import type { RecipeHit, RecipeSelectorData } from "../types";
import "../global.css";
import styles from "./recipe-selector.module.css";

/* ── Category Pill ────────────────────────────────────────────────────── */

const CATEGORY_CLASS: Record<string, string> = {
  main: styles.categoryMain ?? "",
  side: styles.categorySide ?? "",
  snack: styles.categorySnack ?? "",
  dessert: styles.categoryDessert ?? "",
  breakfast: styles.categoryBreakfast ?? "",
};

function CategoryPill({ category }: { category: string | null }) {
  if (!category) return null;
  const colorClass = CATEGORY_CLASS[category] ?? styles.categoryDefault;

  return (
    <span className={`${styles.categoryPill} ${colorClass}`}>
      {category}
    </span>
  );
}

/* ── Time Badge ───────────────────────────────────────────────────────── */

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
    <span className={styles.timeBadge}>
      {"\u23F1"} {total} min
    </span>
  );
}

/* ── Recipe Card ──────────────────────────────────────────────────────── */

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
      selected={isSelected}
    >
      <div className={styles.recipeCardHeader}>
        <div>
          <h3 className={styles.recipeName}>{recipe.name}</h3>
          <div className={styles.recipeMeta}>
            <CategoryPill category={recipe.category} />
            <TimeBadge prepMinutes={recipe.prep_minutes} cookMinutes={recipe.cook_minutes} />
          </div>
        </div>
        {isSelected && (
          <div className={styles.checkmark}>{"\u2713"}</div>
        )}
      </div>

      {recipe.tags.length > 0 && (
        <div className={styles.tags}>
          {recipe.tags.slice(0, 4).map((tag) => (
            <span key={tag} className={styles.tag}>{tag}</span>
          ))}
        </div>
      )}

      {recipe.macro_summary && (
        <MacroBadgeRow macros={recipe.macro_summary} className={styles.macros} />
      )}
    </Card>
  );
}

/* ── Filter Bar ───────────────────────────────────────────────────────── */

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
    <div className={styles.filterBar}>
      <Button
        variant={!selected ? "primary" : "secondary"}
        size="sm"
        onPress={() => onChange(null)}
      >
        All
      </Button>
      {categories.map((cat) => (
        <Button
          key={cat}
          variant={selected === cat ? "primary" : "secondary"}
          size="sm"
          onPress={() => onChange(cat)}
        >
          {cat.charAt(0).toUpperCase() + cat.slice(1)}
        </Button>
      ))}
    </div>
  );
}

/* ── Main App ─────────────────────────────────────────────────────────── */

function RecipeSelectorApp() {
  const data = getViewData<RecipeSelectorData>();
  const recipes = data.recipes ?? [];

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

  useEffect(() => { connectApp("Recipe Selector"); }, []);

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
    callTool("select_recipe", {
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

      <div className={styles.recipeGrid}>
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
        <div className={styles.empty}>
          No recipes match the current filter.
        </div>
      )}

      <div className={styles.footer}>
        <Button variant="secondary" onPress={() => setSelectedId(null)}>
          Clear
        </Button>
        <Button onPress={handleConfirm} isDisabled={!selectedId}>
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
