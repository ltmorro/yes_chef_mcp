import { useState, useEffect, useCallback } from "react";
import { Button, Card, CaloriePanel, SliderPanel } from "../components";
import type { MacroKey, MacroConfig } from "../components";
import type { MacroSetterData } from "../types.ts";
import { fetchMacroTargets, saveMacroTarget } from "../api.ts";
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
  save: (values: MacroValues) => void;
}

/** SPA data source backed by the REST API. */
export function useRestMacroSetterSource(memberId?: string): MacroSetterSource {
  const [data, setData] = useState<MacroSetterData | null>(null);

  useEffect(() => {
    if (!memberId) {
      setData({ current_targets: null });
      return;
    }
    fetchMacroTargets(memberId)
      .then((targets) => {
        const active = targets.find((t) => t.is_active);
        setData({ current_targets: active ?? null });
      })
      .catch(() => setData({ current_targets: null })); // API unavailable — use defaults
  }, [memberId]);

  const save = useCallback(
    (values: MacroValues) => {
      if (!memberId) return;
      saveMacroTarget(memberId, values).catch(() => { /* handle error */ });
    },
    [memberId],
  );

  return { data, save };
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
  const [saved, setSaved] = useState(false);

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
    save({ calories: totalCalories, protein_g: protein, carbs_g: carbs, fat_g: fat });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }, [save, protein, carbs, fat, totalCalories]);

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

  return (
    <div>
      <div className="view-header">
        <h1>Macro Targets</h1>
        <p>Adjust your daily macro goals and see calorie impact in real time.</p>
      </div>

      <Card
        pretitle="Daily Target"
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
            <Button
              onPress={handleSave}
              className={saved ? styles.saved : undefined}
            >
              {saved ? "Saved!" : "Save Targets"}
            </Button>
          </>
        }
      />
    </div>
  );
}
