import { File, FileArchive, FileCode, FileImage, FileSpreadsheet, FileText, FileVideo, Folder } from 'lucide-react'
import type { DriveNode } from '../../api/drive'

const EXT: Record<string, 'image' | 'video' | 'archive' | 'code' | 'sheet' | 'text'> = {
  png: 'image', jpg: 'image', jpeg: 'image', gif: 'image', webp: 'image', svg: 'image', bmp: 'image',
  mp4: 'video', mov: 'video', webm: 'video', m4v: 'video',
  zip: 'archive', tar: 'archive', gz: 'archive', tgz: 'archive', '7z': 'archive', rar: 'archive',
  py: 'code', js: 'code', ts: 'code', tsx: 'code', jsx: 'code', html: 'code', css: 'code', json: 'code', sh: 'code', yml: 'code', yaml: 'code', sql: 'code',
  csv: 'sheet', xlsx: 'sheet', xls: 'sheet', tsv: 'sheet',
  txt: 'text', md: 'text', pdf: 'text', doc: 'text', docx: 'text', ppt: 'text', pptx: 'text', hwp: 'text', hwpx: 'text',
}

export function NodeIcon({ node, size = 16 }: { node: Pick<DriveNode, 'type' | 'name'>; size?: number }) {
  if (node.type === 'folder') return <Folder size={size} className="text-accent-blue flex-shrink-0" aria-hidden />
  const kind = EXT[node.name.split('.').pop()?.toLowerCase() ?? '']
  const cls = 'text-content-tertiary flex-shrink-0'
  switch (kind) {
    case 'image': return <FileImage size={size} className={cls} aria-hidden />
    case 'video': return <FileVideo size={size} className={cls} aria-hidden />
    case 'archive': return <FileArchive size={size} className={cls} aria-hidden />
    case 'code': return <FileCode size={size} className={cls} aria-hidden />
    case 'sheet': return <FileSpreadsheet size={size} className={cls} aria-hidden />
    case 'text': return <FileText size={size} className={cls} aria-hidden />
    default: return <File size={size} className={cls} aria-hidden />
  }
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return n < 10240 ? `${(n / 1024).toFixed(1)} KB` : `${Math.round(n / 1024)} KB`
  if (n < 1024 ** 3) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${(n / 1024 ** 3).toFixed(1)} GB`
}

/** Drive 경로: 현재 폴더 경로('/' 또는 '/보고서')와 이름을 잇는다 */
export function joinPath(folderPath: string, name: string): string {
  return `${folderPath === '/' ? '' : folderPath}/${name}`
}
