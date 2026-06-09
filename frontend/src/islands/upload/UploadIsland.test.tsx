/**
 * UploadIsland component tests.
 *
 * Cover the behaviour users depend on: client-side validation rejects non-PDFs
 * before any network call, a valid upload calls the API and redirects to the
 * new paper workspace, and a backend error is surfaced to the user.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { UploadIsland } from './UploadIsland'
import * as api from '@/lib/api'

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof api>('@/lib/api')
  return { ...actual, uploadPaper: vi.fn() }
})

const uploadPaperMock = api.uploadPaper as unknown as ReturnType<typeof vi.fn>

function pdfFile(name = 'paper.pdf'): File {
  return new File(['%PDF-1.4 fake'], name, { type: 'application/pdf' })
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('UploadIsland', () => {
  it('rejects a non-PDF file without calling the API', async () => {
    render(<UploadIsland />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const txt = new File(['hello'], 'note.txt', { type: 'text/plain' })
    fireEvent.change(input, { target: { files: [txt] } })

    expect(await screen.findByRole('alert')).toHaveTextContent(/PDF/i)
    expect(uploadPaperMock).not.toHaveBeenCalled()
  })

  it('uploads a valid PDF and redirects to the paper workspace', async () => {
    const assign = vi.fn()
    Object.defineProperty(window, 'location', {
      value: { assign },
      writable: true,
    })
    uploadPaperMock.mockResolvedValue({
      paper: { id: 42, title: 'T', filename: 'paper.pdf', num_pages: 1 },
      analysis: {
        summary: 's',
        contributions: [],
        methodology: '',
        key_claims: [],
        limitations: [],
        glossary: [],
        questions: [],
      },
    })

    render(<UploadIsland />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [pdfFile()] } })

    await waitFor(() => expect(uploadPaperMock).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(assign).toHaveBeenCalledWith('/papers/42'))
  })

  it('shows an error when the upload fails', async () => {
    uploadPaperMock.mockRejectedValue(new api.ApiError('No extractable text.', 400))
    render(<UploadIsland />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [pdfFile()] } })

    expect(await screen.findByRole('alert')).toHaveTextContent('No extractable text.')
  })
})
