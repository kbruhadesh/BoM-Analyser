/**
 * SummaryBar.jsx
 * 4 metric cards: total cost, savings, components, in-stock ratio.
 */
import { TrendingDown, Package, CheckCircle, IndianRupee } from 'lucide-react'
import { formatINR } from '../lib/utils.js'

function Metric({ icon: Icon, label, value, sub, accent }) {
  return (
    <div className="card px-4 py-3 flex items-start gap-3">
      <div className={`w-7 h-7 rounded flex items-center justify-center mt-0.5 ${accent}`}>
        <Icon size={14} />
      </div>
      <div className="min-w-0">
        <p className="eyebrow mb-0.5">{label}</p>
        <p className="text-xl font-semibold text-ink font-mono tabular leading-tight">{value}</p>
        {sub && <p className="text-2xs text-ink-3 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

export default function SummaryBar({ summary }) {
  if (!summary) return null

  const {
    total_components,
    total_estimated_cost_inr,
    total_savings_inr,
    components_in_stock,
    components_out_of_stock,
    cheapest_vendor_overall,
    usd_inr_rate,
  } = summary

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
      <Metric
        icon={IndianRupee}
        label="Est. Total Cost"
        value={formatINR(total_estimated_cost_inr, 2)}
        sub={`${total_components} components`}
        accent="bg-trace/10 text-trace"
      />
      <Metric
        icon={TrendingDown}
        label="Total Savings"
        value={formatINR(total_savings_inr, 2)}
        sub={`vs. worst vendor`}
        accent="bg-stock/10 text-stock"
      />
      <Metric
        icon={CheckCircle}
        label="In Stock"
        value={`${components_in_stock}/${total_components}`}
        sub={`${components_out_of_stock > 0 ? components_out_of_stock + ' OOS' : 'All available'}`}
        accent="bg-stock/10 text-stock"
      />
      <Metric
        icon={Package}
        label="Best Vendor"
        value={cheapest_vendor_overall ?? '—'}
        sub={`1 USD = ₹${usd_inr_rate?.toFixed(2)}`}
        accent="bg-purple/10 text-purple"
      />
    </div>
  )
}
