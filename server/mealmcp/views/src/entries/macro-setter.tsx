import { StrictMode, useState, useEffect, useRef, useCallback } from "react";
import { createRoot } from "react-dom/client";
import { connectApp, callTool, getViewData, extractText } from "../bridge";
import { Button, Card } from "../components";
import { colors, spacing, font } from "../theme";
import type { MacroSetterData } from "../types";
import "../global.css";

/* ── Pie Chart (Canvas) ─────────────────────────────────────────────── */

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
    const r = size / 2 - 12;

    ctx.clearRect(0, 0, size, size);

    if (totalCal === 0) {
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.strokeStyle = colors.border;
      ctx.lineWidth = 24;
      ctx.stroke();
      return;
    }

    const slices = [
      { value: protein * 4, color: colors.protein },
      { value: carbs * 4, color: colors.carbs },
      { value: fat * 9, color: colors.fat },
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

    ctx.fillStyle = colors.text;
    ctx.font = `700 28px ${font.sans}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(Math.round(totalCal)), cx, cy - 8);

    ctx.fillStyle = colors.textMuted;
    ctx.font = `500 12px ${font.sans}`;
    ctx.fillText("calories", cx, cy + 16);
  }, [protein, carbs, fat, totalCal]);

  return (
    <canvas
      ref={canvasRef}
      width={200}
      height={200}
      style={{ display: "block", margin: "0 auto" }}
    />
  );
}

/* ── Macro Slider ───────────────────────────────────────────────────── */

function MacroSlider({
  label,
  value,
  min,
  max,
  step,
  color,
  unit,
  calPer,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  color: string;
  unit: string;
  calPer: number;
  onChange: (v: number) => void;
}) {
  const calContribution = Math.round(value * calPer);

  return (
    <div style={{ marginBottom: spacing.lg }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: spacing.sm,
        }}
      >
        <label style={{ fontSize: "0.875rem", fontWeight: 600, color: colors.text }}>
          {label}
        </label>
        <div style={{ display: "flex", alignItems: "baseline", gap: spacing.sm }}>
          <span
            style={{ fontSize: "1.25rem", fontWeight: 700, color, fontFamily: font.mono }}
          >
            {value}
          </span>
          <span style={{ fontSize: "0.75rem", color: colors.textMuted }}>{unit}</span>
          <span
            style={{ fontSize: "0.75rem", color: colors.textDim, marginLeft: spacing.xs }}
          >
            ({calContribution} cal)
          </span>
        </div>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ width: "100%", accentColor: color, height: "6px", cursor: "pointer" }}
      />
    </div>
  );
}

/* ── Legend Dot ──────────────────────────────────────────────────────── */

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
      <div style={{ width: 8, height: 8, borderRadius: "50%", background: color }} />
      {label}
    </div>
  );
}

/* ── Main App ───────────────────────────────────────────────────────── */

function MacroSetterApp() {
  const data = getViewData<MacroSetterData>();
  const defaults = data.current_targets;

  const [protein, setProtein] = useState(defaults?.protein_g ?? 150);
  const [carbs, setCarbs] = useState(defaults?.carbs_g ?? 200);
  const [fat, setFat] = useState(defaults?.fat_g ?? 65);
  const [saved, setSaved] = useState(false);

  const totalCalories = Math.round(protein * 4 + carbs * 4 + fat * 9);

  // Connect to MCP host on mount (no-op in standalone mode)
  useEffect(() => {
    const app = connectApp("Macro Setter");
    app.then((a) => {
      if (!a) return;
      // Receive refreshed targets pushed by the host
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

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 240px",
          gap: spacing.xl,
          alignItems: "start",
        }}
      >
        <Card>
          <MacroSlider
            label="Protein"
            value={protein}
            min={50}
            max={350}
            step={5}
            color={colors.protein}
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
            color={colors.carbs}
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
            color={colors.fat}
            unit="g"
            calPer={9}
            onChange={setFat}
          />
        </Card>

        <Card
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: spacing.md,
          }}
        >
          <MacroPieChart protein={protein} carbs={carbs} fat={fat} />
          <div style={{ display: "flex", gap: spacing.md, fontSize: "0.75rem" }}>
            <LegendDot color={colors.protein} label="Protein" />
            <LegendDot color={colors.carbs} label="Carbs" />
            <LegendDot color={colors.fat} label="Fat" />
          </div>
        </Card>
      </div>

      <div
        style={{
          marginTop: spacing.xl,
          display: "flex",
          justifyContent: "flex-end",
          gap: spacing.md,
        }}
      >
        <Button variant="secondary" onClick={handleReset}>
          Reset
        </Button>
        <Button
          onClick={handleSave}
          style={saved ? { background: colors.success } : undefined}
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
