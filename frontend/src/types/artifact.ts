export type ArtifactKind = 'image' | 'text' | 'pdf' | 'office' | 'archive' | 'other'

export interface Artifact {
  path: string
  name: string
  size: number
  modified: string
  kind: ArtifactKind
  mime: string | null
}

export interface ArtifactList {
  status: string
  files: Artifact[]
  truncated: boolean
  restorable: boolean
}

export type ArtifactPreview =
  | { kind: 'text'; content: string; size: number; truncated: boolean }
  | { kind: 'image' | 'binary' | 'too_large' }
