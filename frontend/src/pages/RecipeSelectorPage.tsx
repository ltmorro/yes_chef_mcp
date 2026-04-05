import { useState, useMemo, useEffect } from "react";
import { Button, RecipeCard } from "../components";
import type { RecipeHit } from "../types.ts";
import { fetchRecipes } from "../api.ts";
import styles from "./RecipeSelectorPage.module.css";

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

/* ── Page Component ──────────────────────────────────────────────────── */

export function RecipeSelectorPage() {
  const [recipes, setRecipes] = useState<RecipeHit[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRecipes()
      .then(setRecipes)
      .catch(() => { /* API unavailable */ })
      .finally(() => setLoading(false));
  }, []);

  const categories = useMemo(() => {
    const cats = new Set(recipes.map((r) => r.category).filter(Boolean) as string[]);
    return [...cats].sort();
  }, [recipes]);

  const filtered = useMemo(
    () => (categoryFilter ? recipes.filter((r) => r.category === categoryFilter) : recipes),
    [recipes, categoryFilter],
  );

  if (loading) {
    return (
      <div>
        <div className={styles.loading}>Loading recipes...</div>
      </div>
    );
  }

  return (
    <div>
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
            {...recipe}
            isSelected={selectedId === recipe.id}
            onSelect={setSelectedId}
          />
        ))}
      </div>

      {filtered.length === 0 && (
        <div className={styles.empty}>
          {recipes.length === 0
            ? "No recipes available. Add some recipes to get started."
            : "No recipes match the current filter."}
        </div>
      )}

      <div className={styles.footer}>
        <Button variant="secondary" onPress={() => setSelectedId(null)}>
          Clear
        </Button>
        <Button isDisabled={!selectedId}>
          View Recipe Details
        </Button>
      </div>
    </div>
  );
}
