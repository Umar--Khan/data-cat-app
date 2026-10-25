# Styling

> _Draft_ · Last verified against code: not yet

## Purpose

The design principles the UI follows, and the Tailwind v4 setup that enforces them: semantic tokens defined once in CSS, a variant pattern for primitives, and contrast checked at the token level rather than per component.

## Key files

- `frontend/src/index.css`: `@import "tailwindcss"`, the `@theme` tokens, the base layer, the sonner colour mapping.
- `frontend/src/components/ui/`: primitives, each with one `tv()` definition.
- `prettier.config.js`: `prettier-plugin-tailwindcss`, scoped to `frontend/**`, with `tailwindStylesheet` set to the CSS above and `tailwindFunctions: ["tv", "cn"]`.

## Behaviour contract

Design principles:

1. **One column, content first.** Header, form card, then the list of cards. No decorative chrome. The form is the only call to action.
2. **Semantic tokens only.** Components say `bg-surface text-fg-muted`, never `bg-slate-100`.
3. **Every state is designed:** idle, pending, success, partial success (curation failed), empty, loading, failed load, and failed refresh with stale data.
4. **Status is text first.** Colour and icon reinforce the words and never replace them.
5. **Native before ARIA.** `button`, `label`, `ul`, `dl` and `dialog` come first. ARIA only adds names, descriptions and live regions.
6. **Quiet type.** Inter Variable at weights 400, 500 and 600: `text-2xl` for the `h1`, `text-lg` for `h2`, `text-base` for `h3` and body, `text-sm` for labels and metadata, `text-xs` for tags.
7. **4 px rhythm**, on Tailwind's default spacing scale: field gap `1.5`, card padding `5`–`6`, gap between cards `3`, between sections `8`.
8. **Restrained motion.** Colour and opacity only, 150 ms or less, behind `motion-safe`.

## Data contract

Tokens. Values are Tailwind 4 palette colours in OKLCH. Ratios are WCAG contrast against `surface` (white) unless another background is noted.

| Token                                       | Value                      | Use                                 | Contrast                                                   |
| ------------------------------------------- | -------------------------- | ----------------------------------- | ---------------------------------------------------------- |
| `canvas`                                    | slate-50                   | Page background                     |                                                            |
| `surface`                                   | white                      | Cards, inputs, dialog               |                                                            |
| `surface-muted`                             | slate-100                  | Tags, neutral badges, skeletons     |                                                            |
| `fg`                                        | slate-900                  | Body text                           | 17.84:1                                                    |
| `fg-muted`                                  | slate-600                  | Metadata, hints, neutral badge text | 7.56:1; 7.23:1 on canvas; 6.90:1 on surface-muted          |
| `border`                                    | slate-200                  | Decorative dividers only            | n/a                                                        |
| `border-input`                              | slate-500                  | Control borders                     | 4.77:1; 4.55:1 on canvas                                   |
| `accent` / `accent-hover`                   | indigo-600 / indigo-700    | Primary button                      |                                                            |
| `on-accent`                                 | white                      | Text on accent and danger buttons   | 6.44:1 on accent, 8.07:1 on accent-hover, 6.42:1 on danger |
| `accent-subtle` / `accent-subtle-fg`        | indigo-50 / indigo-700     | "Curated by Claude" badge           | 7.22:1                                                     |
| `focus`                                     | indigo-600                 | Focus ring                          | ≥ 5.76:1 on every background                               |
| `danger` / `danger-hover` / `danger-subtle` | red-700 / red-800 / red-50 | Delete, errors, error toast         | 6.42:1; 5.88:1 on danger-subtle                            |
| `warning-fg` / `warning-subtle`             | amber-800 / amber-50       | Curation failed, warning toast      | 6.88:1                                                     |
| `success-fg` / `success-subtle`             | emerald-800 / emerald-50   | Success toast                       | 7.19:1                                                     |

- The "Keyword curated" and "Sample data" badges and the info toast use `surface-muted` with `fg-muted`.
- Radii: `sm` 0.25rem (tags, badges), `md` 0.5rem (controls), `lg` 0.75rem (cards, dialog).
- Shadows: `sm` (cards), `lg` (dialog).
- Font: `Inter Variable`, self-hosted through `@fontsource-variable/inter`, so there are no third-party requests.

## Invariants & decided points

- **The default palette, radii and shadows are removed** (`--color-*: initial` and the same for radii and all four shadow namespaces: box, inset, drop and text). A raw hue in a component produces no CSS, so the tokens cannot be bypassed by accident, and contrast is checked once, on the tokens. White is therefore available only as the `surface` and `on-accent` tokens. Rejected: keeping the default palette and relying on convention.
- **The type scale and spacing keep Tailwind's default keys.** tailwind-merge resolves conflicts only on keys it knows. It reads custom `text-*` names as colours and does not merge custom radius names.
- **Variants use `tv()` from tailwind-variants.**
  - Prop types come from `VariantProps`.
  - A caller's `className` goes through `tv`'s `class` slot, so overrides merge correctly.
  - Ad-hoc composition uses `cn` from tailwind-variants, with no local wrapper.

  Rejected: class-variance-authority, which has no slots and needs a separate merge helper.

- **Focus.** A global `:focus-visible` outline: 2 px, `focus` colour, 2 px offset. Components never remove it.
- **Forced colours.** Buttons and badges carry `border border-transparent`, so they keep a visible boundary in high-contrast mode, where backgrounds are dropped.
- **The sonner overrides are unlayered on purpose.** sonner injects unlayered CSS, which beats anything inside `@layer`. Its default rich colours measure 3.07–4.36:1, below AA, so they are mapped to the tokens above.
- **Light only** (`color-scheme: light`). Because everything goes through tokens, dark mode means redefining these variables under a media query.

## Deferred / open

- Dark mode.
