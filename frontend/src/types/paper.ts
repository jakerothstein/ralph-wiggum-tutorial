/**
 * Shared DTO types mirroring the backend Pydantic schemas
 * (`src/app/schemas/paper.py` and `schemas/conversation.py`).
 *
 * These are the single source of truth on the frontend for the JSON exchanged
 * with the API. Keep them in sync with the Pydantic models — the backend is
 * authoritative.
 */

export interface ClaimEvidence {
  claim: string
  evidence: string
}

export interface GlossaryItem {
  term: string
  definition: string
}

export interface ComprehensionQuestion {
  question: string
  difficulty: string
  ideal_answer: string
}

export interface PaperAnalysis {
  summary: string
  contributions: string[]
  methodology: string
  key_claims: ClaimEvidence[]
  limitations: string[]
  glossary: GlossaryItem[]
  questions: ComprehensionQuestion[]
}

export interface Paper {
  id: number
  title: string
  filename: string
  num_pages: number
}

export interface UploadResponse {
  paper: Paper
  analysis: PaperAnalysis
}

export interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  cited_chunk_ids: number[]
  comprehension_score: number | null
  score_rationale: string | null
}

export interface Conversation {
  id: number
  paper_id: number
  messages: Message[]
}

export interface SendMessageResponse {
  user: Message
  assistant: Message
}
