import { StrictMode, useState, useEffect, useRef, useCallback } from "react";
import { createRoot } from "react-dom/client";
import { Slider, SliderTrack, SliderThumb, SliderOutput, Label } from "react-aria-components";
import { connectApp, callTool, getViewData, extractText } from "../bridge";
import { Button, Card } from "../components";
import { tokens } from "../theme";
import type { MacroSetterData } from "../types";
import "../global.css";
import styles from "./macro-setter.module.css";

/* ── Pie Chart (Canvas — JS tokens required) ─────────────────────────── */

function MacroPieChart({
  protein,
  carbs,
  fat,
}: {
  protein: number;
  carbs: number;
  fat: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const totalCal = protein * 4 + carbs * 4 + fat * 9;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const size = canvas.width;
    const cx = size / 2;
    const cy = size / 2;
    const r = size / 2 - 16;

    ctx.clearRect(0, 0, size, size);

    if (totalCal === 0) {
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.strokeStyle = tokens.color.border;
      ctx.lineWidth = 24;
      ctx.stroke();
      return;
    }

    const slices = [
      { value: protein * 4, color: tokens.color.protein },
      { value: carbs * 4, color: tokens.color.carbs },
      { value: fat * 9, color: tokens.color.fat },
    ];

    let startAngle = -Math.PI / 2;
    for (const slice of slices) {
      const angle = (slice.value / totalCal) * Math.PI * 2;
      ctx.beginPath();
      ctx.arc(cx, cy, r, startAngle, startAngle + angle);
      ctx.strokeStyle = slice.color;
      ctx.lineWidth = 24;
      ctx.lineCap = "butt";
      ctx.stroke();
      startAngle += angle;
    }

    ctx.fillStyle = tokens.color.text;
    ctx.font = `700 28px ${tokens.font.brand}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(Math.round(totalCal)), cx, cy - 8);

    ctx.fillStyle = tokens.color.textMuted;
    ctx.font = `500 12px ${tokens.font.brand}`;
    ctx.fillText("calories", cx, cy + 16);
  }, [protein, carbs, fat, totalCal]);

  return (
    <canvas
      ref={canvasRef}
      width={200}
      height={200}
      className={styles.pieCanvas}
    />
  );
}

/* ── Macro Slider (RAC) ──────────────────────────────────────────────── */

function MacroSlider({
  label,
  value,
  min,
  max,
  step,
  macro,
  unit,
  calPer,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  macro: "protein" | "carbs" | "fat";
  unit: string;
  calPer: number;
  onChange: (v: number) => void;
}) {
  const calContribution = Math.round(value * calPer);
  const colorVar = `var(--color-${macro})`;

  return (
    <Slider
      className={styles.slider}
      minValue={min}
      maxValue={max}
      step={step}
      value={value}
      onChange={onChange}
    >
      <div className={styles.sliderHeader}>
        <Label className={styles.sliderLabel}>{label}</Label>
        <div className={styles.sliderValues}>
          <SliderOutput
            className={styles.sliderAmount}
            {...{ style: { color: colorVar } as React.CSSProperties }}
          />
          <span className={styles.sliderUnit}>{unit}</span>
          <span className={styles.sliderCals}>({calContribution} cal)</span>
        </div>
      </div>
      <SliderTrack
        className={styles.rangeInput}
        {...{ style: { accentColor: colorVar } as React.CSSProperties }}
      >
        <SliderThumb />
      </SliderTrack>
    </Slider>
  );
}

/* ── Legend Dot ────────────────────────────────────────────────────────── */

function LegendDot({ macro, label }: { macro: "protein" | "carbs" | "fat"; label: string }) {
  const dotClass = macro === "protein" ? styles.dotProtein
    : macro === "carbs" ? styles.dotCarbs
    : styles.dotFat;

  return (
    <div className={styles.legendDot}>
      <div className={`${styles.dot} ${dotClass}`} />
      {label}
    </div>
  );
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

  return (
    <div className="view-container">
      <div className="view-header">
        <h1>Macro Targets</h1>
        <p>Adjust your daily macro goals and see calorie impact in real time.</p>
      </div>

      <div className={styles.grid}>
        <Card>
          <MacroSlider
            label="Protein"
            value={protein}
            min={50}
            max={350}
            step={5}
            macro="protein"
            unit="g"
            calPer={4}
            onChange={setProtein}
          />
          <MacroSlider
            label="Carbohydrates"
            value={carbs}
            min={50}
            max={500}
            step={5}
            macro="carbs"
            unit="g"
            calPer={4}
            onChange={setCarbs}
          />
          <MacroSlider
            label="Fat"
            value={fat}
            min={20}
            max={200}
            step={5}
            macro="fat"
            unit="g"
            calPer={9}
            onChange={setFat}
          />
        </Card>

        <Card className={styles.pieCard}>
          <MacroPieChart protein={protein} carbs={carbs} fat={fat} />
          <div className={styles.legend}>
            <LegendDot macro="protein" label="Protein" />
            <LegendDot macro="carbs" label="Carbs" />
            <LegendDot macro="fat" label="Fat" />
          </div>
        </Card>
      </div>

      <div className={styles.actions}>
        <Button variant="secondary" onPress={handleReset}>
          Reset
        </Button>
        <Button
          onPress={handleSave}
          className={saved ? styles.saved : undefined}
        >
          {saved ? "Saved!" : "Save Targets"}
        </Button>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MacroSetterApp />
  </StrictMode>,
);
