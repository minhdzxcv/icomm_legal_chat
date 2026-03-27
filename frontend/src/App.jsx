import React, { useState, useEffect } from 'react'
import AskSection from './components/AskSection'
import ConflictSection from './components/ConflictSection'
import FileUpload from './components/FileUpload'
import { apiService } from './api'
import './App.css'

function App() {
  const [apiStatus, setApiStatus] = useState('checking')
  const [activeTab, setActiveTab] = useState('ask')

  useEffect(() => {
    const checkHealth = async () => {
      try {
        await apiService.health()
        setApiStatus('connected')
      } catch (err) {
        setApiStatus('disconnected')
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 10000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="app">
      <header className="header">
        <h1>⚖️ Legal Chatbot - RAG + Conflict Analysis</h1>
        <div className="status-bar">
          <span className={`status ${apiStatus}`}>
            {apiStatus === 'connected' ? '🟢 API Ready' : '🔴 API Disconnected'}
          </span>
        </div>
      </header>

      {apiStatus === 'disconnected' && (
        <div className="warning">
          ⚠️ Không thể kết nối đến API backend. Kiểm tra xem backend có chạy ở http://localhost:8000
        </div>
      )}

      <nav className="tabs">
        <button
          className={`tab ${activeTab === 'ask' ? 'active' : ''}`}
          onClick={() => setActiveTab('ask')}
        >
          Hỏi đáp
        </button>
        <button
          className={`tab ${activeTab === 'conflict' ? 'active' : ''}`}
          onClick={() => setActiveTab('conflict')}
        >
          Xung đột
        </button>
        <button
          className={`tab ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveTab('upload')}
        >
          Tải lên
        </button>
      </nav>

      <main className="main-content">
        {activeTab === 'ask' && <AskSection />}
        {activeTab === 'conflict' && <ConflictSection />}
        {activeTab === 'upload' && <FileUpload />}
      </main>

      <footer className="footer">
        <p>Legal RAG Chatbot v1.0 | Backend: {import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}</p>
      </footer>
    </div>
  )
}

export default App
