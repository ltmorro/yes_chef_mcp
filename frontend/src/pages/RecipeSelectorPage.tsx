import { useState, useMemo, useEffect } from "react";
import { Button, RecipeCard } from "../components";
import type { RecipeHit, RecipeSelectorData } from "../types.ts";
import { fetchRecipes } from "../api.ts";
import styles from "./RecipeSelectorPage.module.css";

/* ── Data source ─────────────────────────────────────────────────────── */

/**
 * Where the page gets its data and sends its actions. In an MCP host the
 * data is the show_recipe_selector tool result; in the SPA it is REST.
 */
export interface RecipeSelectorSource {
  /** null while loading. */
  data: RecipeSelectorData | null;
  /** Omitted in the SPA, where the details button has no action yet. */
  onViewDetails?: (recipe: RecipeHit) => void;
}

/** SPA data source backed by the REST API. */
export function useRestRecipeSelectorSource(): RecipeSelectorSource {
  const [data, setData] = useState<RecipeSelectorData | null>(null);

  useEffect(() => {
    fetchRecipes()
      .then((recipes) => setData({ recipes }))
      .catch(() => setData({ recipes: [] })); // API unavailable
  }, []);

  return { data };
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

/* ── Page Component ──────────────────────────────────────────────────── */

interface RecipeSelectorPageProps {
  source: RecipeSelectorSource;
}

const NO_RECIPES: RecipeHit[] = [];

export function RecipeSelectorPage({ source }: RecipeSelectorPageProps) {
  const { data, onViewDetails } = source;
  const recipes = data?.recipes ?? NO_RECIPES;
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

  const selectedRecipe = recipes.find((r) => r.id === selectedId);

  if (!data) {
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
        <Button
          isDisabled={!selectedRecipe}
          onPress={selectedRecipe && onViewDetails ? () => onViewDetails(selectedRecipe) : undefined}
        >
          View Recipe Details
        </Button>
      </div>
    </div>
  );
}
