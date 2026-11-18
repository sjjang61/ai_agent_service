import { useEffect, useRef, useState } from 'react'
import { Folder, HardDrive, Loader2, Upload, X } from 'lucide-react'
import { driveError, type DriveNode } from '../../api/drive'
import { functionsApi, uploadPackageToDrive, type FnSummary } from '../../api/functions'
import DriveFilePickerDialog from '../drive/DriveFilePickerDialog'

const NAME_RE = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/

type Source = { kind: 'drive'; node: DriveNode } | { kind: 'local'; file: File }

export const PACKAGE_GUIDE = `my-func.zip
├── function.json   { "runtime": "python3.12", "handler": "main.handler" }
└── main.py         def handler(event, context): return {"ok": True}

runtime: python3.12 | bun        handler: 파일.함수
timeout_seconds / memory_mb / env 는 선택 (비밀값은 시크릿으로 등록)
의존성은 zip 안에 함께 넣으세요. 네트워크는 차단됩니다.`

/** 새 함수 등록: 이름·설명·패키지(zip). 패키지는 Drive 에서 고르거나 내 컴퓨터에서 올린다(올리면 Drive 의 /Functions 에 저장된다). */
export default function CreateFunctionDialog({ onCreated, onClose }: { onCreated: (fn: FnSummary) => void; onClose: () => void }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [source, setSource] = useState<Source | null>(null)
  const [picking, setPicking] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && !picking && !busy && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, picking, busy])

  const nameOk = NAME_RE.test(name)
  const canSubmit = nameOk && !!source && !busy

  const submit = async () => {
    if (!source) return
    setError(null)
    try {
      let nodeId: string
      if (source.kind === 'local') {
        setBusy('패키지를 Drive 에 올리는 중...')
        nodeId = await uploadPackageToDrive(source.file, () => undefined)
      } else nodeId = source.node.id
      setBusy('함수를 등록하는 중...')
      onCreated(await functionsApi.create(name, description, nodeId))
    } catch (e) {
      setError(e instanceof Error && !('response' in e) ? e.message : driveError(e, '함수를 등록하지 못했습니다'))
      setBusy(null)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-[8vh] px-4" onMouseDown={() => !busy && onClose()}>
      <div role="dialog" aria-label="새 함수" onMouseDown={(e) => e.stopPropagation()} className="w-full max-w-lg rounded-xl border border-border bg-surface-primary shadow-xl">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
          <h2 className="flex-1 m-0 text-sm font-semibold text-content-primary">새 함수</h2>
          <button onClick={onClose} disabled={!!busy} aria-label="닫기" className="p-1 border-none bg-transparent text-content-muted hover:text-content-primary cursor-pointer"><X size={15} /></button>
        </div>
        <div className="p-4 space-y-3 text-xs">
          <label className="block">
            <span className="text-content-secondary">이름</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="daily-report" autoFocus aria-invalid={name !== '' && !nameOk}
              className="mt-1 w-full px-2.5 py-2 rounded-lg border border-border bg-surface-secondary text-sm text-content-primary" />
            {name !== '' && !nameOk && <span className="block mt-1 text-accent-red">영문·숫자로 시작하는 64자 이하의 영문·숫자·_·- 만 쓸 수 있습니다</span>}
          </label>
          <label className="block">
            <span className="text-content-secondary">설명 (선택)</span>
            <input value={description} onChange={(e) => setDescription(e.target.value)} maxLength={500} className="mt-1 w-full px-2.5 py-2 rounded-lg border border-border bg-surface-secondary text-sm text-content-primary" />
          </label>
          <div>
            <span className="text-content-secondary">패키지 (zip)</span>
            <div className="mt-1 flex items-center gap-2">
              <button onClick={() => setPicking(true)} className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-border bg-surface-secondary text-content-primary hover:bg-surface-hover cursor-pointer"><HardDrive size={13} /> Drive 에서 선택</button>
              <button onClick={() => fileInput.current?.click()} className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-border bg-surface-secondary text-content-primary hover:bg-surface-hover cursor-pointer"><Upload size={13} /> 내 컴퓨터에서 올리기</button>
              <input ref={fileInput} type="file" accept=".zip,application/zip" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) setSource({ kind: 'local', file: f }); e.target.value = '' }} />
            </div>
            <div className="mt-2 flex items-center gap-1.5 text-content-secondary min-h-[20px]" aria-live="polite">
              {source ? <><Folder size={13} className="text-accent-blue flex-shrink-0" /><span className="truncate" title={source.kind === 'drive' ? source.node.name : source.file.name}>{source.kind === 'drive' ? source.node.name : source.file.name}</span>
                <span className="text-content-tertiary">{source.kind === 'drive' ? '(Drive)' : '(올리면 Drive 의 /Functions 에 저장됩니다)'}</span></> : <span className="text-content-muted">선택한 파일이 없습니다</span>}
            </div>
          </div>
          <details className="rounded-lg border border-border">
            <summary className="px-3 py-2 cursor-pointer text-content-secondary">패키지 구성 안내</summary>
            <pre className="m-0 px-3 pb-3 text-[11px] leading-relaxed text-content-secondary font-mono whitespace-pre-wrap">{PACKAGE_GUIDE}</pre>
          </details>
          {error && <p role="alert" className="m-0 text-accent-red whitespace-pre-wrap">{error}</p>}
        </div>
        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-border">
          {busy && <span className="flex-1 flex items-center gap-1.5 text-xs text-content-secondary"><Loader2 size={13} className="animate-spin" /> {busy}</span>}
          <button onClick={onClose} disabled={!!busy} className="px-3 py-1.5 rounded-lg text-sm border border-border bg-transparent text-content-secondary hover:bg-surface-hover cursor-pointer disabled:opacity-50">취소</button>
          <button onClick={submit} disabled={!canSubmit} className="px-3 py-1.5 rounded-lg text-sm border-none bg-accent-primary text-white cursor-pointer disabled:opacity-50">등록</button>
        </div>
      </div>
      {picking && <DriveFilePickerDialog title="패키지(zip) 선택" confirmLabel="선택" extensions={['zip']} maxSelect={1} onPick={(nodes) => { setPicking(false); if (nodes[0]) setSource({ kind: 'drive', node: nodes[0] }) }} onClose={() => setPicking(false)} />}
    </div>
  )
}
