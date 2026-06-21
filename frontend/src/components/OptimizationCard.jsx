/**
 * OptimizationCard.jsx
 * Per-component card showing best vendor, stock bar, all-vendor price list,
 * split-order plan if applicable.
 */
import { Package, AlertTriangle, CheckCircle2, Layers } from 'lucide-react'
import { formatINR, formatQty, getVendorConfig, cx } from '../lib/utils.js'

function StockBar({ stock, required }) {
  const pct = required > 0 ? Math.min(100, Math.round((stock / required) * 100)) : 0
  const ok = pct >= 100
  return (
    <div>
      <div className="flex justify-between text-2xs font-mono mb-1">
        <span className="text-ink-3">Stock vs. required</span>
        <span className={ok ? 'text-stock' : 'text-warn'}>
          {formatQty(stock)} / {required}
        </span>
      </div>
      <div className="h-1 bg-elevated rounded-full overflow-hidden border border-border">
        <div
          className={cx('h-full rounded-full transition-all duration-500', ok ? 'bg-stock' : 'bg-warn')}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function VendorPricePill({ vendorResult, isBest }) {
  const cfg = getVendorConfig(vendorResult.vendor)
  const oos = vendorResult.availability === 'Out of Stock'
  return (
    <div className={cx(
      'flex items-center gap-2 px-2.5 py-1.5 rounded border text-xs',
      isBest
        ? 'border-stock/40 bg-stock/5'
        : oos
        ? 'border-border bg-elevated opacity-50'
        : 'border-border bg-elevated'
    )}>
      <span className={cx('text-2xs font-mono px-1 py-0.5 rounded border', cfg.badgeClass)}>
        {cfg.short}
      </span>
      <span className={cx(
        'font-mono text-xs',
        oos ? 'text-ink-3 line-through' : isBest ? 'text-stock font-medium' : 'text-ink-2'
      )}>
        {oos ? 'OOS' : formatINR(vendorResult.unit_price_inr)}
      </span>
      {vendorResult.moq > 1 && !oos && (
        <span className="text-2xs text-ink-3">MOQ {vendorResult.moq}</span>
      )}
      {isBest && <span className="text-2xs text-stock ml-auto">★ best</span>}
    </div>
  )
}

function SplitOrderPlan({ plan }) {
  if (!plan?.length) return null
  const total = plan.reduce((s, p) => s + p.subtotal_inr, 0)
  return (
    <div className="mt-3 pt-3 border-t border-border/50">
      <div className="flex items-center gap-1.5 mb-2">
        <Layers size={11} className="text-warn" />
        <span className="eyebrow text-warn">Split order recommended</span>
      </div>
      <div className="space-y-1">
        {plan.map((p, i) => {
          const cfg = getVendorConfig(p.vendor)
          return (
            <div key={i} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5">
                <span className={cx('text-2xs font-mono px-1 py-0.5 rounded border', cfg.badgeClass)}>
                  {cfg.short}
                </span>
                <span className="text-ink-3 font-mono">{p.qty_from_vendor} units</span>
              </div>
              <span className="font-mono text-ink-2">{formatINR(p.subtotal_inr, 2)}</span>
            </div>
          )
        })}
        <div className="flex justify-between text-xs pt-1 border-t border-border/30">
          <span className="text-ink-3">Split total</span>
          <span className="font-mono text-ink font-medium">{formatINR(total, 2)}</span>
        </div>
      </div>
    </div>
  )
}

export default function OptimizationCard({ result }) {
  const {
    component, normalized_mpn, quantity_required,
    best_vendor, best_unit_price_inr, best_total_price_inr,
    availability, all_vendors = [], savings_vs_worst_inr,
    recommendation_reason, split_order,
  } = result

  const bestVendorData = all_vendors.find(v => v.vendor === best_vendor)
  const allOOS = !best_vendor || availability === 'Out of Stock'

  return (
    <div className={cx(
      'card p-4 transition-colors duration-150 animate-slide-up',
      allOOS && 'border-danger/30'
    )}>
      {/* Header row */}
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-0.5">
            <p className="font-mono text-sm font-medium text-ink truncate">{normalized_mpn}</p>
            {normalized_mpn !== component && (
              <span className="text-2xs text-ink-3 font-mono truncate">({component})</span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span className="text-2xs text-ink-3">{quantity_required} units required</span>
            {/* Availability indicator */}
            {allOOS ? (
              <div className="flex items-center gap-1 text-danger">
                <AlertTriangle size={10} />
                <span className="text-2xs">No stock</span>
              </div>
            ) : (
              <div className="flex items-center gap-1 text-stock">
                <CheckCircle2 size={10} />
                <span className="text-2xs">In stock</span>
              </div>
            )}
          </div>
        </div>

        {/* Price block */}
        {!allOOS && best_unit_price_inr != null && (
          <div className="text-right shrink-0">
            <p className="font-mono text-lg font-semibold text-ink leading-tight">
              {formatINR(best_unit_price_inr)}
            </p>
            <p className="text-2xs text-ink-3">
              Total: <span className="text-ink-2 font-mono">{formatINR(best_total_price_inr, 2)}</span>
            </p>
            {savings_vs_worst_inr > 0.5 && (
              <p className="text-2xs text-stock mt-0.5">
                −{formatINR(savings_vs_worst_inr, 2)} vs worst
              </p>
            )}
          </div>
        )}
      </div>

      {/* Stock bar */}
      {bestVendorData && (
        <div className="mb-3">
          <StockBar stock={bestVendorData.stock_qty} required={quantity_required} />
        </div>
      )}

      {/* Vendor price grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
        {all_vendors.map(v => (
          <VendorPricePill
            key={v.vendor}
            vendorResult={v}
            isBest={v.vendor === best_vendor}
          />
        ))}
      </div>

      {/* Split order */}
      {split_order && <SplitOrderPlan plan={split_order} />}

      {/* Recommendation note */}
      {recommendation_reason && (
        <p className="text-2xs text-ink-3 mt-2 pt-2 border-t border-border/30 leading-relaxed">
          {recommendation_reason}
        </p>
      )}
    </div>
  )
}
