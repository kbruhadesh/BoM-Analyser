/**
 * ProcessingView.jsx
 * Shown while Celery task is running.
 * Oscilloscope-inspired progress bar + live component log.
 */
import { useEffect, useRef, useState } from 'react'
import { Cpu, X } from 'lucide-react'
import { cx } from '../lib/utils.js'

// Simulated log messages for UX while we wait for real progress
const LOG_STEPS = [
  '→ Parsing BoM input format…',
  '→ Fuzzy-matching column headers…',
  '→ Normalising MPNs (stripping package suffixes)…',
  '→ Fetching live USD/INR exchange rate…',
  '→ Querying LCSC public JSON endpoint…',
  '→ Launching Playwright for DigiKey IN…',
  '→ Launching Playwright for Mouser IN (stealth mode)…',
  '→ Querying Arrow partner API…',
  '→ Scraping Robu.in…',
  '→ Scraping Evelta.com…',
  '→ Caching results in Redis (TTL 4 h)…',
  '→ Running cost optimisation (weighted scoring)…',
  '→ Generating split-order plan…',
  '→ Building vendor comparison matrix…',
  '→ Analysis complete ✓',
]

export default function ProcessingView({ progress, currentComponent, onCancel }) {
  const [logLines, setLogLines] = useState([LOG_STEPS[0]])
  const [logIdx, setLogIdx]     = useState(0)
  const logRef = useRef(null)

  // Advance simulated log at a fixed cadence
  useEffect(() => {
    const interval = setInterval(() => {
      setLogIdx(prev => {
        const next = Math.min(prev + 1, LOG_STEPS.length - 1)
        setLogLines(lines => {
          const updated = [...lines, LOG_STEPS[next]]
          return updated.slice(-8)   // keep last 8 lines
        })
        return next
      })
    }, 1800)
    return () => clearInterval(interval)
  }, [])

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [logLines])

  const pct = Math.max(0, Math.min(100, progress))

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-trace/10 border border-trace/20 flex items-center justify-center">
            <Cpu size={16} className="text-trace animate-pulse-slow" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-ink">Analyzing BoM</h2>
            <p className="text-xs text-ink-3">
              {currentComponent
                ? <><span className="text-ink-2">Processing:</span> <span className="font-mono text-trace">{currentComponent}</span></>
                : 'Initialising analysis pipeline…'
              }
            </p>
          </div>
        </div>
        <button onClick={onCancel} className="btn btn-ghost px-2 py-1">
          <X size={14} />
        </button>
      </div>

      {/* Progress bar — oscilloscope trace style */}
      <div className="mb-1 flex items-center justify-between">
        <span className="eyebrow">Progress</span>
        <span className="font-mono text-xs text-trace">{pct}%</span>
      </div>
      <div className="h-1.5 bg-elevated rounded-full overflow-hidden border border-border mb-5">
        <div
          className="h-full bg-gradient-to-r from-trace to-stock rounded-full transition-all duration-500 ease-out shadow-glow-blue"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Stage indicators */}
      <div className="grid grid-cols-4 gap-1.5 mb-6">
        {['Parse', 'Normalize', 'Scrape', 'Optimize'].map((stage, i) => {
          const stagePct = (i + 1) * 25
          const done = pct >= stagePct
          const active = pct >= stagePct - 25 && pct < stagePct
          return (
            <div
              key={stage}
              className={cx(
                'text-center py-2 px-1 rounded border text-2xs font-mono transition-colors duration-300',
                done   ? 'border-stock/40 bg-stock/10 text-stock'
                : active ? 'border-trace/40 bg-trace/10 text-trace'
                : 'border-border bg-elevated text-ink-3'
              )}
            >
              {done ? '✓ ' : active ? '⟳ ' : ''}{stage}
            </div>
          )
        })}
      </div>

      {/* Scrolling log panel — the signature oscilloscope "readout" element */}
      <div className="scope-panel overflow-hidden rounded-md">
        <div className="flex items-center gap-2 px-3 py-1.5 border-b border-border bg-elevated">
          <div className="flex gap-1">
            <span className="w-2 h-2 rounded-full bg-danger/70" />
            <span className="w-2 h-2 rounded-full bg-warn/70" />
            <span className="w-2 h-2 rounded-full bg-stock/70" />
          </div>
          <span className="eyebrow text-2xs">task.log</span>
        </div>
        <div
          ref={logRef}
          className="h-36 overflow-y-auto px-3 py-2 no-scrollbar"
        >
          {logLines.map((line, i) => (
            <p
              key={i}
              className={cx(
                'text-xs font-mono leading-5 transition-opacity duration-300',
                i === logLines.length - 1 ? 'text-stock' : 'text-ink-3'
              )}
            >
              {line}
            </p>
          ))}
          {/* Blinking cursor */}
          <span className="inline-block w-1.5 h-3 bg-stock animate-pulse" />
        </div>
      </div>
    </div>
  )
}
