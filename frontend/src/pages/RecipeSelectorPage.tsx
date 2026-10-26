import { useState, useMemo, useEffect } from "react";
import { ActionStatus, Button, RecipeCard } from "../components";
import type { RecipeHit, RecipeSelectorData } from "../types.ts";
import { fetchRecipes } from "../api.ts";
import { useAsyncAction } from "../useAsyncAction.ts";
import styles from "./RecipeSelectorPage.module.css";

/* ── Data source ─────────────────────────────────────────────────────── */

/**
 * Where the page gets its data and sends its actions. In an MCP host the
 * data is the show_recipe_selector tool result; in the SPA it is REST.
 */
export interface RecipeSelectorSource {
  /** null while loading. */
  data: RecipeSelectorData | null;
  /** Called when the user selects or clears a recipe (null = cleared). */
  onSelectionChange?: (recipe: RecipeHit | null) => void;
  /**
   * Hand the chosen recipe back. Omitted (and the button hidden) in the SPA,
   * which has nothing to hand it to, and in hosts that can't send messages.
   */
  onConfirm?: (recipe: RecipeHit) => Promise<void>;
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
  const { data, onSelectionChange, onConfirm } = source;
  const recipes = data?.recipes ?? NO_RECIPES;
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [confirmState, runConfirm] = useAsyncAction();

  const categories = useMemo(() => {
    const cats = new Set(recipes.map((r) => r.category).filter(Boolean) as string[]);
    return [...cats].sort();
  }, [recipes]);

  const filtered = useMemo(
    () => (categoryFilter ? recipes.filter((r) => r.category === categoryFilter) : recipes),
    [recipes, categoryFilter],
  );

  const selectedRecipe = recipes.find((r) => r.id === selectedId);

  const select = (id: string | null) => {
    if (id === selectedId) return;
    setSelectedId(id);
    onSelectionChange?.(recipes.find((r) => r.id === id) ?? null);
  };

  const confirm = () => {
    if (!selectedRecipe || !onConfirm) return;
    const recipe = selectedRecipe;
    runConfirm("Sending…", async () => {
      await onConfirm(recipe);
      return `Sent "${recipe.name}" to the conversation.`;
    });
  };

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
            onSelect={select}
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
        <Button variant="secondary" onPress={() => select(null)}>
          Clear
        </Button>
        {onConfirm && (
          <Button
            isDisabled={!selectedRecipe || confirmState.kind === "pending"}
            onPress={confirm}
          >
            Use This Recipe
          </Button>
        )}
      </div>
      <ActionStatus state={confirmState} />
    </div>
  );
}
