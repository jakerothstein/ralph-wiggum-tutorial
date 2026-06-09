/**
 * AnalysisIsland — read-only render of the structured upfront analysis.
 *
 * Fetches `/api/papers/<id>` on mount and renders the sections the analyzer
 * produced: summary, contributions, methodology, key claims + evidence,
 * limitations, glossary, and the graded comprehension questions. This gives the
 * reader an immediate map of the paper before the Socratic conversation begins.
 */
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { ApiError, getAnalysis } from '@/lib/api'
import type { PaperAnalysis } from '@/types/paper'

interface Props {
  paperId: number
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mb-6">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
        {title}
      </h3>
      {children}
    </section>
  )
}

export function AnalysisIsland({ paperId }: Props) {
  const [analysis, setAnalysis] = useState<PaperAnalysis | null>(null)
  const [title, setTitle] = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    getAnalysis(paperId)
      .then((data) => {
        if (!active) return
        setAnalysis(data.analysis)
        setTitle(data.paper.title)
      })
      .catch((e) => {
        if (!active) return
        setError(e instanceof ApiError ? e.message : 'Failed to load analysis.')
      })
    return () => {
      active = false
    }
  }, [paperId])

  if (error) {
    return (
      <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
        {error}
      </p>
    )
  }
  if (!analysis) {
    return <p className="text-gray-500">Loading analysis…</p>
  }

  return (
    <div className="text-gray-800">
      <h2 className="mb-4 text-xl font-bold text-gray-900">Paper Analysis</h2>

      <Section title="Summary">
        <p className="text-sm leading-relaxed">{analysis.summary}</p>
      </Section>

      {analysis.contributions.length > 0 && (
        <Section title="Contributions">
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {analysis.contributions.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </Section>
      )}

      {analysis.methodology && (
        <Section title="Methodology">
          <p className="text-sm leading-relaxed">{analysis.methodology}</p>
        </Section>
      )}

      {analysis.key_claims.length > 0 && (
        <Section title="Key Claims">
          <ul className="space-y-2 text-sm">
            {analysis.key_claims.map((c, i) => (
              <li key={i}>
                <span className="font-medium">{c.claim}</span>
                {c.evidence && (
                  <span className="text-gray-500"> — {c.evidence}</span>
                )}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {analysis.limitations.length > 0 && (
        <Section title="Limitations">
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {analysis.limitations.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </Section>
      )}

      {analysis.glossary.length > 0 && (
        <Section title="Glossary">
          <dl className="space-y-1 text-sm">
            {analysis.glossary.map((g, i) => (
              <div key={i}>
                <dt className="inline font-medium">{g.term}: </dt>
                <dd className="inline text-gray-600">{g.definition}</dd>
              </div>
            ))}
          </dl>
        </Section>
      )}

      {analysis.questions.length > 0 && (
        <Section title="Comprehension Questions">
          <ul className="space-y-1 text-sm">
            {analysis.questions.map((q, i) => (
              <li key={i} className="flex gap-2">
                <span className="rounded bg-gray-100 px-1.5 text-xs uppercase text-gray-500">
                  {q.difficulty}
                </span>
                <span>{q.question}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <p className="sr-only">{title}</p>
    </div>
  )
}
