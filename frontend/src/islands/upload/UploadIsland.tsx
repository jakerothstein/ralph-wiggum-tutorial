/**
 * UploadIsland — drag/drop + file-input upload of a research-paper PDF.
 *
 * Handles client-side validation (PDF type + size), POSTs to `/api/papers`,
 * surfaces ingest/analysis progress, and on success redirects to the paper
 * workspace (`/papers/<id>`). Keeping validation here gives the user instant
 * feedback; the backend re-validates authoritatively.
 */
import { useCallback, useRef, useState } from 'react'
import type { DragEvent } from 'react'
import { ApiError, uploadPaper } from '@/lib/api'

const MAX_BYTES = 10 * 1024 * 1024

type Status = 'idle' | 'uploading' | 'error'

function validate(file: File): string | null {
  const isPdf =
    file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
  if (!isPdf) return 'Please choose a PDF file.'
  if (file.size > MAX_BYTES) return 'That file is larger than the 10 MB limit.'
  return null
}

export function UploadIsland() {
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(async (file: File) => {
    const validationError = validate(file)
    if (validationError) {
      setStatus('error')
      setError(validationError)
      return
    }
    setStatus('uploading')
    setError(null)
    try {
      const result = await uploadPaper(file)
      window.location.assign(`/papers/${result.paper.id}`)
    } catch (e) {
      setStatus('error')
      setError(
        e instanceof ApiError ? e.message : 'Upload failed. Please try again.',
      )
    }
  }, [])

  const onDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      setDragging(false)
      const file = event.dataTransfer.files?.[0]
      if (file) void handleFile(file)
    },
    [handleFile],
  )

  const busy = status === 'uploading'

  return (
    <div className="w-full">
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload a PDF"
        onClick={() => !busy && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (!busy && (e.key === 'Enter' || e.key === ' ')) {
            inputRef.current?.click()
          }
        }}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={[
          'flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-12 text-center transition-colors cursor-pointer',
          dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white',
          busy ? 'opacity-60 pointer-events-none' : 'hover:border-blue-400',
        ].join(' ')}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) void handleFile(file)
          }}
        />
        {busy ? (
          <p className="text-gray-700" aria-live="polite">
            Uploading &amp; analyzing the paper… this can take a moment.
          </p>
        ) : (
          <>
            <p className="text-lg font-medium text-gray-800">
              Drag &amp; drop a PDF here
            </p>
            <p className="text-sm text-gray-500">or click to choose a file (max 10 MB)</p>
          </>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  )
}
