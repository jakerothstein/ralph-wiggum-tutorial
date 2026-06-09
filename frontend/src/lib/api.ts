/**
 * Typed `fetch` helpers for the tutor backend.
 *
 * One thin module so islands never hand-roll fetch calls or URL strings.
 * Errors are normalized: any non-2xx response throws an `ApiError` carrying the
 * backend's `{error}` message so islands can render it directly.
 */
import type {
  Conversation,
  SendMessageResponse,
  UploadResponse,
} from '@/types/paper'

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function parseError(response: Response): Promise<never> {
  let message = `Request failed (${response.status})`
  try {
    const body = await response.json()
    if (body && typeof body.error === 'string') message = body.error
  } catch {
    // Non-JSON error body; keep the default message.
  }
  throw new ApiError(message, response.status)
}

export async function uploadPaper(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch('/api/papers', { method: 'POST', body: form })
  if (!response.ok) return parseError(response)
  return (await response.json()) as UploadResponse
}

export async function getAnalysis(paperId: number): Promise<UploadResponse> {
  const response = await fetch(`/api/papers/${paperId}`)
  if (!response.ok) return parseError(response)
  return (await response.json()) as UploadResponse
}

export async function startConversation(
  paperId: number,
): Promise<Conversation> {
  const response = await fetch(`/api/papers/${paperId}/conversation`, {
    method: 'POST',
  })
  if (!response.ok) return parseError(response)
  return (await response.json()) as Conversation
}

export async function sendMessage(
  conversationId: number,
  message: string,
): Promise<SendMessageResponse> {
  const response = await fetch(
    `/api/conversations/${conversationId}/messages`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    },
  )
  if (!response.ok) return parseError(response)
  return (await response.json()) as SendMessageResponse
}
