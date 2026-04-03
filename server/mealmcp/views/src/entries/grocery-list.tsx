import { StrictMode, useState, useMemo, useCallback, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { connectApp, callTool, getViewData } from "../bridge";
import { Button, Card } from "../components";
import { colors, radius, spacing, font } from "../theme";
import type { GroceryItem, GroceryListData } from "../types";
import "../global.css";

/* ── Category Header ────────────────────────────────────────────────── */

function CategoryHeader({
  name,
  count,
  checkedCount,
}: {
  name: string;
  count: number;
  checkedCount: number;
}) {
  const allChecked = checkedCount === count;

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: `${spacing.sm} 0`,
        marginTop: spacing.md,
        borderBottom: `1px solid ${colors.border}`,
      }}
    >
      <h2
        style={{
          fontSize: "0.85rem",
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          color: allChecked ? colors.textDim : colors.text,
        }}
      >
        {name}
      </h2>
      <span style={{ fontSize: "0.75rem", color: colors.textMuted, fontFamily: font.mono }}>
        {checkedCount}/{count}
      </span>
    </div>
  );
}

/* ── Checklist Item ─────────────────────────────────────────────────── */

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
    <div
      onClick={onToggle}
      style={{
        display: "flex",
        alignItems: "center",
        gap: spacing.md,
        padding: `${spacing.sm} ${spacing.md}`,
        borderRadius: radius.sm,
        cursor: "pointer",
        transition: "background 0.1s ease",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = colors.surfaceHover;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "transparent";
      }}
    >
      {/* Checkbox */}
      <div
        style={{
          width: 20,
          height: 20,
          borderRadius: radius.sm,
          border: `2px solid ${isChecked ? colors.success : colors.border}`,
          background: isChecked ? colors.successBg : "transparent",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          transition: "all 0.15s ease",
        }}
      >
        {isChecked && <span style={{ color: colors.success, fontSize: "12px" }}>{"\u2713"}</span>}
      </div>

      {/* Item details */}
      <div style={{ flex: 1 }}>
        <span
          style={{
            fontSize: "0.9rem",
            color: isChecked ? colors.textDim : colors.text,
            textDecoration: isChecked ? "line-through" : "none",
            transition: "all 0.15s ease",
          }}
        >
          {item.name}
        </span>
        {displayQty && (
          <span
            style={{
              marginLeft: spacing.sm,
              fontSize: "0.8rem",
              color: colors.textMuted,
              fontFamily: font.mono,
            }}
          >
            {displayQty}
          </span>
        )}
      </div>

      {/* Recipe sources */}
      {item.recipe_sources.length > 0 && (
        <div
          style={{
            fontSize: "0.7rem",
            color: colors.textDim,
            maxWidth: "120px",
            textAlign: "right",
            lineHeight: 1.3,
          }}
        >
          {item.recipe_sources.join(", ")}
        </div>
      )}
    </div>
  );
}

/* ── Summary Bar ────────────────────────────────────────────────────── */

function SummaryBar({ total, checked }: { total: number; checked: number }) {
  const remaining = total - checked;
  const pct = total > 0 ? (checked / total) * 100 : 0;

  return (
    <Card
      style={{
        display: "flex",
        alignItems: "center",
        gap: spacing.lg,
        marginBottom: spacing.lg,
      }}
    >
      <div style={{ flex: 1 }}>
        <div
          style={{
            height: "6px",
            background: colors.border,
            borderRadius: radius.full,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${pct}%`,
              height: "100%",
              background: pct === 100 ? colors.success : colors.primary,
              borderRadius: radius.full,
              transition: "width 0.3s ease",
            }}
          />
        </div>
        <div style={{ fontSize: "0.75rem", color: colors.textMuted, marginTop: spacing.xs }}>
          {checked} of {total} items checked off
        </div>
      </div>
      <div
        style={{
          fontSize: "1.5rem",
          fontWeight: 700,
          color: remaining === 0 ? colors.success : colors.text,
          fontFamily: font.mono,
          minWidth: "60px",
          textAlign: "center",
        }}
      >
        {remaining === 0 ? "\u2713" : remaining}
      </div>
    </Card>
  );
}

/* ── Main App ───────────────────────────────────────────────────────── */

interface IndexedItem extends GroceryItem {
  _idx: number;
}

interface CategoryGroup {
  category: string;
  items: IndexedItem[];
}

function GroceryListApp() {
  const data = getViewData<GroceryListData>();
  const items = data.grocery_list?.items ?? [];

  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set());

  useEffect(() => { connectApp("Grocery List"); }, []);

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

  const handleFinalize = useCallback(() => {
    const uncheckedItems = items.filter((_, idx) => !checkedIds.has(idx));
    callTool("confirm_grocery_list", {
      items: uncheckedItems,
      checked_off_count: checkedIds.size,
      total_count: items.length,
    });
  }, [items, checkedIds]);

  return (
    <div className="view-container" style={{ maxWidth: "700px" }}>
      <div className="view-header">
        <h1>Grocery List</h1>
        <p>Check off items you already have. Unchecked items will be your shopping list.</p>
      </div>

      <SummaryBar total={items.length} checked={checkedIds.size} />

      {grouped.map(({ category, items: catItems }) => {
        const checkedCount = catItems.filter((it) => checkedIds.has(it._idx)).length;
        return (
          <div key={category}>
            <div
              style={{ cursor: "pointer" }}
              onClick={() => {
                if (checkedCount < catItems.length) checkAll(category);
              }}
            >
              <CategoryHeader name={category} count={catItems.length} checkedCount={checkedCount} />
            </div>
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
        <div style={{ textAlign: "center", padding: spacing.xl, color: colors.textMuted }}>
          No items in the grocery list.
        </div>
      )}

      <div
        style={{
          marginTop: spacing.xl,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          position: "sticky",
          bottom: spacing.lg,
          background: colors.bg,
          padding: `${spacing.md} 0`,
        }}
      >
        <Button variant="ghost" onClick={() => setCheckedIds(new Set())}>
          Uncheck All
        </Button>
        <Button onClick={handleFinalize} disabled={items.length === 0}>
          {checkedIds.size === items.length
            ? "All Items In Pantry"
            : `Confirm List (${items.length - checkedIds.size} items)`}
        </Button>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <GroceryListApp />
  </StrictMode>,
);
