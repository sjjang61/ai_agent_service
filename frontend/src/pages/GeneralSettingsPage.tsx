import { useMemo } from 'react'
import SettingsPage from '../components/skills/SettingsPage'
import { T } from '../components/skills/typography'
import { inputCls } from '../components/skills/common'
import { allTimezones } from '../components/schedules/scheduleUtils'
import { formatFullDateTime } from '../utils/time'
import { DEFAULT_TIMEZONE, useSettingsStore } from '../store/settingsStore'

const PRESETS = [
  { value: 'Asia/Seoul', label: '한국 표준시 (KST, UTC+9)' },
  { value: 'UTC', label: '협정 세계시 (UTC)' },
  { value: 'Asia/Tokyo', label: '일본 (JST, UTC+9)' },
  { value: 'America/Los_Angeles', label: '미국 서부 (PT)' },
  { value: 'America/New_York', label: '미국 동부 (ET)' },
  { value: 'Europe/London', label: '영국 (GMT/BST)' },
]

export default function GeneralSettingsPage() {
  const { timezone, setTimezone } = useSettingsStore()
  const options = useMemo(() => {
    const presetValues = new Set(PRESETS.map((p) => p.value))
    return { presets: PRESETS, others: allTimezones().filter((z) => !presetValues.has(z)) }
  }, [])

  return (
    <SettingsPage active="etc" title="기타 설정" subtitle="화면 표시와 관련된 기본 설정입니다.">
      <div className="space-y-6 max-w-[720px]">
        <section className="space-y-2">
          <h2 className={T.section}>시간대</h2>
          <p className={T.itemDesc}>
            메시지와 목록의 시각을 이 시간대로 표시합니다. 서버는 시각을 UTC 로 저장하고, 화면에서만 변환합니다. 기본값은 한국 표준시(KST)입니다.
          </p>
          <select value={timezone} onChange={(e) => setTimezone(e.target.value)} aria-label="시간대" className={inputCls}>
            <optgroup label="자주 쓰는 시간대">
              {options.presets.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </optgroup>
            <optgroup label="전체">
              {options.others.map((z) => (
                <option key={z} value={z}>{z}</option>
              ))}
            </optgroup>
          </select>
          <div className={T.meta}>현재 시각: {formatFullDateTime(new Date().toISOString())}</div>
          {timezone !== DEFAULT_TIMEZONE && (
            <button
              onClick={() => setTimezone(DEFAULT_TIMEZONE)}
              className="text-[13px] text-accent-primary bg-transparent border-none cursor-pointer p-0"
            >
              기본값(KST)으로 되돌리기
            </button>
          )}
          <p className={T.meta}>이 설정은 이 브라우저에 저장됩니다. 새 예약 작업의 기본 시간대와 에이전트가 쓰는 현재 시각에도 같이 적용됩니다.</p>
        </section>
      </div>
    </SettingsPage>
  )
}
