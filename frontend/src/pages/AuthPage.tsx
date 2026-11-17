import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { authApi } from '../api/auth'

export default function AuthPage() {
  const [loginId, setLoginId] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const { setAuth } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!loginId.trim()) {
      setError('로그인 ID를 입력해주세요')
      return
    }

    setError('')
    setIsLoading(true)

    try {
      const res = await authApi.simpleLogin({ login_id: loginId.trim() })
      const { access_token, user } = res.data
      setAuth(access_token, {
        id: user.id,
        email: user.email,
        display_name: user.display_name,
      })
      navigate('/')
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      setError(err.response?.data?.detail || '로그인에 실패했습니다')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-primary">
      <div className="w-full max-w-md bg-surface-secondary rounded-xl p-8 shadow-lg border border-border">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-content-primary">AI Agent Platform</h1>
          <p className="text-content-secondary mt-1 text-sm">로그인 ID를 입력하세요</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-content-secondary mb-1">
              로그인 ID
            </label>
            <input
              type="text"
              value={loginId}
              onChange={(e) => setLoginId(e.target.value)}
              className="w-full px-3 py-2 bg-surface-primary border border-border rounded-lg text-content-primary placeholder:text-content-muted focus:outline-none focus:border-accent-primary"
              placeholder="사용자 ID를 입력하세요"
              autoFocus
            />
          </div>

          {error && (
            <p className="text-accent-red text-sm bg-accent-red/10 px-3 py-2 rounded-lg">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2.5 px-4 bg-accent-primary hover:bg-accent-hover disabled:opacity-50 text-white font-semibold rounded-lg transition-colors"
          >
            {isLoading ? '로그인 중...' : '로그인'}
          </button>
        </form>

        <p className="mt-6 text-center text-content-tertiary text-xs">
          처음 입력하는 ID는 자동으로 계정이 생성됩니다
        </p>
      </div>
    </div>
  )
}
