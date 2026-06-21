/**
 * VendorMatrix.jsx
 * Sticky-first-column table. Each cell is a scope-readout price chip.
 * Click any row to expand inline price-break details.
 */
import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { formatINR, formatQty, priceRank, getVendorConfig, cx } from '../lib/utils.js'

const PRICE_CLASS = {
  best: 'price-best',
  mid:  'price-mid',
  high: 'price-high',
  oos:  'price-oos',
}

function VendorBadge({ name }) {
  const cfg = getVendorConfig(name)
  return (
    <span className={cx('text-2xs font-mono px-1.5 py-0.5 rounded border', cfg.badgeClass)}>
      {cfg.short}
    </span>
  )
}

function PriceCell({ vendor, qty, vendorList }) {
  const prices = vendorList
    .filter(v => v.availability !== 'Out of Stock')
    .map(v => v.unit_price_inr)

  const v = vendorList.find(v => v.vendor === vendor)
  if (!v) return <td className="px-3 py-2 text-center"><span className="price-oos text-2xs px-2 py-1 rounded border">—</span></td>

  if (v.availability === 'Out of Stock') {
    return (
      <td className="px-3 py-2 text-center">
        <span className="price-oos text-2xs font-mono px-2 py-1 rounded border">OOS</span>
      </td>
    )
  }

  const rank = priceRank(v.unit_price_inr, prices)
  const cls = PRICE_CLASS[rank]

  return (
    <td className="px-3 py-2 text-center">
      <span className={cx('text-xs px-2 py-1 rounded border inline-block min-w-[70px]', cls)}>
        {formatINR(v.unit_price_inr)}
      </span>
    </td>
  )
}

function ExpandedDetail({ result, vendors }) {
  return (
    <tr>
      <td colSpan={vendors.length + 4} className="px-0 py-0">
        <div className="bg-canvas border-y border-border/50 px-4 py-3 animate-slide-up">
          <div className="flex gap-6 flex-wrap">
            {result.all_vendors.map(v => {
              if (!v.price_breaks?.length) return null
              const cfg = getVendorConfig(v.vendor)
              return (
                <div key={v.vendor}>
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <span className={cx('text-2xs font-mono px-1.5 py-0.5 rounded border', cfg.badgeClass)}>
                      {cfg.label}
                    </span>
                    <span className="text-2xs text-ink-3 font-mono">{v.vendor_part_number}</span>
                  </div>
                  <div className="space-y-0.5">
                    {v.price_breaks.map((b, i) => (
                      <div key={i} className="flex items-center gap-3 text-xs font-mono">
                        <span className="text-ink-3 w-16 text-right">{formatQty(b.qty)}+</span>
                        <span className="text-ink-2">{formatINR(b.price_inr)}</span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-1.5 text-2xs text-ink-3">
                    Stock: {formatQty(v.stock_qty)}
                    {v.moq > 1 && <> · MOQ: {v.moq}</>}
                    {v.lead_time_weeks && <> · {v.lead_time_weeks}wk lead</>}
                  </div>
                </div>
              )
            })}
            {result.all_vendors.every(v => !v.price_breaks?.length) && (
              <p className="text-xs text-ink-3 italic">No price break data available for this component.</p>
            )}
          </div>
          {result.recommendation_reason && (
            <div className="mt-3 pt-2 border-t border-border/40">
              <p className="text-2xs text-ink-3">
                <span className="text-stock font-medium">Recommendation: </span>
                {result.recommendation_reason}
              </p>
            </div>
          )}
        </div>
      </td>
    </tr>
  )
}

export default function VendorMatrix({ results }) {
  const [expanded, setExpanded] = useState(null)

  if (!results?.length) return null

  // Collect all unique vendors in a stable order
  const vendorOrder = ['DigiKey', 'Mouser', 'LCSC', 'Arrow', 'Robu', 'Evelta']
  const activeVendors = vendorOrder.filter(v =>
    results.some(r => r.all_vendors.some(av => av.vendor === v))
  )

  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="data-table" style={{ minWidth: `${360 + activeVendors.length * 110}px` }}>
          <thead>
            <tr>
              <th className="min-w-[180px] sticky left-0 bg-elevated z-20">Component</th>
              <th className="text-center w-14">Qty</th>
              {activeVendors.map(v => (
                <th key={v} className="text-center">
                  <VendorBadge name={v} />
                </th>
              ))}
              <th>Best</th>
              <th className="text-right">Savings</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => {
              const isExpanded = expanded === r.normalized_mpn
              const worstInStockPrice = Math.max(
                ...r.all_vendors
                  .filter(v => v.availability !== 'Out of Stock')
                  .map(v => v.unit_price_inr),
                0
              )
              return (
                <>
                  <tr
                    key={r.normalized_mpn}
                    className={cx(
                      'cursor-pointer transition-colors duration-100',
                      isExpanded ? 'bg-elevated' : 'hover:bg-elevated/40'
                    )}
                    onClick={() => setExpanded(isExpanded ? null : r.normalized_mpn)}
                  >
                    {/* Component name — sticky */}
                    <td className="sticky left-0 bg-[inherit] z-10 min-w-[180px]">
                      <div className="flex items-center gap-2">
                        <span className={cx(
                          'transition-transform duration-150 text-ink-3',
                          isExpanded ? 'rotate-90' : ''
                        )}>
                          <ChevronRight size={12} />
                        </span>
                        <div>
                          <p className="font-mono text-xs text-ink font-medium">{r.normalized_mpn}</p>
                          {r.normalized_mpn !== r.component && (
                            <p className="text-2xs text-ink-3 font-mono">{r.component}</p>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* Qty */}
                    <td className="text-center font-mono text-xs text-ink-3">{r.quantity_required}</td>

                    {/* Vendor price cells */}
                    {activeVendors.map(v => (
                      <PriceCell
                        key={v}
                        vendor={v}
                        qty={r.quantity_required}
                        vendorList={r.all_vendors}
                      />
                    ))}

                    {/* Best vendor */}
                    <td>
                      {r.best_vendor ? (
                        <div className="flex items-center gap-1.5">
                          <span className={cx(
                            'text-2xs font-mono px-1.5 py-0.5 rounded border',
                            getVendorConfig(r.best_vendor).badgeClass
                          )}>
                            {r.best_vendor}
                          </span>
                          <span className="font-mono text-xs text-ink-2">
                            {formatINR(r.best_unit_price_inr)}
                          </span>
                        </div>
                      ) : (
                        <span className="text-xs text-danger">No stock</span>
                      )}
                    </td>

                    {/* Savings */}
                    <td className="text-right">
                      {r.savings_vs_worst_inr > 0 ? (
                        <span className="font-mono text-xs text-stock">
                          −{formatINR(r.savings_vs_worst_inr, 2)}
                        </span>
                      ) : (
                        <span className="text-xs text-ink-3">—</span>
                      )}
                    </td>
                  </tr>

                  {/* Expanded detail row */}
                  {isExpanded && (
                    <ExpandedDetail
                      key={`${r.normalized_mpn}-detail`}
                      result={r}
                      vendors={activeVendors}
                    />
                  )}
                </>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="px-4 py-2 border-t border-border bg-elevated">
        <p className="text-2xs text-ink-3">
          <span className="price-best text-2xs px-1.5 py-0.5 rounded border mr-1.5">green</span>best price ·
          <span className="price-mid text-2xs px-1.5 py-0.5 rounded border mx-1.5">amber</span>mid ·
          <span className="price-high text-2xs px-1.5 py-0.5 rounded border mx-1.5">red</span>most expensive ·
          <span className="price-oos text-2xs px-1.5 py-0.5 rounded border ml-1.5">OOS</span>out of stock
          · Click row to expand price breaks
        </p>
      </div>
    </div>
  )
}
