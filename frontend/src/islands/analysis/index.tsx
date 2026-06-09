/**
 * Analysis island mount logic. Dynamically imported by `main.ts` for
 * `[data-island="analysis"]`. Expects a `{ paperId }` prop from `data-props`.
 */
import { createRoot } from 'react-dom/client'
import { AnalysisIsland } from './AnalysisIsland'

interface AnalysisProps {
  paperId: number
}

export function mount(element: HTMLElement, props: unknown): void {
  const { paperId } = (props ?? {}) as AnalysisProps
  element.innerHTML = ''
  createRoot(element).render(<AnalysisIsland paperId={paperId} />)
}
