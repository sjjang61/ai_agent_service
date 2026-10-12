import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { useAuthStore } from '../store/authStore'
import { authApi } from '../api/auth'

interface FormData {
  email: string
  password: string
  display_name: string
}

export default function AuthPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [error, setError] = useState('')
  const { setAuth } = useAuthStore()
  const navigate = useNavigate()
  const {
    register,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<FormData>()

  const onSubmit = async (data: FormData) => {
    setError('')
    try {
      if (mode === 'login') {
        const res = await authApi.login({ email: data.email, password: data.password })
        setAuth(res.data.access_token, { id: '', email: data.email, display_name: '' })
        const meRes = await authApi.me()
        setAuth(res.data.access_token, meRes.data)
        navigate('/')
      } else {
        await authApi.register(data)
        const res = await authApi.login({ email: data.email, password: data.password })
        setAuth(res.data.access_token, { id: '', email: data.email, display_name: '' })
        const meRes = await authApi.me()
        setAuth(res.data.access_token, meRes.data)
        navigate('/')
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      setError(err.response?.data?.detail || 'An error occurred')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900">
      <div className="w-full max-w-md bg-slate-800 rounded-xl p-8 shadow-2xl border border-slate-700">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-white">AI Agent Platform</h1>
          <p className="text-slate-400 mt-1 text-sm">
            {mode === 'login' ? 'Sign in to your account' : 'Create a new account'}
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {mode === 'register' && (
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">
                Display Name
              </label>
              <input
                {...register('display_name')}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                placeholder="Your name"
              />
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Email</label>
            <input
              {...register('email')}
              type="email"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Password</label>
            <input
              {...register('password')}
              type="password"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              placeholder="••••••••"
            />
          </div>

          {error && <p className="text-red-400 text-sm bg-red-900/20 px-3 py-2 rounded-lg">{error}</p>}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold rounded-lg transition-colors"
          >
            {isSubmitting ? 'Loading...' : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>

        <p className="mt-4 text-center text-slate-400 text-sm">
          {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
          <button
            onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
            className="text-blue-400 hover:underline"
          >
            {mode === 'login' ? 'Register' : 'Sign In'}
          </button>
        </p>
      </div>
    </div>
  )
}
