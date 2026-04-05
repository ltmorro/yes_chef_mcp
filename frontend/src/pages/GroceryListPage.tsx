import { useState, useMemo, useCallback, useEffect } from "react";
import { Checkbox } from "react-aria-components";
import { Button, Card } from "../components";
import type { GroceryItem } from "../types.ts";
import { fetchPlans, fetchGroceryList } from "../api.ts";
import styles from "./GroceryListPage.module.css";

/* ── Plan Selector ───────────────────────────────────────────────────── */

interface PlanOption {
  id: string;
  name: string;
}

function PlanSelector({
  plans,
  selectedId,
  onSelect,
}: {
  plans: PlanOption[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (plans.length === 0) return null;

  return (
    <div className={styles.planSelector}>
      {plans.map((plan) => (
        <Button
          key={plan.id}
          variant={selectedId === plan.id ? "primary" : "secondary"}
          size="sm"
          onPress={() => onSelect(plan.id)}
        >
          {plan.name}
        </Button>
      ))}
    </div>
  );
}

/* ── Category Header ──────────────────────────────────────────────────── */

function CategoryHeader({
  name,
  count,
  checkedCount,
  onCheckAll,
}: {
  name: string;
  count: number;
  checkedCount: number;
  onCheckAll: () => void;
}) {
  const allChecked = checkedCount === count;

  return (
    <div className={styles.categoryHeader} onClick={onCheckAll}>
      <h2 className={`${styles.categoryName} ${allChecked ? styles.categoryNameDone : ""}`}>
        {name}
      </h2>
      <span className={styles.categoryCount}>
        {checkedCount}/{count}
      </span>
    </div>
  );
}

/* ── Checklist Item ───────────────────────────────────────────────────── */

function ChecklistItem({
  item,
  isChecked,
  onToggle,
}: {
  item: GroceryItem;
  isChecked: boolean;
  onToggle: () => void;
}) {
  const displayQty = item.quantity
    ? `${item.quantity}${item.unit ? " " + item.unit : ""}`
    : "";

  return (
    <div className={styles.checklistItem} onClick={onToggle}>
      <div className={styles.checkboxWrapper}>
        <Checkbox
          isSelected={isChecked}
          onChange={onToggle}
          aria-label={`${item.name}${displayQty ? ` (${displayQty})` : ""}`}
        />
      </div>

      <div className={styles.itemDetails}>
        <span className={`${styles.itemName} ${isChecked ? styles.itemNameChecked : ""}`}>
          {item.name}
        </span>
        {displayQty && (
          <span className={styles.itemQty}>{displayQty}</span>
        )}
      </div>

      {item.recipe_sources.length > 0 && (
        <div className={styles.recipeSources}>
          {item.recipe_sources.join(", ")}
        </div>
      )}
    </div>
  );
}

/* ── Summary Bar ──────────────────────────────────────────────────────── */

function SummaryBar({ total, checked }: { total: number; checked: number }) {
  const remaining = total - checked;
  const pct = total > 0 ? (checked / total) * 100 : 0;

  return (
    <Card
      className={styles.summaryCard}
      pretitle="Shopping Status"
      title={
        <div className={styles.summaryTrack}>
          <div
            className={`${styles.summaryFill} ${pct === 100 ? styles.summaryFillComplete : styles.summaryFillActive}`}
            {...{ style: { "--progress-pct": `${pct}%` } as React.CSSProperties }}
          />
        </div>
      }
      subtitle={
        <div>{checked} of {total} items checked off</div>
      }
      trailingMedia={
        <div className={`${styles.summaryCount} ${remaining === 0 ? styles.summaryCountDone : ""}`}>
          {remaining === 0 ? "\u2713" : remaining}
        </div>
      }
    />
  );
}

/* ── Page Component ──────────────────────────────────────────────────── */

interface IndexedItem extends GroceryItem {
  _idx: number;
}

interface CategoryGroup {
  category: string;
  items: IndexedItem[];
}

export function GroceryListPage() {
  const [plans, setPlans] = useState<PlanOption[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [items, setItems] = useState<GroceryItem[]>([]);
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPlans()
      .then((result) => {
        const options = result.map((p) => ({ id: p.id, name: p.name }));
        setPlans(options);
        if (options.length > 0) {
          setSelectedPlanId(options[0]!.id);
        }
      })
      .catch(() => { /* API unavailable */ })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedPlanId) return;
    setLoading(true);
    setCheckedIds(new Set());
    fetchGroceryList(selectedPlanId)
      .then((result) => setItems(result.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [selectedPlanId]);

  const toggle = useCallback((idx: number) => {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }, []);

  const checkAll = useCallback(
    (category: string) => {
      setCheckedIds((prev) => {
        const next = new Set(prev);
        items.forEach((item, idx) => {
          if ((item.category || "other") === category) next.add(idx);
        });
        return next;
      });
    },
    [items],
  );

  const grouped: CategoryGroup[] = useMemo(() => {
    const groups: Record<string, IndexedItem[]> = {};
    items.forEach((item, idx) => {
      const cat = item.category || "other";
      if (!groups[cat]) groups[cat] = [];
      groups[cat]!.push({ ...item, _idx: idx });
    });
    const sorted = Object.keys(groups).sort((a, b) => {
      if (a === "other") return 1;
      if (b === "other") return -1;
      return a.localeCompare(b);
    });
    return sorted.map((cat) => ({ category: cat, items: groups[cat]! }));
  }, [items]);

  if (loading && items.length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>Loading grocery list...</div>
      </div>
    );
  }

  if (plans.length === 0) {
    return (
      <div className={styles.container}>
        <div className="view-header">
          <h1>Grocery List</h1>
          <p>No meal plans found. Create a plan to generate a grocery list.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className="view-header">
        <h1>Grocery List</h1>
        <p>Check off items you already have. Unchecked items will be your shopping list.</p>
      </div>

      <PlanSelector plans={plans} selectedId={selectedPlanId} onSelect={setSelectedPlanId} />

      <SummaryBar total={items.length} checked={checkedIds.size} />

      {grouped.map(({ category, items: catItems }) => {
        const checkedCount = catItems.filter((it) => checkedIds.has(it._idx)).length;
        return (
          <div key={category}>
            <CategoryHeader
              name={category}
              count={catItems.length}
              checkedCount={checkedCount}
              onCheckAll={() => {
                if (checkedCount < catItems.length) checkAll(category);
              }}
            />
            {catItems.map((item) => (
              <ChecklistItem
                key={item._idx}
                item={item}
                isChecked={checkedIds.has(item._idx)}
                onToggle={() => toggle(item._idx)}
              />
            ))}
          </div>
        );
      })}

      {items.length === 0 && (
        <div className={styles.empty}>
          No items in the grocery list.
        </div>
      )}

      <div className={styles.footer}>
        <Button variant="ghost" onPress={() => setCheckedIds(new Set())}>
          Uncheck All
        </Button>
        <Button isDisabled={items.length === 0}>
          {checkedIds.size === items.length
            ? "All Items In Pantry"
            : `Confirm List (${items.length - checkedIds.size} items)`}
        </Button>
      </div>
    </div>
  );
}
