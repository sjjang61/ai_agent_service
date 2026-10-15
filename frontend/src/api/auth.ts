import apiClient from './client'

export interface LoginPayload {
  email: string
  password: string
}

export interface RegisterPayload {
  email: string
  password: string
  display_name: string
}

export interface SimpleLoginPayload {
  login_id: string
}

export interface SimpleLoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: {
    id: string
    email: string
    display_name: string
    is_active: boolean
    created_at: string
  }
}

export const authApi = {
  login: (data: LoginPayload) => apiClient.post('/auth/login', data),
  register: (data: RegisterPayload) => apiClient.post('/auth/register', data),
  simpleLogin: (data: SimpleLoginPayload) =>
    apiClient.post<SimpleLoginResponse>('/auth/simple-login', data),
  me: () => apiClient.get('/auth/me'),
}
