import { useState } from 'react'
import { Loader2, X } from 'lucide-react'
import { appsApi, type DeployedApp } from '../../api/apps'
import { CATEGORY_LABEL, errorDetail } from './appStoreMeta'

const inputCls = 'w-full px-3 py-2 bg-surface-primary border border-border rounded-lg text-sm text-content-primary focus:outline-none focus:border-accent-primary'

/** App Store 등록(공개) / 목록 정보 수정 대화상자. 등록하면 로그인 없이 누구나 이 앱에 접속할 수 있다. */
export default function PublishDialog({ app, onClose, onDone }: { app: DeployedApp; onClose: () => void; onDone: (a: DeployedApp) => void }) {
  const editing = app.visibility === 'public'
  const [title, setTitle] = useState(app.title ?? app.name)
  const [description, setDescription] = useState(app.description ?? '')
  const [category, setCategory] = useState(app.category ?? 'other')
  const [tags, setTags] = useState((app.tags ?? []).join(', '))
  const [terms, setTerms] = useState(editing)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const submit = async () => {
    setBusy(true)
    setErr(null)
    const data = { title: title.trim(), description: description.trim(), category, tags: tags.split(',').map((t) => t.trim()).filter(Boolean), accept_terms: terms }
    try {
      const r = editing ? await appsApi.updateListing(app.id, data) : await appsApi.publish(app.id, data)
      onDone(r.data)
      onClose()
    } catch (e) {
      setErr(errorDetail(e, '등록하지 못했습니다'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="w-full max-w-lg bg-surface-secondary border border-border rounded-xl p-5 space-y-3 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center">
          <h3 className="flex-1 text-[16px] font-semibold text-content-primary">{editing ? '스토어 정보 수정' : 'App Store에 등록'}</h3>
          <button onClick={onClose} aria-label="닫기" className="p-1 text-content-muted hover:text-content-primary border-none bg-transparent cursor-pointer"><X size={16} /></button>
        </div>
        <input autoFocus className={inputCls} placeholder="제목" maxLength={100} value={title} onChange={(e) => setTitle(e.target.value)} />
        <textarea className={`${inputCls} resize-none`} rows={4} maxLength={2000} placeholder="앱 설명" value={description} onChange={(e) => setDescription(e.target.value)} />
        <div className="grid grid-cols-2 gap-2">
          <label className="text-xs text-content-muted">카테고리
            <select className={`${inputCls} mt-1`} value={category} onChange={(e) => setCategory(e.target.value)}>
              {Object.entries(CATEGORY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label className="text-xs text-content-muted">태그 (쉼표로 구분)
            <input className={`${inputCls} mt-1`} value={tags} onChange={(e) => setTags(e.target.value)} placeholder="예: 메모, 할 일" />
          </label>
        </div>
        {!editing && (
          <>
            <div className="rounded-lg bg-accent-amber/10 border border-accent-amber/30 p-3 text-xs text-content-secondary space-y-1">
              <p className="font-medium text-content-primary">공개하기 전에 확인하세요</p>
              <p>· 등록하면 <b>로그인 없이 누구나</b> 이 앱에 접속할 수 있습니다.</p>
              <p>· 앱의 데이터 폴더(<code>$DATA_DIR</code>)는 방문자 모두가 함께 씁니다. 방문자별 구분이나 로그인은 앱이 직접 처리해야 합니다.</p>
              <p>· 등록 전에 비밀 파일(<code>.env</code>, 키)과 API 키 패턴을 자동으로 점검하며, 걸리면 등록되지 않습니다.</p>
              <p>· {app.kind === 'server' ? '서버형 앱은 관리자 승인 후에 공개됩니다.' : '정적 앱은 점검을 통과하면 바로 공개됩니다.'}</p>
              <p>· 신고가 누적되거나 부적절한 앱은 정지될 수 있으며, 새 버전을 배포하면 다시 점검합니다.</p>
            </div>
            <label className="flex items-start gap-2 text-[13px] text-content-secondary cursor-pointer">
              <input type="checkbox" className="mt-0.5" checked={terms} onChange={(e) => setTerms(e.target.checked)} />
              <span>위 내용을 확인했고, 비밀 정보와 개인정보가 앱에 없음을 확인했습니다.</span>
            </label>
          </>
        )}
        {err && <p className="text-xs text-accent-red whitespace-pre-wrap">{err}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <button onClick={onClose} className="px-3 py-2 rounded-lg text-sm text-content-muted hover:text-content-primary border-none bg-transparent cursor-pointer">취소</button>
          <button onClick={submit} disabled={busy || !title.trim() || !terms} className="flex items-center gap-1 px-4 py-2 rounded-lg text-sm bg-accent-primary text-white disabled:opacity-50 border-none cursor-pointer">
            {busy && <Loader2 size={14} className="animate-spin" />} {editing ? '저장' : '등록'}
          </button>
        </div>
      </div>
    </div>
  )
}
