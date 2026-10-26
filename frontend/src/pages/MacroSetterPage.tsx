import { useState, useEffect, useCallback } from "react";
import { ActionStatus, Button, Card, CaloriePanel, SliderPanel } from "../components";
import type { MacroKey, MacroConfig } from "../components";
import type { MacroSetterData, MacroTarget } from "../types.ts";
import { fetchMacroTargets, saveMacroTarget } from "../api.ts";
import { useAsyncAction } from "../useAsyncAction.ts";
import styles from "./MacroSetterPage.module.css";

/* ── Data source ─────────────────────────────────────────────────────── */

export interface MacroValues {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

/**
 * Where the page gets its data and sends its actions. In an MCP host the
 * data is the show_macro_target_setter tool result; in the SPA it is REST.
 */
export interface MacroSetterSource {
  /** null while loading. */
  data: MacroSetterData | null;
  /**
   * Save the values as the member's new active target and resolve to the
   * saved target. Omitted when saving isn't possible (no member selected in
   * the SPA, or a host that can't call server tools).
   */
  save?: (values: MacroValues) => Promise<MacroTarget>;
}

const DEFAULT_TARGET_NAME = "Custom";

/** SPA data source backed by the REST API. */
export function useRestMacroSetterSource(memberId?: string): MacroSetterSource {
  const [data, setData] = useState<MacroSetterData | null>(null);

  useEffect(() => {
    const empty: MacroSetterData = {
      member_id: memberId ?? "",
      member_name: "",
      target_name: DEFAULT_TARGET_NAME,
      current_targets: null,
    };
    if (!memberId) {
      setData(empty);
      return;
    }
    fetchMacroTargets(memberId)
      .then((targets) => {
        const active = targets.find((t) => t.is_active);
        setData(
          active
            ? { ...empty, target_name: active.name, current_targets: active }
            : empty,
        );
      })
      .catch(() => setData(empty)); // API unavailable — use defaults
  }, [memberId]);

  const targetName = data?.target_name ?? DEFAULT_TARGET_NAME;
  const save = useCallback(
    (values: MacroValues) => {
      if (!memberId) return Promise.reject(new Error("No member selected."));
      return saveMacroTarget(memberId, { name: targetName, ...values });
    },
    [memberId, targetName],
  );

  return { data, save: memberId ? save : undefined };
}

/* ── Macro definitions ───────────────────────────────────────────────── */

const DEFAULTS = { protein_g: 150, carbs_g: 200, fat_g: 65 };

function buildMacros(protein: number, carbs: number, fat: number): MacroConfig[] {
  return [
    { key: "protein", label: "Protein", grams: protein, min: 50, max: 350, step: 5, calPerGram: 4 },
    { key: "carbs", label: "Carbs", grams: carbs, min: 50, max: 500, step: 5, calPerGram: 4 },
    { key: "fat", label: "Fat", grams: fat, min: 20, max: 200, step: 5, calPerGram: 9 },
  ];
}

function describeTarget(target: MacroTarget): string {
  return (
    `Saved "${target.name}" as the active target: ${Math.round(target.calories)} kcal, ` +
    `${Math.round(target.protein_g)}g protein, ${Math.round(target.carbs_g)}g carbs, ` +
    `${Math.round(target.fat_g)}g fat`
  );
}

/* ── Page Component ──────────────────────────────────────────────────── */

interface MacroSetterPageProps {
  source: MacroSetterSource;
}

export function MacroSetterPage({ source }: MacroSetterPageProps) {
  const { data, save } = source;
  const defaults = data?.current_targets ?? DEFAULTS;

  const [protein, setProtein] = useState(defaults.protein_g);
  const [carbs, setCarbs] = useState(defaults.carbs_g);
  const [fat, setFat] = useState(defaults.fat_g);
  const [saveState, runSave] = useAsyncAction();

  // Re-seed the sliders whenever new data arrives (REST load or a new tool result)
  useEffect(() => {
    const next = data?.current_targets ?? DEFAULTS;
    setProtein(next.protein_g);
    setCarbs(next.carbs_g);
    setFat(next.fat_g);
  }, [data]);

  const totalCalories = Math.round(protein * 4 + carbs * 4 + fat * 9);

  const handleMacroChange = useCallback((key: MacroKey, grams: number) => {
    if (key === "protein") setProtein(grams);
    else if (key === "carbs") setCarbs(grams);
    else setFat(grams);
  }, []);

  const handleCalorieChange = useCallback((newCal: number) => {
    if (totalCalories === 0) return;
    const scale = newCal / totalCalories;
    const clampSnap = (v: number, min: number, max: number, step: number) =>
      Math.min(max, Math.max(min, Math.round(v / step) * step));
    setProtein((p) => clampSnap(p * scale, 50, 350, 5));
    setCarbs((c) => clampSnap(c * scale, 50, 500, 5));
    setFat((f) => clampSnap(f * scale, 20, 200, 5));
  }, [totalCalories]);

  const handleSave = useCallback(() => {
    if (!save) return;
    const values = { calories: totalCalories, protein_g: protein, carbs_g: carbs, fat_g: fat };
    runSave("Saving…", async () => describeTarget(await save(values)));
  }, [save, runSave, protein, carbs, fat, totalCalories]);

  const handleReset = () => {
    setProtein(defaults.protein_g);
    setCarbs(defaults.carbs_g);
    setFat(defaults.fat_g);
  };

  if (!data) {
    return (
      <div>
        <div className={styles.loading}>Loading targets...</div>
      </div>
    );
  }

  const macros = buildMacros(protein, carbs, fat);
  const heading = data.member_name ? `Daily Target · ${data.member_name}` : "Daily Target";

  return (
    <div>
      <div className="view-header">
        <h1>Macro Targets</h1>
        <p>Adjust your daily macro goals and see calorie impact in real time.</p>
      </div>

      <Card
        pretitle={heading}
        title="Macro Targets"
        subtitle="Drag the sliders or edit the calorie total directly."
        leadingMedia={
          <CaloriePanel
            macros={macros}
            totalCalories={totalCalories}
            onCalorieChange={handleCalorieChange}
          />
        }
        body={<SliderPanel macros={macros} onMacroChange={handleMacroChange} />}
        footer={
          <>
            <Button variant="secondary" onPress={handleReset}>
              Reset
            </Button>
            <Button onPress={handleSave} isDisabled={!save || saveState.kind === "pending"}>
              Save Targets
            </Button>
          </>
        }
      />
      <ActionStatus state={saveState} />
    </div>
  );
}
