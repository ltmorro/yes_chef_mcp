import { useState, useMemo, useEffect } from "react";
import { ActionStatus, Button, Card, FullscreenToggle, RecipeCard, ProgressBar } from "../components";
import type { DisplayModeControl } from "../bridge.ts";
import type { DaySummary, MacroSummary, RecipeHit, WeeklyCalendarData } from "../types.ts";
import { fetchPlans, fetchPlanSummary, fetchMacroTargets, fetchRecipesByIds } from "../api.ts";
import { useAsyncAction } from "../useAsyncAction.ts";
import styles from "./WeeklyCalendarPage.module.css";

const DAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MEAL_ORDER = ["breakfast", "lunch", "dinner", "snack"] as const;

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

/**
 * Plan actions for the shown plan. Each is omitted (and its button hidden)
 * when the host can't perform it.
 */
export interface WeeklyCalendarActions {
  /** Re-fetch the plan and re-render. */
  refresh?: () => Promise<void>;
  /** Ask for proposals to fill the empty slots. */
  optimizeEmptySlots?: () => Promise<void>;
  /** Ask for a rebalance for data.member_id (the button is disabled without one). */
  rebalance?: () => Promise<void>;
}

/**
 * Where the page gets its data and sends its actions. In an MCP host the
 * data is the show_weekly_calendar tool result for one plan; in the SPA it
 * is REST, with a picker over all plans.
 */
export interface WeeklyCalendarSource {
  loading: boolean;
  /** null when not loaded yet, or when there is no plan to show. */
  data: WeeklyCalendarData | null;
  /** SPA only: choose which plan to show. */
  plans?: PlanPicker;
  /** MCP host only: plan actions routed through the host. */
  actions?: WeeklyCalendarActions;
  /** MCP host only, when it offers fullscreen: inline / fullscreen toggle. */
  display?: DisplayModeControl;
}

function planRecipeIds(data: WeeklyCalendarData["plan_summary"]): string[] {
  return [
    ...new Set(
      data.daily_summaries.flatMap((day) =>
        Object.values(day.meals).flatMap((components) => components.map((c) => c.recipe_id)),
      ),
    ),
  ];
}

/** SPA data source backed by the REST API. */
export function useRestWeeklyCalendarSource(memberId?: string): WeeklyCalendarSource {
  const [plans, setPlans] = useState<PlanOption[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [data, setData] = useState<WeeklyCalendarData | null>(null);
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
    // Ignore responses for a plan/member that is no longer selected
    let stale = false;
    setLoading(true);
    fetchPlanSummary(selectedPlanId, memberId)
      .then((plan_summary) => {
        if (stale) return;
        setData({
          plan_id: selectedPlanId,
          member_id: memberId ?? null,
          plan_summary,
          targets: null,
          recipes: [],
        });
        setLoading(false);
        // Recipe hits are non-critical enrichment: cards fall back to name-only without them
        fetchRecipesByIds(planRecipeIds(plan_summary))
          .then((recipes: RecipeHit[]) => {
            if (!stale) setData((prev) => (prev ? { ...prev, recipes } : prev));
          })
          .catch(() => { /* keep fallback cards */ });
      })
      .catch(() => {
        if (stale) return;
        setData(null);
        setLoading(false);
      });
    return () => {
      stale = true;
    };
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

  const merged = useMemo(() => (data ? { ...data, targets } : null), [data, targets]);

  return {
    loading,
    data: merged,
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

/* ── Day Row ──────────────────────────────────────────────────────────── */

function DayRow({
  dayOffset,
  dayData,
  targets,
  recipeIndex,
}: {
  dayOffset: number;
  dayData: DaySummary;
  targets: MacroSummary | null;
  recipeIndex: Map<string, RecipeHit>;
}) {
  const dayName = DAY_SHORT[dayOffset % 7] ?? `Day ${dayOffset + 1}`;
  const meals = dayData.meals ?? {};
  const macros = dayData.member_macros ?? {};
  const firstMemberMacros = Object.values(macros)[0];
  const isEmpty = Object.keys(meals).length === 0;

  const recipeItems = MEAL_ORDER.flatMap((mt) =>
    (meals[mt] ?? []).map((r) => ({ mealType: mt, component: r })),
  );

  return (
    <Card
      pretitle={dayName}
      className={!isEmpty ? styles.dayRowFilled : undefined}
      title={
        <div className={styles.dayRowBody}>
          <div className={styles.dayRecipes}>
            {isEmpty ? (
              <div className={styles.dayEmpty}>No meals</div>
            ) : (
              recipeItems.map((item, i) => {
                const hit = recipeIndex.get(item.component.recipe_id);
                if (hit) {
                  return <RecipeCard key={i} {...hit} />;
                }
                // Fallback for recipes not yet in the index
                return (
                  <Card
                    key={i}
                    pretitle={item.mealType}
                    title={item.component.recipe_name ?? item.component.recipe_id}
                  />
                );
              })
            )}
          </div>
          {targets && firstMemberMacros?.calories != null && (
            <div className={styles.dayVariance}>
              <MacroVarianceBar actual={firstMemberMacros.calories} target={targets.calories} nutrient="Cal" macro="calories" />
              <MacroVarianceBar actual={firstMemberMacros.protein_g} target={targets.protein_g} nutrient="Protein" macro="protein" />
              <MacroVarianceBar actual={firstMemberMacros.carbs_g} target={targets.carbs_g} nutrient="Carbs" macro="carbs" />
              <MacroVarianceBar actual={firstMemberMacros.fat_g} target={targets.fat_g} nutrient="Fat" macro="fat" />
            </div>
          )}
        </div>
      }
    />
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
    <Card
      pretitle="Macro Totals"
      title={
        <div className={styles.summaryGrid}>
          <ProgressBar value={avg.calories} max={targets?.calories ?? avg.calories} macro="calories" label="Calories" />
          <ProgressBar value={avg.protein_g} max={targets?.protein_g ?? avg.protein_g} macro="protein" label="Protein" />
          <ProgressBar value={avg.carbs_g} max={targets?.carbs_g ?? avg.carbs_g} macro="carbs" label="Carbs" />
          <ProgressBar value={avg.fat_g} max={targets?.fat_g ?? avg.fat_g} macro="fat" label="Fat" />
        </div>
      }
      className={styles.summaryCard}
    />
  );
}

/* ── Page Component ──────────────────────────────────────────────────── */

interface WeeklyCalendarPageProps {
  source: WeeklyCalendarSource;
}

export function WeeklyCalendarPage({ source }: WeeklyCalendarPageProps) {
  const { loading, data, plans, actions, display } = source;
  const planSummary = data?.plan_summary ?? null;
  const targets = data?.targets ?? null;
  const [actionState, runAction] = useAsyncAction();

  const recipeIndex = useMemo(
    () => new Map((data?.recipes ?? []).map((r) => [r.id, r])),
    [data],
  );

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

  const hasEmptySlots = days.some((d) => Object.keys(d.meals).length === 0);

  const busy = actionState.kind === "pending";
  const hasMember = Boolean(data?.member_id);

  const trigger = (run: (() => Promise<void>) | undefined, pending: string, done: string) => {
    if (!run) return;
    runAction(pending, async () => {
      await run();
      return done;
    });
  };

  if (loading && !planSummary) {
    return (
      <div>
        <div className={styles.loading}>Loading meal plans...</div>
      </div>
    );
  }

  if (!planSummary && (!plans || plans.options.length === 0)) {
    return (
      <div>
        <div className="view-header">
          <h1>Weekly Calendar</h1>
          <p>No meal plans found. Create one to get started.</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className={styles.headerRow}>
        <div className="view-header">
          <h1>{planSummary?.plan_name ?? "Weekly Calendar"}</h1>
          <p>{planSummary ? `${planSummary.days}-day plan overview` : "Select a plan"}</p>
        </div>
        {display && <FullscreenToggle display={display} />}
      </div>

      {plans && (
        <PlanSelector plans={plans.options} selectedId={plans.selectedId} onSelect={plans.onSelect} />
      )}

      {planSummary && (
        <>
          <WeeklySummary weeklyAverages={planSummary.weekly_averages} targets={targets} />

          <div className={styles.dayList}>
            {days.map((day) => (
              <DayRow key={day.day_offset} dayOffset={day.day_offset} dayData={day} targets={targets} recipeIndex={recipeIndex} />
            ))}
          </div>
        </>
      )}

      {actions && planSummary && (
        <>
          <div className={styles.actions}>
            {hasEmptySlots && actions.optimizeEmptySlots && (
              <Button
                isDisabled={busy}
                onPress={() =>
                  trigger(actions.optimizeEmptySlots, "Sending…", "Asked for proposals to fill the empty slots.")
                }
              >
                Optimize Empty Slots
              </Button>
            )}
            {actions.rebalance && (
              <Button
                variant="secondary"
                isDisabled={busy || !hasMember}
                onPress={() => trigger(actions.rebalance, "Sending…", "Asked for a rebalanced plan.")}
              >
                Rebalance Plan
              </Button>
            )}
            {actions.refresh && (
              <Button
                variant="ghost"
                isDisabled={busy}
                onPress={() => trigger(actions.refresh, "Refreshing…", "Plan refreshed.")}
              >
                Refresh
              </Button>
            )}
          </div>
          {actions.rebalance && !hasMember && (
            <div className={styles.hint}>Rebalancing needs a family member to balance for.</div>
          )}
          <ActionStatus state={actionState} />
        </>
      )}
    </div>
  );
}
