/**
 * ChatIsland component tests.
 *
 * Verify the conversation UI contract: it starts a conversation on mount and
 * renders existing history, sending a message appends the user + assistant
 * turns and surfaces the updated comprehension score and citations, and the
 * input is disabled while a reply is pending.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatIsland } from './ChatIsland'
import * as api from '@/lib/api'
import type { Message } from '@/types/paper'

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof api>('@/lib/api')
  return { ...actual, startConversation: vi.fn(), sendMessage: vi.fn() }
})

const startMock = api.startConversation as unknown as ReturnType<typeof vi.fn>
const sendMock = api.sendMessage as unknown as ReturnType<typeof vi.fn>

function assistant(id: number, content: string, score: number): Message {
  return {
    id,
    role: 'assistant',
    content,
    cited_chunk_ids: [7],
    comprehension_score: score,
    score_rationale: 'because',
  }
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('ChatIsland', () => {
  it('starts a conversation and renders prior history', async () => {
    startMock.mockResolvedValue({
      id: 1,
      paper_id: 9,
      messages: [assistant(10, 'Welcome back', 30)],
    })
    render(<ChatIsland paperId={9} />)

    expect(await screen.findByText('Welcome back')).toBeInTheDocument()
    expect(screen.getByTestId('score-value')).toHaveTextContent('30/100')
  })

  it('sends a message and shows the assistant reply, score, and citation', async () => {
    startMock.mockResolvedValue({ id: 1, paper_id: 9, messages: [] })
    sendMock.mockResolvedValue({
      user: {
        id: 11,
        role: 'user',
        content: 'my answer',
        cited_chunk_ids: [],
        comprehension_score: null,
        score_rationale: null,
      },
      assistant: assistant(12, 'Good, but why?', 65),
    })

    render(<ChatIsland paperId={9} />)
    await waitFor(() => expect(startMock).toHaveBeenCalled())

    const input = screen.getByLabelText('Message the tutor')
    fireEvent.change(input, { target: { value: 'my answer' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText('Good, but why?')).toBeInTheDocument()
    expect(screen.getByText('my answer')).toBeInTheDocument()
    expect(screen.getByTestId('score-value')).toHaveTextContent('65/100')
    expect(screen.getByText('source #7')).toBeInTheDocument()
  })

  it('disables the input until the conversation has started', async () => {
    let resolveStart: (v: unknown) => void = () => {}
    startMock.mockImplementation(
      () => new Promise((resolve) => {
        resolveStart = resolve
      }),
    )
    render(<ChatIsland paperId={9} />)

    const input = screen.getByLabelText('Message the tutor') as HTMLInputElement
    expect(input).toBeDisabled()

    resolveStart({ id: 1, paper_id: 9, messages: [] })
    await waitFor(() => expect(input).not.toBeDisabled())
  })
})
