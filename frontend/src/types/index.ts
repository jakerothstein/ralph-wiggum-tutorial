/**
 * Shared TypeScript types for the application.
 *
 * Feature DTOs for the Research Paper Comprehension Tutor live in
 * `frontend/src/types/paper.ts` and mirror the backend Pydantic schemas.
 */

/**
 * Props passed to islands via the `data-props` attribute.
 *
 * Each island receives its initial data from the server (e.g. the analysis and
 * chat islands receive `{ paperId }`). The type is kept generic so future
 * islands can pass typed initial state.
 */
export type IslandProps<T = unknown> = {
  initialData?: T
}
