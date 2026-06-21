# BoM Analyzer — Frontend

React 18 + Vite + TailwindCSS dashboard for the BoM Analyzer backend.

## Design

**Theme:** PCB dark — oscilloscope-inspired readouts on a near-black `#0D1117` background.  
**Signature element:** Price cells styled as scope readout panels — dark canvas, coloured glowing text (green best, amber mid, red worst), monospaced font. The vendor matrix feels like reading a logic analyser.  
**Type:** JetBrains Mono for all part numbers, prices, and data. Inter for UI chrome.

## Quick start

```bash
npm install
npm run dev        # → http://localhost:3000
```

Requires the FastAPI backend running on port 8000. The Vite dev server proxies `/api/*` automatically.

## Testing

```bash
npm test           # run all tests once
npm run test:watch # watch mode
```

47 frontend tests across:
- Utility functions (`formatINR`, `priceRank`, `getVendorConfig`, `formatQty`)
- `useBomAnalysis` hook state machine (IDLE → SUBMITTING → POLLING → COMPLETE / FAILED)
- `BomUploader` (render, paste, file drop, submit, sample load, format badge)
- `SummaryBar` (metrics, FX rate, null guard)
- `VendorMatrix` (price cells, OOS, expand/collapse, savings)
- `OptimizationCard` (stock bar, price grid, split order, OOS state)
- `ExportBar` (Excel/JSON download, copy, share link)

## File structure

```
src/
├── App.jsx                     ← Root layout: sidebar + main column + PCB grid bg
├── main.jsx                    ← ReactDOM entry
├── index.css                   ← Tailwind base + custom scope-panel / badge / btn classes
├── lib/
│   ├── api.js                  ← Typed fetch client (analyzeBom, getTaskStatus, exportResult…)
│   └── utils.js                ← formatINR, priceRank, VENDOR_CONFIG, SAMPLE_BOM
├── hooks/
│   └── useBomAnalysis.js       ← State machine hook, polling loop, abort on reset
└── components/
    ├── BomUploader.jsx         ← Drag-drop + textarea + format auto-detect + sample loader
    ├── ProcessingView.jsx      ← Progress bar + stage indicators + scrolling log panel
    ├── SummaryBar.jsx          ← 4 metric cards (cost, savings, in-stock, best vendor)
    ├── VendorMatrix.jsx        ← Sticky-column price table with expandable price-break rows
    ├── OptimizationCard.jsx    ← Per-component card: stock bar + vendor pills + split order
    ├── ExportBar.jsx           ← Excel/JSON download + copy/share buttons
    └── ResultsView.jsx         ← Tab container (Matrix / Cards) + ExportBar
```

## Build for production

```bash
npm run build      # outputs to dist/
```

The `Dockerfile` builds with nginx and proxies `/api/*` to `http://api:8000`. Run with:

```bash
docker compose up --build
```

## INR / currency

All prices displayed with `₹` symbol using Indian number formatting (`en-IN` locale).  
Sub-₹1 prices show 4 decimal places; ₹1–₹10 show 3; ₹10+ show 2.  
FX rate shown in summary bar and footer.
