# Frontend

A React and TypeScript app for ponds, forecasts and alerts, built with Bun, Vite and Tailwind CSS. It talks only to the [Go backend](../backend/README.md).

```powershell
bun install
bun run dev
```

It opens on `http://127.0.0.1:5190` and passes `/api` to `http://127.0.0.1:8090`. Set `API_URL` to use another backend.

| Folder | Purpose |
| --- | --- |
| `src/api` | Requests, types, cached queries |
| `src/charts` | Water column, oxygen chart, trend, all plain SVG |
| `src/lib` | Time, pond states, scales, motion helpers |
| `src/pages` | One file per page, loaded when opened |
| `src/styles` | Tailwind theme with both colour sets, and motion |
| `src/ui` | Buttons, fields, dialogs, notices, page frame, shared utility groups |
| `e2e` | Browser tour with measurements |

## Rules the interface keeps

- It never calls a pond safe. Having no alert is shown as having no alert.
- A withheld forecast output stays hidden. The only 90% range is at +1 h, and there is no value at +12 h.
- Demo data carries a demo label everywhere it appears.
- Colours judge a reading only against limits the operator chose. They always come with words or an icon.
- Times use the pond's timezone. A missing or partial hour breaks the chart line.

## Motion

There is no animation library. Layout uses Tailwind utilities. All movement is in `src/styles/motion.css`, the Web Animations API and browser view transitions.

- Only `transform`, `opacity`, `clip-path` and colours animate. `bun run lint` fails on anything that moves layout, and on Tailwind motion utilities that would bypass the check.
- The boot story plays once per visit and any key or tap skips it. It waits for real loading, not the reverse.
- Endless motion is limited to water waves, which rest when off screen.
- The app times its own page transitions. A device that is slow twice keeps the lighter entrances only.
- `prefers-reduced-motion` removes movement and keeps fades.

Measured in Chrome on 22 November 2026 on a 144 Hz laptop, on a production build.

| | Result |
| --- | ---: |
| JavaScript to first page, compressed | 118 KB, plus 1 to 5 KB per page |
| Frame time during page changes and chart drawing, 95th percentile | 7.1 ms |
| Tasks over 50 ms during the tour | 0 |
| Main thread in use when idle | 0.2 to 0.4% |
| Layout shift | 0.009 |
| Boot, first visit and later | 2.0 s, 0.4 s |
| Worst frame on page change, processor slowed 6 times | about 240 ms before adapting, 35 to 83 ms after |

## Checks

```powershell
bun run lint
bun run test
bun run build
```

`node e2e/tour.mjs <folder> <file.csv>` drives the whole product in an installed Chrome, saves screenshots and prints the measurements. Run it against `bun run preview` and an empty test database. It creates accounts and ponds.
