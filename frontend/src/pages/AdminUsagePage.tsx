import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Database, BarChart3, Users, Cpu } from 'lucide-react'
import { adminApi } from '../api/admin'
import type { UsageSummary, DailyUsage, UserUsage, ModelUsage } from '../types/admin'

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
    <div className="min-h-screen bg-slate-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <Link to="/" className="text-slate-400 hover:text-white transition-colors">
            <ArrowLeft size={20} />
          </Link>
          <h1 className="text-xl font-bold text-white">Token Usage Analytics</h1>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-64 text-slate-400">
            Loading...
          </div>
        ) : (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
              <div className="bg-slate-800 rounded-lg p-4">
                <div className="flex items-center gap-2 text-slate-400 mb-2">
                  <Database size={18} />
                  <span className="text-sm">Total Tokens</span>
                </div>
                <p className="text-2xl font-bold text-white">
                  {summary ? formatNumber(summary.total_tokens) : '-'}
                </p>
              </div>
              <div className="bg-slate-800 rounded-lg p-4">
                <div className="flex items-center gap-2 text-slate-400 mb-2">
                  <BarChart3 size={18} />
                  <span className="text-sm">Input Tokens</span>
                </div>
                <p className="text-2xl font-bold text-emerald-400">
                  {summary ? formatNumber(summary.total_input_tokens) : '-'}
                </p>
              </div>
              <div className="bg-slate-800 rounded-lg p-4">
                <div className="flex items-center gap-2 text-slate-400 mb-2">
                  <BarChart3 size={18} />
                  <span className="text-sm">Output Tokens</span>
                </div>
                <p className="text-2xl font-bold text-blue-400">
                  {summary ? formatNumber(summary.total_output_tokens) : '-'}
                </p>
              </div>
              <div className="bg-slate-800 rounded-lg p-4">
                <div className="flex items-center gap-2 text-slate-400 mb-2">
                  <Users size={18} />
                  <span className="text-sm">Total Requests</span>
                </div>
                <p className="text-2xl font-bold text-white">
                  {summary ? formatNumber(summary.total_requests) : '-'}
                </p>
              </div>
            </div>

            {/* Time Range Selector */}
            <div className="flex gap-2 mb-4">
              <select
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value as TimeRange)}
                className="bg-slate-800 text-white rounded px-3 py-2 border border-slate-700 focus:border-blue-500 outline-none"
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="bg-slate-800 text-white rounded px-3 py-2 border border-slate-700 focus:border-blue-500 outline-none"
              >
                <option value="7">Last 7 days</option>
                <option value="30">Last 30 days</option>
                <option value="90">Last 90 days</option>
                <option value="365">Last year</option>
              </select>
            </div>

            {/* Usage Chart - Simple CSS bar chart */}
            <div className="bg-slate-800 rounded-lg p-4 mb-8">
              <h2 className="text-lg font-semibold text-white mb-4">Token Usage Over Time</h2>
              {usageData.length === 0 ? (
                <div className="text-slate-400 text-center py-8">No data available</div>
              ) : (
                <div className="space-y-2">
                  {usageData.slice(-14).map((d) => (
                    <div key={d.date} className="flex items-center gap-3">
                      <span className="text-slate-400 text-xs w-24 shrink-0">{d.date}</span>
                      <div className="flex-1 flex h-6 bg-slate-700 rounded overflow-hidden">
                        <div
                          className="bg-emerald-500 h-full"
                          style={{ width: `${(d.input_tokens / maxTokens) * 100}%` }}
                          title={`Input: ${formatNumber(d.input_tokens)}`}
                        />
                        <div
                          className="bg-blue-500 h-full"
                          style={{ width: `${(d.output_tokens / maxTokens) * 100}%` }}
                          title={`Output: ${formatNumber(d.output_tokens)}`}
                        />
                      </div>
                      <span className="text-slate-300 text-xs w-24 text-right shrink-0">
                        {formatNumber(d.total_tokens)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex gap-4 mt-4 text-xs">
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 bg-emerald-500 rounded" />
                  <span className="text-slate-400">Input Tokens</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 bg-blue-500 rounded" />
                  <span className="text-slate-400">Output Tokens</span>
                </div>
              </div>
            </div>

            {/* Two-column layout for tables */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* User Breakdown */}
              <div className="bg-slate-800 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-4">
                  <Users size={18} className="text-slate-400" />
                  <h2 className="text-lg font-semibold text-white">Usage by User</h2>
                </div>
                {userUsage.length === 0 ? (
                  <div className="text-slate-400 text-center py-8">No data available</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-slate-400 border-b border-slate-700">
                          <th className="text-left py-2 px-2">User</th>
                          <th className="text-right py-2 px-2">Tokens</th>
                          <th className="text-right py-2 px-2">Requests</th>
                        </tr>
                      </thead>
                      <tbody>
                        {userUsage.map((u) => (
                          <tr key={u.user_id} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                            <td className="py-2 px-2 text-white truncate max-w-[200px]">
                              {u.display_name}
                            </td>
                            <td className="py-2 px-2 text-right text-slate-300">
                              {formatNumber(u.total_tokens)}
                            </td>
                            <td className="py-2 px-2 text-right text-slate-400">
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
              <div className="bg-slate-800 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-4">
                  <Cpu size={18} className="text-slate-400" />
                  <h2 className="text-lg font-semibold text-white">Usage by Model</h2>
                </div>
                {modelUsage.length === 0 ? (
                  <div className="text-slate-400 text-center py-8">No data available</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-slate-400 border-b border-slate-700">
                          <th className="text-left py-2 px-2">Model</th>
                          <th className="text-right py-2 px-2">Tokens</th>
                          <th className="text-right py-2 px-2">Requests</th>
                        </tr>
                      </thead>
                      <tbody>
                        {modelUsage.map((m) => (
                          <tr
                            key={`${m.llm_provider}-${m.model_name}`}
                            className="border-b border-slate-700/50 hover:bg-slate-700/30"
                          >
                            <td className="py-2 px-2 text-white">
                              <span className="text-slate-500">{m.llm_provider}/</span>
                              {m.model_name}
                            </td>
                            <td className="py-2 px-2 text-right text-slate-300">
                              {formatNumber(m.total_tokens)}
                            </td>
                            <td className="py-2 px-2 text-right text-slate-400">
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
          </>
        )}
      </div>
    </div>
  )
}
