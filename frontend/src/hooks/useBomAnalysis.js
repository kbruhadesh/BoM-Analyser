/**
 * useBomAnalysis.js
 * Central hook managing the full BoM analysis lifecycle:
 *   idle → submitting → polling → complete | failed
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { analyzeBom, getTaskStatus, getTaskResult, ApiError } from '../lib/api.js'

const POLL_INTERVAL_MS = 1200

export const STATES = {
  IDLE:       'idle',
  SUBMITTING: 'submitting',
  POLLING:    'polling',
  COMPLETE:   'complete',
  FAILED:     'failed',
}

export function useBomAnalysis() {
  const [state, setState]               = useState(STATES.IDLE)
  const [taskId, setTaskId]             = useState(null)
  const [progress, setProgress]         = useState(0)
  const [currentComponent, setCurrent]  = useState(null)
  const [result, setResult]             = useState(null)
  const [error, setError]               = useState(null)
  const [fxRate, setFxRate]             = useState(null)

  const pollRef   = useRef(null)
  const abortRef  = useRef(false)

  const stopPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = null
  }, [])

  const reset = useCallback(() => {
    stopPolling()
    abortRef.current = true
    setState(STATES.IDLE)
    setTaskId(null)
    setProgress(0)
    setCurrent(null)
    setResult(null)
    setError(null)
    // allow new submissions
    setTimeout(() => { abortRef.current = false }, 50)
  }, [stopPolling])

  /** Submit BoM text, kick off polling */
  const submit = useCallback(async (bomText, format = 'auto') => {
    abortRef.current = false
    setError(null)
    setResult(null)
    setProgress(0)
    setCurrent(null)
    setState(STATES.SUBMITTING)

    try {
      const { task_id } = await analyzeBom(bomText, format)
      if (abortRef.current) return
      setTaskId(task_id)
      setState(STATES.POLLING)
    } catch (err) {
      if (abortRef.current) return
      setError(err instanceof ApiError ? err.message : String(err))
      setState(STATES.FAILED)
    }
  }, [])

  /** Poll loop triggered when taskId changes */
  useEffect(() => {
    if (state !== STATES.POLLING || !taskId) return

    const poll = async () => {
      if (abortRef.current) return
      try {
        const status = await getTaskStatus(taskId)
        if (abortRef.current) return

        setProgress(status.progress ?? 0)
        setCurrent(status.current_component ?? null)

        if (status.status === 'complete') {
          stopPolling()
          const data = await getTaskResult(taskId)
          if (abortRef.current) return
          setResult(data)
          setFxRate(data.summary?.usd_inr_rate ?? null)
          setState(STATES.COMPLETE)
        } else if (status.status === 'failed') {
          stopPolling()
          setError(status.error_message ?? 'Analysis failed.')
          setState(STATES.FAILED)
        }
      } catch (err) {
        if (abortRef.current) return
        stopPolling()
        setError(err instanceof ApiError ? err.message : 'Connection error.')
        setState(STATES.FAILED)
      }
    }

    poll()
    pollRef.current = setInterval(poll, POLL_INTERVAL_MS)
    return () => stopPolling()
  }, [taskId, state, stopPolling])

  return {
    state,
    taskId,
    progress,
    currentComponent,
    result,
    error,
    fxRate,
    submit,
    reset,
    isIdle:       state === STATES.IDLE,
    isSubmitting: state === STATES.SUBMITTING,
    isPolling:    state === STATES.POLLING,
    isComplete:   state === STATES.COMPLETE,
    isFailed:     state === STATES.FAILED,
    isBusy:       state === STATES.SUBMITTING || state === STATES.POLLING,
  }
}
