/**
 * ResultsView.jsx
 * Wraps the results: tab bar (Matrix / Cards), SummaryBar, ExportBar.
 */
import { useState } from 'react'
import { ArrowLeft, LayoutGrid, Table2 } from 'lucide-react'
import SummaryBar from './SummaryBar.jsx'
import VendorMatrix from './VendorMatrix.jsx'
import OptimizationCard from './OptimizationCard.jsx'
import ExportBar from './ExportBar.jsx'
import { cx } from '../lib/utils.js'

const TABS = [
  { id: 'matrix', label: 'Vendor Matrix', icon: Table2 },
  { id: 'cards',  label: 'Optimization Cards', icon: LayoutGrid },
]

export default function ResultsView({ data, taskId, onReset }) {
  const [tab, setTab] = useState('matrix')

  const { summary, results = [] } = data

  return (
    <div className="animate-fade-in">
      {/* Top bar */}
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <button onClick={onReset} className="btn btn-ghost px-2 py-1.5">
            <ArrowLeft size={13} />
          </button>
          <div>
            <h2 className="text-base font-semibold text-ink">Analysis results</h2>
            <p className="text-xs text-ink-3">
              {results.length} components · All prices in ₹ INR
              {summary?.usd_inr_rate && (
                <> · 1 USD = ₹{summary.usd_inr_rate.toFixed(2)}</>
              )}
            </p>
          </div>
        </div>

        <ExportBar taskId={taskId} summary={summary} />
      </div>

      {/* Metrics */}
      <SummaryBar summary={summary} />

      {/* Tab bar */}
      <div className="flex items-center gap-1 mb-4 bg-elevated border border-border rounded-md p-1 w-fit">
        {TABS.map(t => {
          const Icon = t.icon
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cx(
                'flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors duration-100',
                tab === t.id
                  ? 'bg-surface text-ink border border-border shadow-sm'
                  : 'text-ink-3 hover:text-ink-2 border border-transparent'
              )}
            >
              <Icon size={12} />
              {t.label}
            </button>
          )
        })}
      </div>

      {/* Panel: Vendor Matrix */}
      {tab === 'matrix' && (
        <div className="animate-fade-in">
          <VendorMatrix results={results} />
        </div>
      )}

      {/* Panel: Optimization Cards */}
      {tab === 'cards' && (
        <div className="animate-fade-in space-y-3">
          {results.map(r => (
            <OptimizationCard key={r.normalized_mpn} result={r} />
          ))}
        </div>
      )}
    </div>
  )
}
