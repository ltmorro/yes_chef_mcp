import { Card } from "../Card";
import { MacroBadgeRow } from "../MacroBadge";
import type { RecipeHit } from "../../types.ts";
import styles from "./RecipeCard.module.css";

interface RecipeCardProps extends RecipeHit {
  isSelected?: boolean;
  onSelect?: (id: string) => void;
}

export type { RecipeCardProps };

const CATEGORY_CLASS: Record<string, string> = {
  main: styles.categoryMain ?? "",
  side: styles.categorySide ?? "",
  snack: styles.categorySnack ?? "",
  dessert: styles.categoryDessert ?? "",
  breakfast: styles.categoryBreakfast ?? "",
};

function CategoryPill({ category }: { category: string }) {
  const colorClass = CATEGORY_CLASS[category] ?? styles.categoryDefault;
  return (
    <span className={`${styles.categoryPill} ${colorClass}`}>{category}</span>
  );
}

function TimeBadge({
  prep_minutes,
  cook_minutes,
}: {
  prep_minutes: number | null;
  cook_minutes: number | null;
}) {
  const total = (prep_minutes ?? 0) + (cook_minutes ?? 0);
  if (total === 0) return null;
  return <span className={styles.timeBadge}>⏱ {total} min</span>;
}

export function RecipeCard({
  id,
  name,
  category,
  tags,
  prep_minutes,
  cook_minutes,
  macro_summary,
  isSelected,
  onSelect,
}: RecipeCardProps) {
  return (
    <Card
      onPress={onSelect ? () => onSelect(id) : undefined}
      selected={isSelected}
      pretitle={
        <div className={styles.recipeMeta}>
          {category && <CategoryPill category={category} />}
          <TimeBadge prep_minutes={prep_minutes} cook_minutes={cook_minutes} />
        </div>
      }
      title={<span className={styles.recipeName}>{name}</span>}
      trailingMedia={isSelected ? <div className={styles.checkmark}>✓</div> : undefined}
      body={
        <>
          {tags.length > 0 && (
            <div className={styles.tags}>
              {tags.slice(0, 4).map((tag) => (
                <span key={tag} className={styles.tag}>{tag}</span>
              ))}
            </div>
          )}
          <MacroBadgeRow macros={macro_summary} />
        </>
      }
    />
  );
}