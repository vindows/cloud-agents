# Harbor Wireless — design lock

**Recommended direction:** Signal Deck (light carrier NOC).

Full directions + critique live in the Project store:

- `docs/design/direction-a-signal-deck.md` (recommended)
- `docs/design/direction-b-tower-ops.md`
- `docs/design/direction-c-harbor-brief.md`
- `docs/design/critique-and-recommendation.md`

## Tokens (implement these)

```css
:root {
  --hw-navy: #0b1f33;
  --hw-signal: #0e9f9b;
  --hw-signal-soft: color-mix(in srgb, var(--hw-signal) 16%, white);
  --hw-fog: #e8eef2;
  --hw-panel: #f7fafc;
  --hw-ink: #0b1f33;
  --hw-slate: #5a6b7a;
  --hw-line: #c5d0d8;
  --hw-flare: #c45c26;
  --hw-route: #1f6b4a;
  --hw-warn: #a67c00;
  --hw-dup: #3a5f7a;
  --hw-font-brand: "Fraunces", "Source Serif 4", Georgia, serif;
  --hw-font-ui: "Manrope", "Segoe UI", system-ui, sans-serif;
  --hw-font-mono: "IBM Plex Mono", "SF Mono", ui-monospace, monospace;
  --hw-radius: 6px;
  --hw-ease: cubic-bezier(0.22, 1, 0.36, 1);
  --hw-dur-fast: 180ms;
  --hw-dur: 280ms;
  --hw-dur-pulse: 1200ms;
}
```

## Layout (short)

- **First viewport:** Harbor Wireless brand + live triage spine (classify → dedupe → priority → route → archive) + one ticket + one reasoning block. No stats strip.
- **Tickets / queue:** Table/list, not card grids. Selected row: panel bg + 3px signal left edge.
- **Ops:** ≤3 hero metrics, then one category bar set.
- **Policy:** Auto / Human / Hybrid segmented control.
- **Cards:** interactive surfaces only.

## Motion (short)

1. Step underline grows L→R on advance.
2. Reason text fades/slides up on step complete.
3. Opacity pulse on active stage dot only; respect `prefers-reduced-motion`.

Avoid purple/cream AI clichés, glow shadows, and pill chip clouds.
