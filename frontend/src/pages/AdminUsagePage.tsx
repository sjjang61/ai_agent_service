import { useEffect, useState } from 'react'
import { Database, BarChart3, Users, Cpu, DollarSign } from 'lucide-react'
import SettingsPage from '../components/skills/SettingsPage'
import { T } from '../components/skills/typography'
import { adminApi } from '../api/admin'
import type { UsageSummary, DailyUsage, UserUsage, ModelUsage } from '../types/admin'
import { formatUsd } from '../utils/time'

type TimeRange = 'daily' | 'weekly' | 'monthly'

export default function AdminUsagePage() {
  const [summary, setSummary] = useState<UsageSummary | null>(null)
  const [usageData, setUsageData] = useState<DailyUsage[]>([])
  const [userUsage, setUserUsage] = useState<UserUsage[]>([])
  const [modelUsage, setModelUsage] = useState<ModelUsage[]>([])
  const [timeRange, setTimeRange] = useState<TimeRange>('daily')
  const [days, setDays] = useState(30)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [timeRange, days])

  const loadData = async () => {
    setLoading(true)
    try {
      const [summaryRes, usageRes, usersRes, modelsRes] = await Promise.all([
        adminApi.getUsageSummary(),
        timeRange === 'daily'
          ? adminApi.getDailyUsage(days)
          : timeRange === 'weekly'
            ? adminApi.getWeeklyUsage(Math.ceil(days / 7))
            : adminApi.getMonthlyUsage(Math.ceil(days / 30)),
        adminApi.getUserBreakdown(days),
        adminApi.getModelBreakdown(days),
      ])
      setSummary(summaryRes.data)
      setUsageData(usageRes.data)
      setUserUsage(usersRes.data)
      setModelUsage(modelsRes.data)
    } catch (error) {
      console.error('Failed to load usage data:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatNumber = (n: number) => n.toLocaleString()

  const maxTokens = Math.max(...usageData.map((d) => d.total_tokens), 1)

  return (
    <SettingsPage active="usage" title="토큰 사용량" subtitle="LLM 호출에 쓴 토큰을 기간·사용자·모델별로 확인합니다.">
      <div>
        {loading ? (
          <div className="flex items-center justify-center h-64 text-content-muted">
            Loading...
          </div>
        ) : (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
              <div className="bg-surface-secondary rounded-lg p-4 border border-border">
                <div className="flex items-center gap-2 text-content-muted mb-2">
                  <Database size={18} />
                  <span className="text-sm">Total Tokens</span>
                </div>
                <p className="text-2xl font-bold text-content-primary">
                  {summary ? formatNumber(summary.total_tokens) : '-'}
                </p>
              </div>
              <div className="bg-surface-secondary rounded-lg p-4 border border-border">
                <div className="flex items-center gap-2 text-content-muted mb-2">
                  <BarChart3 size={18} />
                  <span className="text-sm">Input Tokens</span>
                </div>
                <p className="text-2xl font-bold text-accent-green">
                  {summary ? formatNumber(summary.total_input_tokens) : '-'}
                </p>
              </div>
              <div className="bg-surface-secondary rounded-lg p-4 border border-border">
                <div className="flex items-center gap-2 text-content-muted mb-2">
                  <BarChart3 size={18} />
                  <span className="text-sm">Output Tokens</span>
                </div>
                <p className="text-2xl font-bold text-accent-blue">
                  {summary ? formatNumber(summary.total_output_tokens) : '-'}
                </p>
              </div>
              <div className="bg-surface-secondary rounded-lg p-4 border border-border" title="모델 단가 × 토큰으로 계산한 USD 추정치입니다. 프롬프트 캐시 할인은 반영하지 않아 실제 청구액보다 높을 수 있고, 단가를 모르는 모델은 빠집니다.">
                <div className="flex items-center gap-2 text-content-muted mb-2">
                  <DollarSign size={18} />
                  <span className="text-sm">예상 비용</span>
                </div>
                <p className="text-2xl font-bold text-accent-amber">
                  {summary ? formatUsd(summary.cost_usd) : '-'}
                </p>
                {summary?.cost_incomplete && <p className="text-[11px] text-content-muted mt-1">단가를 모르는 모델은 제외됨</p>}
              </div>
              <div className="bg-surface-secondary rounded-lg p-4 border border-border">
                <div className="flex items-center gap-2 text-content-muted mb-2">
                  <Users size={18} />
                  <span className="text-sm">Total Requests</span>
                </div>
                <p className="text-2xl font-bold text-content-primary">
                  {summary ? formatNumber(summary.total_requests) : '-'}
                </p>
              </div>
            </div>

            {/* Time Range Selector */}
            <div className="flex gap-2 mb-4">
              <select
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value as TimeRange)}
                className="bg-surface-secondary text-content-primary rounded px-3 py-2 border border-border focus:border-accent-primary outline-none"
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="bg-surface-secondary text-content-primary rounded px-3 py-2 border border-border focus:border-accent-primary outline-none"
              >
                <option value="7">Last 7 days</option>
                <option value="30">Last 30 days</option>
                <option value="90">Last 90 days</option>
                <option value="365">Last year</option>
              </select>
            </div>

            {/* Usage Chart - Simple CSS bar chart */}
            <div className="bg-surface-secondary rounded-lg p-4 mb-8 border border-border">
              <h2 className={`${T.section} mb-4`}>Token Usage Over Time</h2>
              {usageData.length === 0 ? (
                <div className="text-content-muted text-center py-8">No data available</div>
              ) : (
                <div className="space-y-2">
                  {usageData.slice(-14).map((d) => (
                    <div key={d.date} className="flex items-center gap-3">
                      <span className="text-content-muted text-xs w-24 shrink-0">{d.date}</span>
                      <div className="flex-1 flex h-6 bg-surface-tertiary rounded overflow-hidden">
                        <div
                          className="bg-accent-green h-full"
                          style={{ width: `${(d.input_tokens / maxTokens) * 100}%` }}
                          title={`Input: ${formatNumber(d.input_tokens)}`}
                        />
                        <div
                          className="bg-accent-blue h-full"
                          style={{ width: `${(d.output_tokens / maxTokens) * 100}%` }}
                          title={`Output: ${formatNumber(d.output_tokens)}`}
                        />
                      </div>
                      <span className="text-content-secondary text-xs w-24 text-right shrink-0">
                        {formatNumber(d.total_tokens)}
                      </span>
                      <span className="text-accent-amber text-xs w-16 text-right shrink-0" title="예상 비용">
                        {formatUsd(d.cost_usd)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex gap-4 mt-4 text-xs">
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 bg-accent-green rounded" />
                  <span className="text-content-muted">Input Tokens</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 bg-accent-blue rounded" />
                  <span className="text-content-muted">Output Tokens</span>
                </div>
              </div>
            </div>

            {/* Two-column layout for tables */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* User Breakdown */}
              <div className="bg-surface-secondary rounded-lg p-4 border border-border">
                <div className="flex items-center gap-2 mb-4">
                  <Users size={18} className="text-content-muted" />
                  <h2 className={T.section}>Usage by User</h2>
                </div>
                {userUsage.length === 0 ? (
                  <div className="text-content-muted text-center py-8">No data available</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-content-muted border-b border-border">
                          <th className="text-left py-2 px-2">User</th>
                          <th className="text-right py-2 px-2">Tokens</th>
                          <th className="text-right py-2 px-2">예상 비용</th>
                          <th className="text-right py-2 px-2">Requests</th>
                        </tr>
                      </thead>
                      <tbody>
                        {userUsage.map((u) => (
                          <tr key={u.user_id} className="border-b border-border/50 hover:bg-surface-hover">
                            <td className="py-2 px-2 text-content-primary truncate max-w-[200px]">
                              {u.display_name}
                            </td>
                            <td className="py-2 px-2 text-right text-content-secondary">
                              {formatNumber(u.total_tokens)}
                            </td>
                            <td className="py-2 px-2 text-right text-accent-amber">
                              {formatUsd(u.cost_usd)}{u.cost_incomplete ? '*' : ''}
                            </td>
                            <td className="py-2 px-2 text-right text-content-muted">
                              {formatNumber(u.request_count)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Model Breakdown */}
              <div className="bg-surface-secondary rounded-lg p-4 border border-border">
                <div className="flex items-center gap-2 mb-4">
                  <Cpu size={18} className="text-content-muted" />
                  <h2 className={T.section}>Usage by Model</h2>
                </div>
                {modelUsage.length === 0 ? (
                  <div className="text-content-muted text-center py-8">No data available</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-content-muted border-b border-border">
                          <th className="text-left py-2 px-2">Model</th>
                          <th className="text-right py-2 px-2">Tokens</th>
                          <th className="text-right py-2 px-2">예상 비용</th>
                          <th className="text-right py-2 px-2">Requests</th>
                        </tr>
                      </thead>
                      <tbody>
                        {modelUsage.map((m) => (
                          <tr
                            key={`${m.llm_provider}-${m.model_name}`}
                            className="border-b border-border/50 hover:bg-surface-hover"
                          >
                            <td className="py-2 px-2 text-content-primary">
                              <span className="text-content-muted">{m.llm_provider}/</span>
                              {m.model_name}
                            </td>
                            <td className="py-2 px-2 text-right text-content-secondary">
                              {formatNumber(m.total_tokens)}
                            </td>
                            <td className="py-2 px-2 text-right text-accent-amber" title={m.cost_incomplete ? '이 모델의 단가를 알지 못해 비용에서 제외되었습니다' : undefined}>
                              {m.cost_incomplete && m.cost_usd === 0 ? '단가 없음' : formatUsd(m.cost_usd)}
                            </td>
                            <td className="py-2 px-2 text-right text-content-muted">
                              {formatNumber(m.request_count)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
            <p className="mt-6 text-xs text-content-muted">
              예상 비용은 OpenAI 가격 페이지의 Standard 단가(2026-11-06 확인, USD/1M 토큰) × 토큰으로 계산한 추정치입니다. 입력·출력 토큰만 기록하므로 프롬프트 캐시 할인은 반영하지 않아 실제 청구액보다 높을 수 있고, 목록에 없는 모델(* 표시)은 제외됩니다. 이미지 모델은 텍스트 입력과 이미지 출력 단가로 계산합니다. 동영상 생성 비용은 포함하지 않습니다.
            </p>
          </>
        )}
      </div>
    </SettingsPage>
  )
}
