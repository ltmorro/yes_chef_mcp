import { Slider, SliderTrack, SliderThumb, SliderOutput, Label, NumberField, Input } from "react-aria-components";
import styles from "./MacroTargetEditor.module.css";

/* ── Types ────────────────────────────────────────────────────────────── */

type MacroKey = "protein" | "carbs" | "fat";

interface MacroConfig {
  key: MacroKey;
  label: string;
  grams: number;
  min: number;
  max: number;
  step: number;
  calPerGram: number;
}

interface MacroTargetEditorProps {
  macros: MacroConfig[];
  onMacroChange: (key: MacroKey, grams: number) => void;
  onCalorieChange: (calories: number) => void;
}

export type { MacroKey, MacroConfig, MacroTargetEditorProps };

/* ── Calorie Panel (left column) ─────────────────────────────────────── */

function CaloriePanel({ macros, totalCalories, onCalorieChange }: {
  macros: MacroConfig[];
  totalCalories: number;
  onCalorieChange: (calories: number) => void;
}) {
  return (
    <div className={styles.caloriePanel}>
      <div className={styles.calorieHeader}>
        <NumberField
          className={styles.calorieField}
          value={totalCalories}
          minValue={0}
          maxValue={9999}
          step={50}
          onChange={onCalorieChange}
          aria-label="Total calories"
          formatOptions={{ maximumFractionDigits: 0 }}
        >
          <Input className={styles.calorieInput} />
        </NumberField>
        <span className={styles.calorieUnit}>calories</span>
      </div>

      <div className={styles.breakdown}>
        {macros.map((m) => {
          const cal = Math.round(m.grams * m.calPerGram);
          const pct = totalCalories > 0 ? Math.round((cal / totalCalories) * 100) : 0;
          return (
            <div key={m.key} className={styles.breakdownRow} data-macro={m.key}>
              <div className={styles.breakdownDot} />
              <span className={styles.breakdownLabel}>{m.label}</span>
              <span className={styles.breakdownCal}>{cal} cal</span>
              <span className={styles.breakdownPct}>{pct}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Macro Slider (original style) ───────────────────────────────────── */

function MacroSlider({ config, onMacroChange }: {
  config: MacroConfig;
  onMacroChange: (key: MacroKey, grams: number) => void;
}) {
  const calContribution = Math.round(config.grams * config.calPerGram);

  return (
    <Slider
      className={styles.slider}
      data-macro={config.key}
      minValue={config.min}
      maxValue={config.max}
      step={config.step}
      value={config.grams}
      onChange={(v: number) => onMacroChange(config.key, v)}
    >
      <div className={styles.sliderHeader}>
        <Label className={styles.sliderLabel}>{config.label}</Label>
        <div className={styles.sliderValues}>
          <SliderOutput className={styles.sliderAmount} />
          <span className={styles.sliderUnit}>g</span>
          <span className={styles.sliderCals}>({calContribution} cal)</span>
        </div>
      </div>
      <SliderTrack className={styles.track}>
        {({ state }) => (
          <>
            <div
              className={styles.trackFill}
              {...{ style: { "--track-width": `${state.getThumbPercent(0) * 100}%` } as React.CSSProperties }}
            />
            <SliderThumb className={styles.thumb} />
          </>
        )}
      </SliderTrack>
    </Slider>
  );
}

/* ── Slider Panel (right column / body) ──────────────────────────────── */

function SliderPanel({ macros, onMacroChange }: {
  macros: MacroConfig[];
  onMacroChange: (key: MacroKey, grams: number) => void;
}) {
  return (
    <div className={styles.sliderPanel}>
      {macros.map((m) => (
        <MacroSlider key={m.key} config={m} onMacroChange={onMacroChange} />
      ))}
    </div>
  );
}

/* ── Exports (used by entry to compose Card slots) ───────────────────── */

export { CaloriePanel, SliderPanel };
