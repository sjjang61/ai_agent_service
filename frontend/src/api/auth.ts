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

export const authApi = {
  login: (data: LoginPayload) => apiClient.post('/auth/login', data),
  register: (data: RegisterPayload) => apiClient.post('/auth/register', data),
  me: () => apiClient.get('/auth/me'),
}
