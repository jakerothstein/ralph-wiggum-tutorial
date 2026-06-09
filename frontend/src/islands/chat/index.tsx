/**
 * Chat island mount logic. Dynamically imported by `main.ts` for
 * `[data-island="chat"]`. Expects a `{ paperId }` prop from `data-props`.
 */
import { createRoot } from 'react-dom/client'
import { ChatIsland } from './ChatIsland'

interface ChatProps {
  paperId: number
}

export function mount(element: HTMLElement, props: unknown): void {
  const { paperId } = (props ?? {}) as ChatProps
  element.innerHTML = ''
  createRoot(element).render(<ChatIsland paperId={paperId} />)
}
