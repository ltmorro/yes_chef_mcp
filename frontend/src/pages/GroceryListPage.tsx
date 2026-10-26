import { useState, useMemo, useCallback, useEffect } from "react";
import { Checkbox } from "react-aria-components";
import { ActionStatus, Button, Card, FullscreenToggle } from "../components";
import type { DisplayModeControl } from "../bridge.ts";
import type { GroceryItem, GroceryListData } from "../types.ts";
import { fetchPlans, fetchGroceryList } from "../api.ts";
import { useAsyncAction } from "../useAsyncAction.ts";
import styles from "./GroceryListPage.module.css";

/* ── Data source ─────────────────────────────────────────────────────── */

interface PlanOption {
  id: string;
  name: string;
}

interface PlanPicker {
  options: PlanOption[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export interface GroceryConfirmation {
  items: GroceryItem[];
  checked_off_count: number;
  total_count: number;
}

/**
 * Where the page gets its data and sends its actions. In an MCP host the
 * data is the show_grocery_checklist tool result for one plan; in the SPA it
 * is REST, with a picker over all plans.
 */
export interface GroceryListSource {
  loading: boolean;
  /** null when not loaded yet, or when there is no plan to show. */
  data: GroceryListData | null;
  /** SPA only: choose which plan's list to show. */
  plans?: PlanPicker;
  /**
   * Hand the to-buy list back. Omitted (and the button hidden) in the SPA,
   * which has nowhere to send it yet, and in hosts that can't send messages.
   */
  onConfirm?: (confirmation: GroceryConfirmation) => Promise<void>;
  /** MCP host only, when it offers fullscreen: inline / fullscreen toggle. */
  display?: DisplayModeControl;
}

/** SPA data source backed by the REST API. */
export function useRestGroceryListSource(): GroceryListSource {
  const [plans, setPlans] = useState<PlanOption[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [data, setData] = useState<GroceryListData | null>(null);
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
    fetchGroceryList(selectedPlanId)
      .then((grocery_list) => setData({ grocery_list }))
      .catch(() => setData({ grocery_list: { plan_id: selectedPlanId, items: [] } }))
      .finally(() => setLoading(false));
  }, [selectedPlanId]);

  return {
    loading,
    data,
    plans: { options: plans, selectedId: selectedPlanId, onSelect: setSelectedPlanId },
  };
}

/* ── Plan Selector ───────────────────────────────────────────────────── */

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

interface ChecklistItemProps {
  item: GroceryItem;
  isChecked: boolean;
  onToggle: () => void;
}

/**
 * The whole row is the checkbox (RAC renders a <label> around a hidden
 * input), so a click anywhere toggles once and the box is visible.
 */
function ChecklistItem({ item, isChecked, onToggle }: ChecklistItemProps) {
  const displayQty = item.quantity
    ? `${item.quantity}${item.unit ? " " + item.unit : ""}`
    : "";

  return (
    <Checkbox
      className={styles.checklistItem}
      isSelected={isChecked}
      onChange={onToggle}
      aria-label={`${item.name}${displayQty ? ` (${displayQty})` : ""}`}
    >
      <span className={styles.checkbox} aria-hidden="true">
        {isChecked && (
          <svg viewBox="0 0 16 16" className={styles.checkmark}>
            <path d="M4 8.5l2.5 2.5L12 5.5" />
          </svg>
        )}
      </span>

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
    </Checkbox>
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
          {remaining === 0 ? "✓" : remaining}
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

interface GroceryListPageProps {
  source: GroceryListSource;
}

const NO_ITEMS: GroceryItem[] = [];

export function GroceryListPage({ source }: GroceryListPageProps) {
  const { loading, data, plans, onConfirm, display } = source;
  const items = data?.grocery_list.items ?? NO_ITEMS;
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set());
  const [confirmState, runConfirm] = useAsyncAction();

  // A new list (another plan, or a new tool result) starts fully unchecked
  useEffect(() => {
    setCheckedIds(new Set());
  }, [data]);

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

  const handleConfirm = useCallback(() => {
    if (!onConfirm) return;
    const toBuy = items.filter((_, idx) => !checkedIds.has(idx));
    runConfirm("Sending…", async () => {
      await onConfirm({
        items: toBuy,
        checked_off_count: checkedIds.size,
        total_count: items.length,
      });
      const noun = toBuy.length === 1 ? "item" : "items";
      return `Sent your shopping list (${toBuy.length} ${noun}) to the conversation.`;
    });
  }, [onConfirm, runConfirm, items, checkedIds]);

  if (loading && items.length === 0) {
    return (
      <div>
        <div className={styles.loading}>Loading grocery list...</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div>
        <div className="view-header">
          <h1>Grocery List</h1>
          <p>No meal plans found. Create a plan to generate a grocery list.</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className={styles.headerRow}>
        <div className="view-header">
          <h1>Grocery List</h1>
          <p>Check off items you already have. Unchecked items will be your shopping list.</p>
        </div>
        {display && <FullscreenToggle display={display} />}
      </div>

      {plans && (
        <PlanSelector plans={plans.options} selectedId={plans.selectedId} onSelect={plans.onSelect} />
      )}

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
        {onConfirm && (
          <Button
            isDisabled={items.length === 0 || confirmState.kind === "pending"}
            onPress={handleConfirm}
          >
            {checkedIds.size === items.length
              ? "All Items In Pantry"
              : `Confirm List (${items.length - checkedIds.size} items)`}
          </Button>
        )}
      </div>
      <ActionStatus state={confirmState} />
    </div>
  );
}
