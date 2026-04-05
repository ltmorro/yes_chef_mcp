import { useState, useEffect, useCallback } from "react";
import { Button, Card, CaloriePanel, SliderPanel } from "../components";
import type { MacroKey, MacroConfig } from "../components";
import { fetchMacroTargets, saveMacroTarget } from "../api.ts";
import styles from "./MacroSetterPage.module.css";

/* ── Macro definitions ───────────────────────────────────────────────── */

function buildMacros(protein: number, carbs: number, fat: number): MacroConfig[] {
  return [
    { key: "protein", label: "Protein", grams: protein, min: 50, max: 350, step: 5, calPerGram: 4 },
    { key: "carbs", label: "Carbs", grams: carbs, min: 50, max: 500, step: 5, calPerGram: 4 },
    { key: "fat", label: "Fat", grams: fat, min: 20, max: 200, step: 5, calPerGram: 9 },
  ];
}

/* ── Page Component ──────────────────────────��───────────────────────── */

interface MacroSetterPageProps {
  memberId?: string;
}

export function MacroSetterPage({ memberId }: MacroSetterPageProps) {
  const [protein, setProtein] = useState(150);
  const [carbs, setCarbs] = useState(200);
  const [fat, setFat] = useState(65);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [defaults, setDefaults] = useState<{ protein_g: number; carbs_g: number; fat_g: number } | null>(null);

  const totalCalories = Math.round(protein * 4 + carbs * 4 + fat * 9);

  useEffect(() => {
    if (!memberId) {
      setLoading(false);
      return;
    }
    fetchMacroTargets(memberId)
      .then((targets) => {
        const active = targets.find((t) => t.is_active);
        if (active) {
          setProtein(active.protein_g);
          setCarbs(active.carbs_g);
          setFat(active.fat_g);
          setDefaults({ protein_g: active.protein_g, carbs_g: active.carbs_g, fat_g: active.fat_g });
        }
      })
      .catch(() => { /* API unavailable — use defaults */ })
      .finally(() => setLoading(false));
  }, [memberId]);

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
    if (memberId) {
      saveMacroTarget(memberId, {
        calories: totalCalories,
        protein_g: protein,
        carbs_g: carbs,
        fat_g: fat,
      }).catch(() => { /* handle error */ });
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }, [memberId, protein, carbs, fat, totalCalories]);

  const handleReset = () => {
    setProtein(defaults?.protein_g ?? 150);
    setCarbs(defaults?.carbs_g ?? 200);
    setFat(defaults?.fat_g ?? 65);
  };

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>Loading targets...</div>
      </div>
    );
  }

  const macros = buildMacros(protein, carbs, fat);

  return (
    <div className={styles.container}>
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
