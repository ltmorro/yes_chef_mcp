import { useState, useMemo, useEffect } from "react";
import { Button, Card, ProgressBar } from "../components";
import type { DaySummary, MacroSummary, MealComponent, PlanSummary } from "../types.ts";
import { fetchPlans, fetchPlanSummary, fetchMacroTargets } from "../api.ts";
import styles from "./WeeklyCalendarPage.module.css";

const DAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MEAL_ORDER = ["breakfast", "lunch", "dinner", "snack"] as const;

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

/* ── Macro Variance Bar ───────────────────────────────────────────────── */

function MacroVarianceBar({
  actual,
  target,
  nutrient,
  macro,
}: {
  actual: number;
  target: number;
  nutrient: string;
  macro: "protein" | "carbs" | "fat" | "calories";
}) {
  if (target === 0) return null;
  const pct = (actual / target) * 100;
  const isOver = pct > 105;
  const isUnder = pct < 85;

  const fillColor = isOver
    ? "var(--color-danger)"
    : isUnder
      ? "var(--color-warning)"
      : `var(--color-${macro})`;

  return (
    <div className={styles.varianceBar}>
      <div className={styles.varianceHeader}>
        <span>{nutrient}</span>
        <span
          className={styles.varianceValue}
          {...{ style: { color: fillColor } as React.CSSProperties }}
        >
          {Math.round(actual)}/{Math.round(target)}
        </span>
      </div>
      <div className={styles.varianceTrack}>
        <div
          className={styles.varianceFill}
          {...{
            style: {
              "--progress-pct": `${Math.min(pct, 100)}%`,
              background: fillColor,
            } as React.CSSProperties,
          }}
        />
      </div>
    </div>
  );
}

/* ── Meal Chip ────────────────────────────────────────────────────────── */

const CHIP_CLASS: Record<string, string> = {
  breakfast: styles.mealChipBreakfast ?? "",
  lunch: styles.mealChipLunch ?? "",
  dinner: styles.mealChipDinner ?? "",
  snack: styles.mealChipSnack ?? "",
};

const TYPE_CLASS: Record<string, string> = {
  breakfast: styles.mealTypeBreakfast ?? "",
  lunch: styles.mealTypeLunch ?? "",
  dinner: styles.mealTypeDinner ?? "",
  snack: styles.mealTypeSnack ?? "",
};

function MealChip({ mealType, recipes }: { mealType: string; recipes: MealComponent[] }) {
  return (
    <div className={`${styles.mealChip} ${CHIP_CLASS[mealType] ?? ""}`}>
      <div className={`${styles.mealType} ${TYPE_CLASS[mealType] ?? ""}`}>
        {mealType}
      </div>
      {recipes.map((r, i) => (
        <div key={i} className={styles.mealRecipe}>
          {r.recipe_name ?? r.recipe_id}
        </div>
      ))}
    </div>
  );
}

/* ── Day Column ───────────────────────────────────────────────────────── */

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

  const columnClasses = [
    styles.dayColumn,
    !isEmpty ? styles.dayColumnFilled : "",
  ].filter(Boolean).join(" ");

  return (
    <div className={columnClasses}>
      <div className={styles.dayName}>{dayName}</div>

      <div className={styles.dayMeals}>
        {isEmpty ? (
          <div className={styles.dayEmpty}>No meals</div>
        ) : (
          MEAL_ORDER.filter((mt) => meals[mt] && meals[mt].length > 0).map((mt) => (
            <MealChip key={mt} mealType={mt} recipes={meals[mt]!} />
          ))
        )}
      </div>

      {targets && firstMemberMacros?.calories != null && (
        <div>
          <MacroVarianceBar actual={firstMemberMacros.calories} target={targets.calories} nutrient="Cal" macro="calories" />
          <MacroVarianceBar actual={firstMemberMacros.protein_g} target={targets.protein_g} nutrient="Protein" macro="protein" />
          <MacroVarianceBar actual={firstMemberMacros.carbs_g} target={targets.carbs_g} nutrient="Carbs" macro="carbs" />
          <MacroVarianceBar actual={firstMemberMacros.fat_g} target={targets.fat_g} nutrient="Fat" macro="fat" />
        </div>
      )}
    </div>
  );
}

/* ── Weekly Summary ───────────────────────────────────────────────────── */

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
    <Card className={styles.summaryCard}>
      <div className={styles.summaryLabel}>Weekly Average</div>
      <div className={styles.summaryGrid}>
        <ProgressBar value={avg.calories} max={targets?.calories ?? avg.calories} macro="calories" label="Calories" />
        <ProgressBar value={avg.protein_g} max={targets?.protein_g ?? avg.protein_g} macro="protein" label="Protein" />
        <ProgressBar value={avg.carbs_g} max={targets?.carbs_g ?? avg.carbs_g} macro="carbs" label="Carbs" />
        <ProgressBar value={avg.fat_g} max={targets?.fat_g ?? avg.fat_g} macro="fat" label="Fat" />
      </div>
    </Card>
  );
}

/* ── Page Component ──────────────────────────────────────────────────── */

interface WeeklyCalendarPageProps {
  memberId?: string;
}

export function WeeklyCalendarPage({ memberId }: WeeklyCalendarPageProps) {
  const [plans, setPlans] = useState<PlanOption[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [planSummary, setPlanSummary] = useState<PlanSummary | null>(null);
  const [targets, setTargets] = useState<MacroSummary | null>(null);
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
    fetchPlanSummary(selectedPlanId, memberId)
      .then(setPlanSummary)
      .catch(() => setPlanSummary(null))
      .finally(() => setLoading(false));
  }, [selectedPlanId, memberId]);

  useEffect(() => {
    if (!memberId) return;
    fetchMacroTargets(memberId)
      .then((tgts) => {
        const active = tgts.find((t) => t.is_active);
        if (active) {
          setTargets({
            calories: active.calories,
            protein_g: active.protein_g,
            carbs_g: active.carbs_g,
            fat_g: active.fat_g,
          });
        }
      })
      .catch(() => { /* ignore */ });
  }, [memberId]);

  const days = useMemo(() => {
    if (!planSummary) return [];
    const dayMap: Record<number, DaySummary> = {};
    for (const ds of planSummary.daily_summaries) {
      dayMap[ds.day_offset] = ds;
    }
    return Array.from({ length: planSummary.days }, (_, i) =>
      dayMap[i] ?? { day_offset: i, meals: {}, member_macros: {} },
    );
  }, [planSummary]);

  if (loading && !planSummary) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>Loading meal plans...</div>
      </div>
    );
  }

  if (plans.length === 0) {
    return (
      <div className={styles.container}>
        <div className="view-header">
          <h1>Weekly Calendar</h1>
          <p>No meal plans found. Create one to get started.</p>
        </div>
      </div>
    );
  }

  const gridStyle = planSummary
    ? { gridTemplateColumns: `repeat(${Math.min(planSummary.days, 7)}, 1fr)` } as React.CSSProperties
    : undefined;

  return (
    <div className={styles.container}>
      <div className="view-header">
        <h1>{planSummary?.plan_name ?? "Weekly Calendar"}</h1>
        <p>{planSummary ? `${planSummary.days}-day plan overview` : "Select a plan"}</p>
      </div>

      <PlanSelector plans={plans} selectedId={selectedPlanId} onSelect={setSelectedPlanId} />

      {planSummary && (
        <>
          <WeeklySummary weeklyAverages={planSummary.weekly_averages} targets={targets} />

          <div className={styles.dayGrid} {...(gridStyle ? { style: gridStyle } : {})}>
            {days.map((day) => (
              <DayColumn key={day.day_offset} dayOffset={day.day_offset} dayData={day} targets={targets} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
