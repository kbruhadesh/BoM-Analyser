/**
 * ExportBar.jsx
 * Export buttons: JSON download, Excel (.xlsx), copy summary, share link.
 */
import { useState } from 'react'
import { Download, FileSpreadsheet, Copy, Link2, Check } from 'lucide-react'
import { exportResult, ApiError } from '../lib/api.js'
import { downloadBlob, formatINR } from '../lib/utils.js'

export default function ExportBar({ taskId, summary }) {
  const [copying, setCopying]         = useState(false)
  const [copiedLink, setCopiedLink]   = useState(false)
  const [downloading, setDownloading] = useState(null)   // 'json' | 'excel' | null
  const [exportError, setExportError] = useState(null)

  async function handleExport(format) {
    if (downloading) return
    setExportError(null)
    setDownloading(format)
    try {
      const blob = await exportResult(taskId, format)
      const ext = format === 'excel' ? 'xlsx' : 'json'
      downloadBlob(blob, `bom-analysis-${taskId.slice(0, 8)}.${ext}`)
    } catch (err) {
      setExportError(err instanceof ApiError ? err.message : 'Download failed.')
    } finally {
      setDownloading(null)
    }
  }

  async function handleCopy() {
    const text = JSON.stringify({
      task_id: taskId,
      currency: 'INR',
      summary,
    }, null, 2)
    await navigator.clipboard.writeText(text)
    setCopying(true)
    setTimeout(() => setCopying(false), 1800)
  }

  async function handleShareLink() {
    const url = `${window.location.origin}?task=${taskId}`
    await navigator.clipboard.writeText(url)
    setCopiedLink(true)
    setTimeout(() => setCopiedLink(false), 1800)
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Excel */}
      <button
        onClick={() => handleExport('excel')}
        disabled={!!downloading}
        className="btn btn-success text-sm"
      >
        {downloading === 'excel' ? (
          <span className="w-3 h-3 border border-stock border-t-transparent rounded-full animate-spin" />
        ) : (
          <FileSpreadsheet size={13} />
        )}
        Export Excel ₹
      </button>

      {/* JSON */}
      <button
        onClick={() => handleExport('json')}
        disabled={!!downloading}
        className="btn text-sm"
      >
        {downloading === 'json' ? (
          <span className="w-3 h-3 border border-ink-3 border-t-transparent rounded-full animate-spin" />
        ) : (
          <Download size={13} />
        )}
        Export JSON
      </button>

      {/* Copy summary */}
      <button onClick={handleCopy} className="btn text-sm">
        {copying ? <Check size={13} className="text-stock" /> : <Copy size={13} />}
        {copying ? 'Copied!' : 'Copy summary'}
      </button>

      {/* Share link */}
      <button onClick={handleShareLink} className="btn btn-ghost text-sm">
        {copiedLink ? <Check size={13} className="text-stock" /> : <Link2 size={13} />}
        {copiedLink ? 'Link copied!' : 'Share link'}
      </button>

      {exportError && (
        <p className="text-xs text-danger w-full mt-1">{exportError}</p>
      )}
    </div>
  )
}
