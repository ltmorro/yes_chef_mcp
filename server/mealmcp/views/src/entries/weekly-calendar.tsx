import { StrictMode, useState, useMemo, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { connectApp, callTool, getViewData } from "../bridge";
import { Button, Card, ProgressBar } from "../components";
import { colors, radius, spacing } from "../theme";
import type { DaySummary, MacroSummary, MealComponent, WeeklyCalendarData } from "../types";
import "../global.css";

const DAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MEAL_ORDER = ["breakfast", "lunch", "dinner", "snack"] as const;

/* ── Macro Variance Bar ─────────────────────────────────────────────── */

function MacroVarianceBar({
  actual,
  target,
  nutrient,
  color,
}: {
  actual: number;
  target: number;
  nutrient: string;
  color: string;
}) {
  if (target === 0) return null;
  const pct = (actual / target) * 100;
  const barColor = pct > 105 ? colors.danger : pct < 85 ? colors.warning : color;

  return (
    <div style={{ marginBottom: "4px" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: "0.65rem",
          color: colors.textDim,
          marginBottom: "2px",
        }}
      >
        <span>{nutrient}</span>
        <span style={{ color: barColor, fontWeight: 600 }}>
          {Math.round(actual)}/{Math.round(target)}
        </span>
      </div>
      <div
        style={{
          height: "4px",
          background: colors.border,
          borderRadius: radius.full,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${Math.min(pct, 100)}%`,
            height: "100%",
            background: barColor,
            borderRadius: radius.full,
            transition: "width 0.3s ease",
          }}
        />
      </div>
    </div>
  );
}

/* ── Meal Chip ──────────────────────────────────────────────────────── */

const MEAL_COLORS: Record<string, string> = {
  breakfast: colors.carbs,
  lunch: colors.protein,
  dinner: colors.primary,
  snack: colors.textMuted,
};

function MealChip({ mealType, recipes }: { mealType: string; recipes: MealComponent[] }) {
  const color = MEAL_COLORS[mealType] ?? colors.textMuted;

  return (
    <div
      style={{
        padding: `${spacing.xs} ${spacing.sm}`,
        background: `${color}12`,
        borderRadius: radius.sm,
        borderLeft: `3px solid ${color}`,
        marginBottom: "4px",
      }}
    >
      <div
        style={{
          fontSize: "0.65rem",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          color,
          marginBottom: "2px",
        }}
      >
        {mealType}
      </div>
      {recipes.map((r, i) => (
        <div key={i} style={{ fontSize: "0.8rem", color: colors.text, lineHeight: 1.3 }}>
          {r.recipe_name ?? r.recipe_id}
        </div>
      ))}
    </div>
  );
}

/* ── Day Column ─────────────────────────────────────────────────────── */

function DayColumn({
  dayOffset,
  dayData,
  targets,
}: {
  dayOffset: number;
  dayData: DaySummary;
  targets: MacroSummary | null;
}) {
  const dayName = DAY_SHORT[dayOffset % 7] ?? `Day ${dayOffset + 1}`;
  const meals = dayData.meals ?? {};
  const macros = dayData.member_macros ?? {};
  const firstMemberMacros = Object.values(macros)[0];
  const isEmpty = Object.keys(meals).length === 0;

  return (
    <div
      style={{
        background: colors.surface,
        border: `1px solid ${isEmpty ? colors.border : colors.borderFocus + "40"}`,
        borderRadius: radius.md,
        padding: spacing.md,
        minHeight: "280px",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          fontSize: "0.8rem",
          fontWeight: 700,
          color: colors.text,
          marginBottom: spacing.sm,
          paddingBottom: spacing.sm,
          borderBottom: `1px solid ${colors.border}`,
        }}
      >
        {dayName}
      </div>

      <div style={{ flex: 1, marginBottom: spacing.sm }}>
        {isEmpty ? (
          <div
            style={{
              color: colors.textDim,
              fontSize: "0.8rem",
              textAlign: "center",
              padding: spacing.lg,
            }}
          >
            No meals
          </div>
        ) : (
          MEAL_ORDER.filter((mt) => meals[mt] && meals[mt].length > 0).map((mt) => (
            <MealChip key={mt} mealType={mt} recipes={meals[mt]!} />
          ))
        )}
      </div>

      {targets && firstMemberMacros?.calories != null && (
        <div style={{ marginTop: "auto" }}>
          <MacroVarianceBar
            actual={firstMemberMacros.calories}
            target={targets.calories}
            nutrient="Cal"
            color={colors.calories}
          />
          <MacroVarianceBar
            actual={firstMemberMacros.protein_g}
            target={targets.protein_g}
            nutrient="Protein"
            color={colors.protein}
          />
          <MacroVarianceBar
            actual={firstMemberMacros.carbs_g}
            target={targets.carbs_g}
            nutrient="Carbs"
            color={colors.carbs}
          />
          <MacroVarianceBar
            actual={firstMemberMacros.fat_g}
            target={targets.fat_g}
            nutrient="Fat"
            color={colors.fat}
          />
        </div>
      )}
    </div>
  );
}

/* ── Weekly Summary ─────────────────────────────────────────────────── */

function WeeklySummary({
  weeklyAverages,
  targets,
}: {
  weeklyAverages: Record<string, MacroSummary>;
  targets: MacroSummary | null;
}) {
  const avg = Object.values(weeklyAverages)[0];
  if (!avg) return null;

  return (
    <Card style={{ marginBottom: spacing.lg }}>
      <div
        style={{
          fontSize: "0.8rem",
          fontWeight: 600,
          color: colors.textMuted,
          marginBottom: spacing.sm,
        }}
      >
        Weekly Average
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: spacing.md }}>
        <ProgressBar
          value={avg.calories}
          max={targets?.calories ?? avg.calories}
          color={colors.calories}
          label="Calories"
        />
        <ProgressBar
          value={avg.protein_g}
          max={targets?.protein_g ?? avg.protein_g}
          color={colors.protein}
          label="Protein"
        />
        <ProgressBar
          value={avg.carbs_g}
          max={targets?.carbs_g ?? avg.carbs_g}
          color={colors.carbs}
          label="Carbs"
        />
        <ProgressBar
          value={avg.fat_g}
          max={targets?.fat_g ?? avg.fat_g}
          color={colors.fat}
          label="Fat"
        />
      </div>
    </Card>
  );
}

/* ── Main App ───────────────────────────────────────────────────────── */

function WeeklyCalendarApp() {
  const data = getViewData<WeeklyCalendarData>();
  const planSummary = data.plan_summary ?? {
    plan_id: "",
    plan_name: "Meal Plan",
    start_date: "",
    days: 7,
    detail_level: "full",
    daily_summaries: [],
    weekly_averages: {},
  };
  const targets = data.targets ?? null;

  const [actionStatus, setActionStatus] = useState<string | null>(null);

  useEffect(() => { connectApp("Weekly Calendar"); }, []);

  const days = useMemo(() => {
    const dayMap: Record<number, DaySummary> = {};
    for (const ds of planSummary.daily_summaries) {
      dayMap[ds.day_offset] = ds;
    }
    return Array.from({ length: planSummary.days }, (_, i) =>
      dayMap[i] ?? { day_offset: i, meals: {}, member_macros: {} },
    );
  }, [planSummary]);

  const hasEmptySlots = days.some((d) => Object.keys(d.meals).length === 0);

  return (
    <div className="view-container" style={{ maxWidth: "1200px" }}>
      <div className="view-header">
        <h1>{planSummary.plan_name}</h1>
        <p>{planSummary.days}-day plan overview</p>
      </div>

      <WeeklySummary weeklyAverages={planSummary.weekly_averages} targets={targets} />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${Math.min(planSummary.days, 7)}, 1fr)`,
          gap: spacing.sm,
          marginBottom: spacing.xl,
        }}
      >
        {days.map((day) => (
          <DayColumn key={day.day_offset} dayOffset={day.day_offset} dayData={day} targets={targets} />
        ))}
      </div>

      <div style={{ display: "flex", gap: spacing.md, flexWrap: "wrap" }}>
        {hasEmptySlots && (
          <Button
            onClick={() => {
              callTool("optimize_empty_slots", { plan_id: planSummary.plan_id });
              setActionStatus("optimizing");
            }}
          >
            Optimize Empty Slots
          </Button>
        )}
        <Button
          variant="secondary"
          onClick={() => {
            callTool("rebalance_plan", { plan_id: planSummary.plan_id });
            setActionStatus("rebalancing");
          }}
        >
          Rebalance Plan
        </Button>
        <Button
          variant="ghost"
          onClick={() => {
            callTool("refresh_plan", { plan_id: planSummary.plan_id });
            setActionStatus("refreshing");
          }}
        >
          Refresh
        </Button>
      </div>

      {actionStatus && (
        <div style={{ marginTop: spacing.md, fontSize: "0.85rem", color: colors.primary }}>
          Status: {actionStatus}...
        </div>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <WeeklyCalendarApp />
  </StrictMode>,
);
