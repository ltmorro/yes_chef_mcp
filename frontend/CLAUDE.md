# Frontend Architecture Rules

> Governs all React TSX code under `frontend/`. Follow exactly.

---

## 1. React Aria Components (RAC)

**All interactive elements** (`button`, `input`, `select`, `dialog`, `a` with click handlers, `label`) must use `react-aria-components`. Raw HTML interactive elements are banned. Non-interactive elements (`div`, `span`, `img`, `h1`–`h6`, etc.) are fine.

**No inline styles.** All styling goes through CSS Modules (preferred), utility classes, or `global.css`. `style={{...}}` is categorically banned.

When wrapping RAC primitives into reusable components, support three tiers: standard props (`variant`, `size`, `isDisabled`) for most call sites; child render props for slot/icon customization; and full RAC prop passthrough + `ref` forwarding for deep overrides.

---

## 2. Spacing & Typography

**8-point grid** — every margin, padding, gap, width, and height must be a multiple of 8px. 4px is allowed only for tight internal micro-spacing (icon gaps, badge padding). No arbitrary values (10px, 6px, 14px, etc.). Use spacing tokens exclusively:

| Token | Value | Use |
|-------|-------|-----|
| `--space-1` | `4px` | Micro-adjustments only |
| `--space-2` | `8px` | Tight gaps, small padding |
| `--space-3` | `16px` | Standard padding, component gaps |
| `--space-4` | `24px` | Section spacing |
| `--space-5` | `32px` | Large section spacing |
| `--space-6` | `48px` | Page-level spacing |

**Internal ≤ External** — a component's external margin must be ≥ its internal padding (Gestalt proximity).

**Baseline-snapped line heights** (snap to nearest 4px):

| Role | Font Size | Line Height |
|------|-----------|-------------|
| Display heading | 28px | 32px |
| Section heading | 20px | 24px |
| Body | 16px | 24px |
| Small / caption | 12px | 20px |
| Badge / micro | 11px | 16px |

---

## 3. Tokens & Aesthetics

Never hardcode hex, rgb, or raw pixel values in component CSS — always use semantic tokens from `global.css`. Tokens are re-exported via `theme.ts` for JS-only use (canvas, etc.).

**Banned patterns:**
- Fonts: Inter, Roboto, Arial, system-ui — use `--font-brand` / `--font-mono`
- Color: hardcoded `#fff`/`#000`, arbitrary `opacity: 0.12` backgrounds, generic purple/indigo gradients — use `--color-*` semantic tokens
- Geometry: generic `8px` border-radius — only valid tokens are:

| Token | Value | Use |
|-------|-------|-----|
| `--radius-none` | `0px` | Cards, containers, inputs |
| `--radius-pill` | `9999px` | Badges, pills, tags |

- Shadows: invented values — only predefined elevation tokens:

| Token | Value |
|-------|-------|
| `--elevation-1` | `0 1px 2px rgba(0, 0, 0, 0.06)` |
| `--elevation-2` | `0 2px 8px rgba(0, 0, 0, 0.08)` |
| `--elevation-3` | `0 4px 16px rgba(0, 0, 0, 0.08)` |

---

## 4. Interaction States

**No layout shifts** — interactive states must never shift layout. Simulate border changes with inset `box-shadow`, not `border-width`.

**No CSS pseudo-classes** for interactive styling. Use RAC data attributes: `[data-hovered]`, `[data-pressed]`, `[data-focused]`, `[data-focus-visible]`, `[data-disabled]`, `[data-selected]`, `[data-invalid]`.

**Focus rings** use `outline` + `outline-offset` on `[data-focus-visible]` only — not `box-shadow`, not `:focus`:

```css
[data-focus-visible] {
  outline: 2px solid var(--color-border-focus);
  outline-offset: 2px;
}
```

**Error states** — pre-allocate `min-height: 20px` for validation messages so error text never causes layout shifts.

---

## 5. File & Module Conventions

```
src/
  components/
    Button/
      Button.tsx        # RAC-based implementation
      Button.module.css
      index.ts          # re-export
  entries/              # page entry points (thin orchestration)
  global.css            # reset, CSS custom properties, root layout
  theme.ts              # tokens for JS-only use
  types.ts              # shared TypeScript types
  bridge.ts             # API communication
```

- Files: `PascalCase.tsx` / `PascalCase.module.css`
- CSS custom properties: `--category-name` (kebab-case) · CSS class names: `camelCase` · Types/interfaces: `PascalCase` · Props: `ComponentNameProps`
- Barrel exports from `components/index.ts` — flat, no nested re-exports, no circular imports

---

## 6. TypeScript

Strict mode on. No `any` — use a union, protocol, or `unknown` + narrowing. No `as` assertions unless unavoidable. Props interfaces required on all components — no inline object types. Constrain RAC generics (e.g. `ListBoxItem<RecipeHit>`).

---

## 7. Accessibility

RAC handles ARIA semantics — do not override `role`, `aria-label`, or `tabIndex` without reason. Every form field needs a RAC `<Label>`. Every `<Popover>`/`<Dialog>`/`<Modal>` needs an `aria-label`. Never use color as the sole state indicator. Do not break RAC keyboard navigation with custom event handlers.

---

## 8. Card Component — Default Bounded Surface

`src/components/Card/Card.tsx` is the canonical surface for new UI elements. Use it before reaching for a raw `<div>`. Do **not** recreate card-like layouts ad-hoc.

Named slots (all optional): `leadingMedia`, `pretitle`, `title`, `subtitle`, `trailingMedia`, `body`, `footer`. Pass `children` for freeform content. Use `onClick` for interactive cards, `selected` for selection state.

```tsx
<Card
  leadingMedia={<img src={recipe.thumbnail} alt="" />}
  title={recipe.name}
  subtitle={`${recipe.calories} kcal`}
  trailingMedia={<MacroBadge macros={recipe.macros} />}
  footer={<Button onPress={() => select(recipe)}>Add to plan</Button>}
/>
```

---

## 9. Migration Notes

Existing components (`Button.tsx`, `Card.tsx`, `MacroBadge.tsx`, `ProgressBar.tsx`) do not yet comply — they use raw HTML elements, inline styles, hardcoded values, Inter, and non-grid spacing. Migrate a component when the task at hand touches it. New components must comply from the start.