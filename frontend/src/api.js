import axios from 'axios'

// In Docker: use /api proxy, in development: use localhost:8000
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '/api')

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const apiService = {
  health: async () => {
    return api.get('/health')
  },

  ask: async (question, topK = 3) => {
    return api.post('/ask', {
      question,
      top_k: topK,
    })
  },

  conflict: async (topic, topK = 5) => {
    return api.post('/conflict', {
      topic,
      top_k: topK,
    })
  },

  uploadFile: async (file, title) => {
    const formData = new FormData()
    formData.append('file', file)
    if (title) {
      formData.append('title', title)
    }

    return axios.post(`${API_BASE_URL}/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },
}

export default api
