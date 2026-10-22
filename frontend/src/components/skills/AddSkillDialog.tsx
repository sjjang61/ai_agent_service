import { useRef, useState } from 'react'
import { FileUp, Loader2 } from 'lucide-react'
import type { SkillCreateInput } from '../../types/skill'
import { Modal, errorText, inputCls, primaryBtn } from './common'

const TEMPLATE = `## 사용 시점
- 이 skill 을 언제 사용해야 하는지 적습니다.

## 절차
1. 첫 번째 단계
2. 두 번째 단계
`

/** 직접 작성 다이얼로그. SKILL.md 파일을 불러오면 frontmatter(name/description)를 읽어 폼을 채운다. */
export default function AddSkillDialog({ onCreate, onClose }: { onCreate: (i: SkillCreateInput) => Promise<void>; onClose: () => void }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [content, setContent] = useState(TEMPLATE)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const loadFile = async (f: File) => {
    if (f.size > 200 * 1024) return setError('SKILL.md 는 200KB 이하여야 합니다')
    const text = await f.text()
    const m = text.match(/^---\s*\n([\s\S]*?)\n---\s*(\n|$)/)
    if (m) {
      const get = (k: string) => m[1].match(new RegExp(`^${k}:\\s*(.*)$`, 'm'))?.[1].trim().replace(/^["']|["']$/g, '') ?? ''
      setName(get('name') || name)
      setDescription(get('description') || description)
    }
    setContent(text) // frontmatter 포함 전체를 그대로 사용
    setError(null)
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onCreate({ name: name.trim(), description: description.trim(), content })
      onClose()
    } catch (err) {
      setError(errorText(err, 'skill 을 만들지 못했습니다'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="스킬 직접 추가" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <div className="flex justify-end">
          <button type="button" onClick={() => fileRef.current?.click()} className="flex items-center gap-1.5 text-[13px] text-accent-primary hover:underline border-none bg-transparent cursor-pointer">
            <FileUp size={14} /> SKILL.md 파일 불러오기
          </button>
          <input ref={fileRef} type="file" accept=".md,text/markdown,text/plain" hidden onChange={(e) => e.target.files?.[0] && loadFile(e.target.files[0])} />
        </div>
        <div className="space-y-1.5">
          <label className="block text-[13px] font-medium text-content-primary">이름</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="my-skill (영문 소문자, 숫자, -, _)" className={inputCls} />
        </div>
        <div className="space-y-1.5">
          <label className="block text-[13px] font-medium text-content-primary">설명</label>
          <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="언제 이 skill 을 써야 하는지 한 줄로" className={inputCls} />
        </div>
        <div className="space-y-1.5">
          <label className="block text-[13px] font-medium text-content-primary">SKILL.md 내용</label>
          <textarea value={content} onChange={(e) => setContent(e.target.value)} rows={10} className={`${inputCls} font-mono resize-y`} />
          <p className="text-xs text-content-tertiary">---로 시작하는 frontmatter 가 있으면 그대로 저장하고, 없으면 위의 이름·설명으로 자동 생성합니다.</p>
        </div>
        {error && <p className="text-[13px] text-accent-red">{error}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="px-4 py-2.5 text-[13px] text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer">취소</button>
          <button type="submit" disabled={busy || !name.trim() || !content.trim()} className={primaryBtn}>
            {busy && <Loader2 size={14} className="animate-spin" />}
            추가
          </button>
        </div>
      </form>
    </Modal>
  )
}
