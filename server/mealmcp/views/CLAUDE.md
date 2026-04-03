# views/CLAUDE.md — Frontend Architecture Rules

> These rules govern all React TSX code under `server/mealmcp/views/`.
> AI coding agents and human contributors must follow them exactly.

---

## 1. React Aria Components (RAC) — Exclusive Interactive Primitives

### 1.1 No Raw HTML for Interactive Elements

Every interactive element must use `react-aria-components`. Do **not** render raw
`<button>`, `<input>`, `<select>`, `<dialog>`, `<a>` (with click handlers), or
`<label>` for complex interactive patterns.

```tsx
// WRONG — raw HTML button
<button onClick={onSave}>Save</button>

// CORRECT — RAC compound component
import { Button } from "react-aria-components";
<Button onPress={onSave}>Save</Button>
```

Compose complex widgets from RAC's declarative building blocks:

```tsx
import { Select, Label, Button, SelectValue, Popover, ListBox, ListBoxItem } from "react-aria-components";

<Select>
  <Label>Category</Label>
  <Button><SelectValue /></Button>
  <Popover>
    <ListBox>
      <ListBoxItem>Main</ListBoxItem>
      <ListBoxItem>Side</ListBoxItem>
    </ListBox>
  </Popover>
</Select>
```

Plain `<div>`, `<span>`, `<canvas>`, `<img>`, `<h1>`–`<h6>`, and other non-interactive
or purely presentational HTML elements remain fine.

### 1.2 Absolute Separation of Style and Logic

RAC components are headless. **Inline styles (`style={{...}}`) are categorically banned.**

Apply all visual styles through one of:

1. **CSS Modules** (`.module.css` files co-located with the component) — preferred
2. **Utility classes** mapped to semantic slots (e.g., via Tailwind Variants)
3. **Global CSS** for resets and root-level layout only (`global.css`)

```tsx
// WRONG
<Button style={{ padding: "10px 20px", background: "#6366f1" }}>Save</Button>

// CORRECT
import styles from "./Button.module.css";
<Button className={styles.primary}>Save</Button>
```

### 1.3 Tiered Component API

When wrapping RAC primitives into reusable system components, expose three tiers:

| Tier | API Surface | Use Case |
|------|-------------|----------|
| **Config** | Standard props: `variant`, `size`, `isDisabled` | Quick usage, most call sites |
| **Slots** | Child render props for node targeting | Customizing icon placement, adornments |
| **Custom** | Exposed RAC primitives + DOM `ref` forwarding | Deep composition overrides |

```tsx
// Config tier (simple)
<ChefButton variant="primary" size="md">Save</ChefButton>

// Slots tier (node targeting)
<ChefButton variant="primary">
  {({ isPressed }) => (
    <>
      <Icon name={isPressed ? "check" : "save"} />
      Save
    </>
  )}
</ChefButton>

// Custom tier (full override)
<ChefButton variant="primary" ref={buttonRef} {...rac props passthrough}>
  Save
</ChefButton>
```

---

## 2. Spatial & Typographic Rigor

### 2.1 Inviolable 8-Point Grid

Every spatial value — margin, padding, gap, width, height — must be an **exact multiple
of 8px**. The only exception is a 4px micro-adjustment for tight internal spacing
(icon-to-label gaps, badge internal padding).

```css
/* WRONG */
padding: 10px 20px;    /* 10 and 20 are not on the 8pt grid */
margin-bottom: 6px;    /* 6 is not on the 8pt grid */
gap: 12px;             /* 12 is not on the 8pt grid */

/* CORRECT */
padding: 8px 16px;     /* 8pt grid */
margin-bottom: 8px;    /* 8pt grid */
gap: 16px;             /* 8pt grid */
padding: 4px 8px;      /* 4px micro-adjustment for tight internal spacing */
```

Use the spacing tokens exclusively:

| Token | Value | Use |
|-------|-------|-----|
| `--space-1` | `4px` | Micro-adjustments only |
| `--space-2` | `8px` | Tight gaps, small padding |
| `--space-3` | `16px` | Standard padding, component gaps |
| `--space-4` | `24px` | Section spacing |
| `--space-5` | `32px` | Large section spacing |
| `--space-6` | `48px` | Page-level spacing |

**Hardcoding arbitrary pixel values (e.g., 10px, 15px, 6px, 14px) is prohibited.**

### 2.2 Internal <= External Rule

A component's external margin must always be >= its internal padding. This preserves
the Gestalt principle of proximity — content inside a container must feel more
tightly grouped than the space between containers.

```css
/* WRONG — 24px internal, 16px external */
.card { padding: 24px; margin-bottom: 16px; }

/* CORRECT — 24px internal, 32px external */
.card { padding: var(--space-4); margin-bottom: var(--space-5); }
```

### 2.3 Baseline-Snapped Typography

Line heights use specific multipliers and **must snap to the nearest 4px**:

| Role | Font Size | Multiplier | Raw Result | Snapped Line Height |
|------|-----------|------------|------------|---------------------|
| Display heading | 28px | 1.14 | 31.92 | 32px |
| Section heading | 20px | 1.2 | 24 | 24px |
| Body | 16px | 1.5 | 24 | 24px |
| Small / caption | 12px | 1.5 | 18 | 20px |
| Badge / micro | 11px | 1.45 | 15.95 | 16px |

---

## 3. Aesthetic Governance & Anti-Slop Directives

### 3.1 Semantic Tokenization

**Never hardcode** raw hex codes, rgb values, or pixel measurements in component CSS.
Always consume semantic CSS custom properties from the token foundation.

```css
/* WRONG */
color: #e2e8f0;
background: rgba(99, 102, 241, 0.12);
border-radius: 10px;

/* CORRECT */
color: var(--color-text);
background: var(--color-primary-bg);
border-radius: var(--radius-pill);
```

All tokens are defined as CSS custom properties on `:root` in `global.css` and
re-exported via `theme.ts` for any rare cases needing JS access (canvas rendering).

### 3.2 Anti-Slop Prohibitions

These patterns are hallmarks of generic AI output and are **explicitly banned**:

#### Typography
- Do not use Inter, Roboto, Arial, or system-ui as the primary font.
- Use the designated brand font family defined in `--font-brand`.
- Monospace values use the font defined in `--font-mono`.

#### Color
- No cliched high-saturation purple/indigo/electric-blue gradients unless
  explicitly defined in the token foundation.
- No random `opacity: 0.12` backgrounds — use only the defined `*-bg` semantic tokens.
- No hardcoded `#fff` or `#000` — use `--color-text-inverse` or `--color-bg`.

#### Geometry
- Do **not** apply a generic `8px` border-radius universally.
- Use **sharp corners** (`0px`) or **pill geometry** (`9999px`) as dictated by tokens.
- The only valid radius tokens are:

| Token | Value | Use |
|-------|-------|-----|
| `--radius-none` | `0px` | Cards, containers, inputs |
| `--radius-pill` | `9999px` | Badges, pills, tags |

#### Shadows
- Do not invent shadow values. Only use predefined elevation tokens.
- Maximum 3 elevation levels, all with low opacity (4–8%) and controlled spreads:

| Token | Value |
|-------|-------|
| `--elevation-1` | `0 1px 2px rgba(0, 0, 0, 0.06)` |
| `--elevation-2` | `0 2px 8px rgba(0, 0, 0, 0.08)` |
| `--elevation-3` | `0 4px 16px rgba(0, 0, 0, 0.08)` |

---

## 4. Interaction Physics & Tactile Mechanics

### 4.1 Zero Layout Shifts

Interactive states (hover, focus, pressed, error) must **never** cause layout shifts.

- If a border thickens on hover, use an inset `box-shadow` or absolutely positioned
  pseudo-element — do not change `border-width`.
- Selected states use `box-shadow` for the highlight ring, not thicker borders.

```css
/* WRONG — changes border-width, causes 1px layout shift */
&[data-hovered] { border-width: 2px; }

/* CORRECT — inset shadow simulates thicker border */
&[data-hovered] { box-shadow: inset 0 0 0 1px var(--color-border-focus); }
```

### 4.2 Data-Attribute Styling

Do **not** use CSS pseudo-classes (`:hover`, `:active`, `:focus`) for interactive
state styling. Use RAC's deterministic data attributes for cross-device fidelity:

```css
/* WRONG */
.button:hover { background: var(--color-surface-hover); }
.button:focus { outline: 2px solid blue; }

/* CORRECT */
.button[data-hovered] { background: var(--color-surface-hover); }
.button[data-focused] { outline: 2px solid var(--color-border-focus); }
.button[data-pressed] { transform: scale(0.98); }
.button[data-disabled] { opacity: 0.5; cursor: not-allowed; }
```

Available RAC data attributes:
- `[data-hovered]` — pointer hover
- `[data-pressed]` — active press
- `[data-focused]` — any focus
- `[data-focus-visible]` — keyboard focus only
- `[data-disabled]` — disabled state
- `[data-selected]` — selected / checked
- `[data-invalid]` — validation error

### 4.3 Stable Focus Rings

Keyboard focus rings are drawn **outside** the component bounding box using
`outline` + `outline-offset`. Do not use `box-shadow` for focus (reserve it for
selected/hover states). Do not use `:focus` — use `[data-focus-visible]`.

```css
[data-focus-visible] {
  outline: 2px solid var(--color-border-focus);
  outline-offset: 2px;
}
```

### 4.4 Error State Pre-allocation

Pre-allocate space for validation messages in the layout grid. The appearance of
error text must **never** push adjacent content down.

```css
/* Reserve 20px (snapped to 4px grid) for error text regardless of state */
.field-error {
  min-height: 20px;
  font-size: 12px;
  line-height: 20px;
  color: var(--color-danger);
  visibility: hidden;
}
.field-error[data-visible] {
  visibility: visible;
}
```

---

## 5. File & Module Conventions

### 5.1 Component File Structure

```
src/
  components/
    Button/
      Button.tsx          # Component implementation (uses RAC)
      Button.module.css   # Scoped styles
      index.ts            # Re-export
    Card/
      Card.tsx
      Card.module.css
      index.ts
  entries/                 # Page entry points (thin orchestration)
  global.css               # Reset, CSS custom properties, root layout
  theme.ts                 # Token values exported for JS-only use (canvas, etc.)
  types.ts                 # Shared TypeScript types
  bridge.ts                # API communication
```

### 5.2 Naming Conventions

- Component files: `PascalCase.tsx`
- CSS modules: `PascalCase.module.css`
- CSS custom properties: `--category-name` (kebab-case)
- CSS class names inside modules: `camelCase`
- TypeScript types/interfaces: `PascalCase`
- Props interfaces: `ComponentNameProps`

### 5.3 Import Rules

- Import RAC components from `react-aria-components`
- Import CSS modules as `import styles from "./Component.module.css"`
- Barrel exports from `components/index.ts` — keep flat, no nested re-exports
- No circular imports between components

---

## 6. TypeScript Constraints

- **Strict mode** is on — `tsconfig.json` enforces `strict: true`
- **No `any`** — find the real type, use a union, or use `unknown` + narrowing
- **No inline type assertions** (`as`) unless unavoidable (e.g., `getElementById`)
- Props interfaces are **required** for all components — no inline object types
- RAC generic types should be properly constrained (e.g., `ListBoxItem<RecipeHit>`)

---

## 7. Accessibility Requirements

- All interactive components inherit RAC's built-in ARIA semantics — do not override
  `role`, `aria-label`, or `tabIndex` unless you have a specific reason
- Every form field must have an associated `<Label>` from RAC
- Every `<Popover>`, `<Dialog>`, and `<Modal>` must have a descriptive `aria-label`
- Color is never the sole indicator of state — always pair with text or iconography
- Keyboard navigation must work for all interactive flows (RAC handles this when
  used correctly — do not break it with custom event handlers)
- Test with screen reader and keyboard-only navigation before marking complete

---

## 8. Migration Notes (Current State)

The existing components (`Button.tsx`, `Card.tsx`, `MacroBadge.tsx`, `ProgressBar.tsx`)
and entry pages **do not yet comply** with these rules. They use:

- Raw `<button>`, `<input type="range">`, `<label>` elements
- Inline `style={{...}}` on every element
- Hardcoded hex colors and arbitrary pixel values
- Inter as primary font
- Non-grid-aligned spacing (10px, 6px, 2px, 14px, etc.)
- Generic border-radius values (6px, 10px, 14px)

When modifying these components, migrate them to comply with these rules. New
components must comply from the start. Do not refactor existing components
unless the task at hand touches that component.
