import { StrictMode, useState, useEffect, useCallback } from "react";
import { createRoot } from "react-dom/client";
import { connectApp, callTool, getViewData, extractText } from "../bridge.ts";
import { Button, Card, CaloriePanel, SliderPanel } from "../components";
import type { MacroKey, MacroConfig } from "../components";
import type { MacroSetterData } from "../types.ts";
import "../global.css";
import styles from "./macro-setter.module.css";

/* ── Macro definitions ───────────────────────────────────────────────── */

function buildMacros(protein: number, carbs: number, fat: number): MacroConfig[] {
  return [
    { key: "protein", label: "Protein", grams: protein, min: 50, max: 350, step: 5, calPerGram: 4 },
    { key: "carbs", label: "Carbs", grams: carbs, min: 50, max: 500, step: 5, calPerGram: 4 },
    { key: "fat", label: "Fat", grams: fat, min: 20, max: 200, step: 5, calPerGram: 9 },
  ];
}

/* ── Main App ─────────────────────────────────────────────────────────── */

function MacroSetterApp() {
  const data = getViewData<MacroSetterData>();
  const defaults = data.current_targets;

  const [protein, setProtein] = useState(defaults?.protein_g ?? 150);
  const [carbs, setCarbs] = useState(defaults?.carbs_g ?? 200);
  const [fat, setFat] = useState(defaults?.fat_g ?? 65);
  const [saved, setSaved] = useState(false);

  const totalCalories = Math.round(protein * 4 + carbs * 4 + fat * 9);

  useEffect(() => {
    const app = connectApp("Macro Setter");
    app.then((a) => {
      if (!a) return;
      a.ontoolresult = ({ content }) => {
        const text = extractText({ content });
        if (!text) return;
        try {
          const parsed = JSON.parse(text) as MacroSetterData;
          if (parsed.current_targets) {
            setProtein(parsed.current_targets.protein_g);
            setCarbs(parsed.current_targets.carbs_g);
            setFat(parsed.current_targets.fat_g);
          }
        } catch { /* non-JSON result, ignore */ }
      };
    });
  }, []);

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
    callTool("save_macro_targets", {
      protein_g: protein,
      carbs_g: carbs,
      fat_g: fat,
      calories: totalCalories,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }, [protein, carbs, fat, totalCalories]);

  const handleReset = () => {
    setProtein(defaults?.protein_g ?? 150);
    setCarbs(defaults?.carbs_g ?? 200);
    setFat(defaults?.fat_g ?? 65);
  };

  const macros = buildMacros(protein, carbs, fat);

  return (
    <div>
      <Card
        pretitle="Daily Target"
        title="Macro Targets"
        subtitle="Adjust your daily macro goals and see calorie impact in real time."
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

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MacroSetterApp />
  </StrictMode>,
);
