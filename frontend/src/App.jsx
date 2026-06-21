/**
 * App.jsx — Root component.
 * Manages top-level view state: upload → processing → results.
 * PCB-dark layout with a fixed left rail + main content area.
 */
import { useEffect } from 'react'
import { Cpu, Github, CircuitBoard, Zap } from 'lucide-react'
import { useBomAnalysis, STATES } from './hooks/useBomAnalysis.js'
import BomUploader from './components/BomUploader.jsx'
import ProcessingView from './components/ProcessingView.jsx'
import ResultsView from './components/ResultsView.jsx'
import { cx } from './lib/utils.js'

// ── Sidebar nav ───────────────────────────────────────────────────────────────
function Sidebar({ state }) {
  const steps = [
    { id: 'upload',  label: 'Upload BoM',   icon: CircuitBoard },
    { id: 'analyze', label: 'Analyze',       icon: Zap },
    { id: 'results', label: 'Results',       icon: Cpu },
  ]

  const activeStep =
    state === STATES.IDLE       ? 'upload'
    : state === STATES.SUBMITTING || state === STATES.POLLING ? 'analyze'
    : 'results'

  return (
    <aside className="hidden lg:flex flex-col w-52 shrink-0 border-r border-border bg-surface min-h-screen sticky top-0 h-screen">
      {/* Logo */}
      <div className="px-5 pt-5 pb-4 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded bg-trace/10 border border-trace/20 flex items-center justify-center">
            <Cpu size={14} className="text-trace" />
          </div>
          <div>
            <p className="text-sm font-semibold text-ink tracking-tight leading-none">BoM Analyzer</p>
            <p className="text-2xs text-ink-3 mt-0.5">v1.0 · INR</p>
          </div>
        </div>
      </div>

      {/* Nav steps */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {steps.map((step, i) => {
          const Icon = step.icon
          const isActive = step.id === activeStep
          const isDone =
            (step.id === 'upload'  && activeStep !== 'upload') ||
            (step.id === 'analyze' && activeStep === 'results')

          return (
            <div
              key={step.id}
              className={cx(
                'flex items-center gap-2.5 px-2.5 py-2 rounded text-xs transition-colors duration-100',
                isActive
                  ? 'bg-trace/10 text-trace border border-trace/20'
                  : isDone
                  ? 'text-stock'
                  : 'text-ink-3'
              )}
            >
              <div className={cx(
                'w-5 h-5 rounded-full border flex items-center justify-center text-2xs font-mono shrink-0',
                isActive ? 'border-trace bg-trace/10 text-trace'
                : isDone  ? 'border-stock bg-stock/10 text-stock'
                : 'border-border text-ink-3'
              )}>
                {isDone ? '✓' : i + 1}
              </div>
              <span className="font-medium">{step.label}</span>
            </div>
          )
        })}
      </nav>

      {/* Vendor list */}
      <div className="px-4 py-4 border-t border-border">
        <p className="eyebrow mb-2">Vendors</p>
        <div className="space-y-1">
          {[
            { name: 'DigiKey',   cls: 'badge-digikey' },
            { name: 'Mouser',    cls: 'badge-mouser'  },
            { name: 'LCSC',      cls: 'badge-lcsc'    },
            { name: 'Arrow',     cls: 'badge-arrow'   },
            { name: 'Robu.in',   cls: 'badge-robu'    },
            { name: 'Evelta',    cls: 'badge-evelta'  },
          ].map(v => (
            <div key={v.name} className="flex items-center gap-2">
              <span className={cx('w-1.5 h-1.5 rounded-full', v.cls.replace('badge-', 'bg-'))} />
              <span className="text-2xs text-ink-3 font-mono">{v.name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-border">
        <a
          href="https://github.com"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-2xs text-ink-3 hover:text-ink-2 transition-colors"
        >
          <Github size={11} />
          View on GitHub
        </a>
      </div>
    </aside>
  )
}

// ── Mobile header ─────────────────────────────────────────────────────────────
function MobileHeader() {
  return (
    <header className="lg:hidden flex items-center gap-2.5 px-4 py-3 border-b border-border bg-surface sticky top-0 z-30">
      <div className="w-6 h-6 rounded bg-trace/10 border border-trace/20 flex items-center justify-center">
        <Cpu size={12} className="text-trace" />
      </div>
      <p className="text-sm font-semibold text-ink">BoM Analyzer</p>
      <span className="text-2xs text-ink-3 font-mono ml-auto">₹ INR</span>
    </header>
  )
}

// ── Grid overlay (subtle PCB trace background) ────────────────────────────────
function PcbGrid() {
  return (
    <div
      className="fixed inset-0 pointer-events-none z-0 opacity-[0.025]"
      style={{
        backgroundImage: `
          linear-gradient(rgba(88,166,255,0.5) 1px, transparent 1px),
          linear-gradient(90deg, rgba(88,166,255,0.5) 1px, transparent 1px)
        `,
        backgroundSize: '40px 40px',
      }}
    />
  )
}

// ── Root App ──────────────────────────────────────────────────────────────────
export default function App() {
  const {
    state, taskId, progress, currentComponent,
    result, error,
    submit, reset,
    isIdle, isBusy, isComplete, isFailed,
  } = useBomAnalysis()

  // Read shared task from URL on load
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const sharedTask = params.get('task')
    if (sharedTask) {
      // Could auto-fetch result here; for now just note it
      console.info('[BoM] Shared task ID from URL:', sharedTask)
    }
  }, [])

  return (
    <div className="flex min-h-screen bg-canvas relative">
      <PcbGrid />

      {/* Sidebar */}
      <Sidebar state={state} />

      {/* Main column */}
      <div className="flex-1 flex flex-col min-w-0 relative z-10">
        <MobileHeader />

        <main className="flex-1 px-4 py-6 lg:px-8 lg:py-8 max-w-5xl mx-auto w-full">

          {/* ── Upload / idle ── */}
          {(isIdle || isFailed) && (
            <>
              <BomUploader onSubmit={submit} isBusy={isBusy} />
              {isFailed && error && (
                <div className="mt-4 p-3 rounded border border-danger/40 bg-danger/5 text-danger text-sm">
                  <strong className="font-mono">Error:</strong> {error}
                </div>
              )}
            </>
          )}

          {/* ── Processing ── */}
          {isBusy && (
            <ProcessingView
              progress={progress}
              currentComponent={currentComponent}
              onCancel={reset}
            />
          )}

          {/* ── Results ── */}
          {isComplete && result && (
            <ResultsView
              data={result}
              taskId={taskId}
              onReset={reset}
            />
          )}
        </main>

        {/* Footer */}
        <footer className="px-4 py-3 lg:px-8 border-t border-border/50 bg-surface/50">
          <p className="text-2xs text-ink-3 text-center">
            BoM Analyzer · Prices scraped live, cached 4 h · Vendor data may vary ·
            Always verify critical component pricing before ordering
          </p>
        </footer>
      </div>
    </div>
  )
}
