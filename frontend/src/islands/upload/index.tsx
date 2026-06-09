/**
 * Upload island mount logic. Dynamically imported by `main.ts` for
 * `[data-island="upload"]`. No server props are needed.
 */
import { createRoot } from 'react-dom/client'
import { UploadIsland } from './UploadIsland'

export function mount(element: HTMLElement, _props: unknown): void {
  element.innerHTML = ''
  createRoot(element).render(<UploadIsland />)
}
