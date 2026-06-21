/**
 * BomUploader.jsx
 * Accepts drag-drop files (.csv, .xlsx, .txt), paste-to-textarea,
 * shows auto-detected format badge, "Load sample" shortcut.
 */
import { useState, useCallback, useRef } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  Upload, FileText, ClipboardPaste, Cpu, ChevronRight, AlertCircle,
} from 'lucide-react'
import { SAMPLE_BOM, cx } from '../lib/utils.js'

const FORMAT_LABELS = {
  csv:   { label: 'CSV',  color: 'text-trace' },
  tsv:   { label: 'TSV',  color: 'text-purple' },
  xlsx:  { label: 'XLSX', color: 'text-stock' },
  text:  { label: 'TXT',  color: 'text-warn' },
  auto:  { label: 'AUTO', color: 'text-ink-3' },
}

function detectFormat(text) {
  if (!text.trim()) return 'auto'
  const lines = text.trim().split('\n')
  const first = lines[0]
  if (first.includes('\t') && (first.match(/\t/g) || []).length >= 2) return 'tsv'
  if (first.includes(',') && (first.match(/,/g) || []).length >= 2) return 'csv'
  if (first.includes(';') && (first.match(/;/g) || []).length >= 2) return 'csv'
  return 'text'
}

export default function BomUploader({ onSubmit, isBusy }) {
  const [bomText, setBomText]     = useState('')
  const [format, setFormat]       = useState('auto')
  const [filename, setFilename]   = useState(null)
  const [fileError, setFileError] = useState(null)
  const textareaRef = useRef(null)

  const handleTextChange = useCallback((e) => {
    const val = e.target.value
    setBomText(val)
    setFormat(detectFormat(val))
    setFilename(null)
    setFileError(null)
  }, [])

  const loadSample = useCallback(() => {
    setBomText(SAMPLE_BOM)
    setFormat('csv')
    setFilename(null)
    setFileError(null)
    textareaRef.current?.focus()
  }, [])

  const handleSubmit = useCallback(() => {
    if (!bomText.trim() || isBusy) return
    onSubmit(bomText, format)
  }, [bomText, format, isBusy, onSubmit])

  const onDrop = useCallback((acceptedFiles, rejectedFiles) => {
    setFileError(null)
    if (rejectedFiles.length) {
      setFileError('Unsupported file type. Use .csv, .xlsx, or .txt')
      return
    }
    const file = acceptedFiles[0]
    if (!file) return
    setFilename(file.name)

    const ext = file.name.split('.').pop().toLowerCase()
    if (ext === 'xlsx' || ext === 'xls') {
      // Read as base64 for the backend
      const reader = new FileReader()
      reader.onload = (ev) => {
        const b64 = ev.target.result.split(',')[1]
        setBomText(b64)
        setFormat('xlsx_base64')
      }
      reader.readAsDataURL(file)
    } else {
      const reader = new FileReader()
      reader.onload = (ev) => {
        const text = ev.target.result
        setBomText(text)
        setFormat(detectFormat(text))
      }
      reader.readAsText(file)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv':  ['.csv'],
      'text/plain': ['.txt', '.tsv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
    },
    maxFiles: 1,
    noClick: true,
    noKeyboard: true,
  })

  const fmt = FORMAT_LABELS[format] ?? FORMAT_LABELS.auto
  const hasContent = bomText.trim().length > 0

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-8 rounded bg-trace/10 border border-trace/20 flex items-center justify-center">
          <Cpu size={16} className="text-trace" />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-ink tracking-tight">BoM Analyzer</h1>
          <p className="text-xs text-ink-3">Vendor price comparison · Optimised for Indian procurement · All prices in ₹ INR</p>
        </div>
      </div>

      {/* Drop zone wrapper */}
      <div
        {...getRootProps()}
        className={cx(
          'border-2 border-dashed rounded-lg p-6 mb-4 transition-colors duration-150',
          isDragActive
            ? 'border-trace bg-trace/5'
            : 'border-border hover:border-muted'
        )}
      >
        <input {...getInputProps()} />

        {isDragActive ? (
          <div className="text-center py-4">
            <Upload size={28} className="mx-auto text-trace mb-2" />
            <p className="text-sm text-trace font-medium">Drop file to load</p>
          </div>
        ) : (
          <>
            {/* File info or prompt */}
            {filename ? (
              <div className="flex items-center gap-2 mb-3 px-2 py-1.5 bg-elevated rounded border border-border w-fit">
                <FileText size={13} className="text-stock" />
                <span className="text-xs text-ink-2 font-mono">{filename}</span>
                <span className={cx('text-2xs font-mono font-medium ml-1', fmt.color)}>{fmt.label}</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 mb-3 text-ink-3">
                <Upload size={14} />
                <span className="text-xs">Drop a .csv, .xlsx, or .txt file, or paste below</span>
              </div>
            )}

            {/* Textarea */}
            <div className="relative">
              <textarea
                ref={textareaRef}
                value={bomText}
                onChange={handleTextChange}
                placeholder={`Qty,MPN,Description,Manufacturer,Ref\n10,ATmega328P-PU,8-bit AVR MCU,Microchip,U1\n50,GRM188R61A106KE69D,100uF MLCC,Murata,C1-C50\n...`}
                className="field font-mono text-xs w-full h-36 resize-y leading-relaxed"
                spellCheck={false}
              />
              {/* Format badge */}
              {hasContent && (
                <div className="absolute top-2 right-2">
                  <span className={cx('eyebrow text-2xs px-1.5 py-0.5 rounded bg-elevated border border-border', fmt.color)}>
                    {fmt.label}
                  </span>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* File error */}
      {fileError && (
        <div className="flex items-center gap-2 text-danger text-xs mb-3 px-1">
          <AlertCircle size={12} />
          {fileError}
        </div>
      )}

      {/* Actions row */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={handleSubmit}
          disabled={!hasContent || isBusy}
          className={cx('btn btn-primary text-sm px-4 py-2', isBusy && 'opacity-50')}
        >
          {isBusy ? (
            <>
              <span className="w-3 h-3 border border-trace border-t-transparent rounded-full animate-spin" />
              Analyzing…
            </>
          ) : (
            <>
              Analyze BoM
              <ChevronRight size={14} />
            </>
          )}
        </button>

        <button
          onClick={loadSample}
          disabled={isBusy}
          className="btn btn-ghost text-sm"
        >
          <ClipboardPaste size={13} />
          Load sample
        </button>

        {hasContent && !isBusy && (
          <span className="text-xs text-ink-3 ml-1">
            {bomText.trim().split('\n').filter(l => l.trim() && !l.startsWith('#')).length - 1} rows detected
          </span>
        )}
      </div>

      {/* Vendor coverage note */}
      <div className="mt-5 pt-4 border-t border-border/50">
        <p className="eyebrow mb-2">Vendors queried</p>
        <div className="flex flex-wrap gap-1.5">
          {['DigiKey', 'Mouser', 'LCSC', 'Arrow', 'Robu.in', 'Evelta'].map(v => (
            <span key={v} className="text-2xs font-mono px-2 py-0.5 rounded bg-elevated border border-border text-ink-3">
              {v}
            </span>
          ))}
        </div>
        <p className="text-2xs text-ink-3 mt-2">
          Prices scraped live · Cached 4 h per component · USD → INR converted at live rate
        </p>
      </div>
    </div>
  )
}
