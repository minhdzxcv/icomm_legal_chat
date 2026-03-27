import React, { useState, useRef, useEffect } from 'react'
import { apiService } from '../api'
import './ConflictSection.css'

export default function ConflictSection() {
  // Multi-conversation management
  const [conversations, setConversations] = useState([])
  const [currentConversationId, setCurrentConversationId] = useState(null)

  // Current chat state
  const [topic, setTopic] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [topK, setTopK] = useState(5)
  const [expandedIdx, setExpandedIdx] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const chatEndRef = useRef(null)

  // Load conversations from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('conflictConversations')
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        setConversations(parsed)
        if (parsed.length > 0) {
          setCurrentConversationId(parsed[0].id)
        }
      } catch (e) {
        console.error('Failed to load conversations:', e)
      }
    }
  }, [])

  // Save conversations to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem('conflictConversations', JSON.stringify(conversations))
  }, [conversations])

  // Auto-scroll to latest message
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [currentConversationId, conversations])

  const createNewConversation = () => {
    const newConv = {
      id: Date.now(),
      title: `Phân tích ${conversations.length + 1}`,
      analyses: [],
      createdAt: new Date().toLocaleString('vi-VN'),
      updatedAt: new Date().toLocaleString('vi-VN')
    }
    setConversations([newConv, ...conversations])
    setCurrentConversationId(newConv.id)
    setExpandedIdx(null)
    setError(null)
  }

  const switchConversation = (convId) => {
    setCurrentConversationId(convId)
    setExpandedIdx(null)
    setError(null)
  }

  const deleteConversation = (convId) => {
    const filtered = conversations.filter((c) => c.id !== convId)
    setConversations(filtered)
    if (currentConversationId === convId) {
      setCurrentConversationId(filtered.length > 0 ? filtered[0].id : null)
    }
  }

  const getCurrentConversation = () => {
    return conversations.find((c) => c.id === currentConversationId)
  }

  const handleAnalyze = async (e) => {
    e.preventDefault()
    if (!topic.trim()) {
      setError('Nhập chủ đề trước')
      return
    }
    if (!currentConversationId) {
      createNewConversation()
      return
    }

    const userTopic = topic
    setTopic('')
    setError(null)
    setLoading(true)

    try {
      // Add loading analysis immediately
      const newAnalysis = {
        id: Date.now(),
        topic: userTopic,
        report: null,
        sources: [],
        timestamp: new Date(),
        isLoading: true
      }

      setConversations((prev) =>
        prev.map((conv) => {
          if (conv.id === currentConversationId) {
            return {
              ...conv,
              analyses: [...conv.analyses, newAnalysis]
            }
          }
          return conv
        })
      )

      // Get response
      const response = await apiService.conflict(userTopic, topK)

      // Update with actual response
      setConversations((prevConversations) =>
        prevConversations.map((conv) => {
          if (conv.id === currentConversationId) {
            return {
              ...conv,
              title:
                conv.analyses.length === 1
                  ? userTopic.substring(0, 40)
                  : conv.title,
              analyses: conv.analyses.map((ana) => {
                if (ana.id === newAnalysis.id) {
                  return {
                    ...ana,
                    report: response.data.answer || response.data.report,
                    sources: response.data.sources || [],
                    isLoading: false
                  }
                }
                return ana
              }),
              updatedAt: new Date().toLocaleString('vi-VN')
            }
          }
          return conv
        })
      )
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Có lỗi xảy ra')
      // Remove loading analysis on error
      setConversations((prev) =>
        prev.map((conv) => {
          if (conv.id === currentConversationId) {
            return {
              ...conv,
              analyses: conv.analyses.filter((ana) => !ana.isLoading)
            }
          }
          return conv
        })
      )
    } finally {
      setLoading(false)
    }
  }

  const currentConv = getCurrentConversation()

  return (
    <div className="conflict-section-wrapper">
      {/* Sidebar */}
      <div className={`conflict-sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
        <div className="sidebar-header">
          <h3>📊 Phân tích</h3>
          <button
            className="toggle-sidebar-btn"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            title="Ẩn/hiện thanh bên"
          >
            {sidebarOpen ? '◀' : '▶'}
          </button>
        </div>

        <button className="new-chat-btn" onClick={createNewConversation}>
          ➕ Phân tích mới
        </button>

        <div className="conversations-list">
          {conversations.length === 0 ? (
            <div className="empty-conversations">Chưa có phân tích nào</div>
          ) : (
            <>
              {/* Current conversation */}
              {conversations.length > 0 && (
                <div className="conversation-section">
                  <div className="section-label">Hiện tại</div>
                  {conversations[0] && (
                    <div
                      className={`conversation-item ${currentConversationId === conversations[0].id ? 'active' : ''
                        }`}
                      onClick={() => switchConversation(conversations[0].id)}
                    >
                      <div className="conv-title">{conversations[0].title}</div>
                      <div className="conv-meta">
                        {conversations[0].analyses.length} phân tích
                      </div>
                      <button
                        className="delete-conv-btn"
                        onClick={(e) => {
                          e.stopPropagation()
                          deleteConversation(conversations[0].id)
                        }}
                        title="Xóa"
                      >
                        🗑️
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* History */}
              {conversations.length > 1 && (
                <div className="conversation-section">
                  <div className="section-label">Lịch sử</div>
                  {conversations.slice(1).map((conv) => (
                    <div
                      key={conv.id}
                      className={`conversation-item history-item ${currentConversationId === conv.id ? 'active' : ''
                        }`}
                      onClick={() => switchConversation(conv.id)}
                    >
                      <div className="conv-title">{conv.title}</div>
                      <div className="conv-meta">
                        {conv.analyses.length} phân tích
                      </div>
                      <button
                        className="delete-conv-btn"
                        onClick={(e) => {
                          e.stopPropagation()
                          deleteConversation(conv.id)
                        }}
                        title="Xóa"
                      >
                        🗑️
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Main analysis area */}
      <div className="conflict-section">
        <h2>📊 Phân tích Xung đột Pháp lệnh</h2>

        {/* Analyses container */}
        <div className="analyses-container">
          {!currentConv || currentConv.analyses.length === 0 ? (
            <div className="empty-state">
              <p>
                {currentConv
                  ? 'Chưa có phân tích nào. Hãy nhập chủ đề đầu tiên!'
                  : 'Tạo phân tích mới để bắt đầu'}
              </p>
            </div>
          ) : (
            <>
              {currentConv.analyses.map((analysis, anaIdx) => (
                <div key={analysis.id} className="analysis-item">
                  <div className="analysis-topic">
                    <strong>🔍 Chủ đề:</strong> {analysis.topic}
                    <span className="analysis-time">
                      {analysis.timestamp.toLocaleTimeString('vi-VN', {
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </span>
                  </div>

                  {analysis.isLoading ? (
                    <div className="analysis-report loading-report">
                      <h4>📋 Đang phân tích...</h4>
                      <div className="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="analysis-report">
                        <h4>📋 Báo cáo Xung đột</h4>
                        <p style={{ whiteSpace: 'pre-wrap' }}>{analysis.report}</p>
                      </div>

                      {analysis.sources && analysis.sources.length > 0 && (
                        <div className="analysis-sources">
                          <details
                            open={expandedIdx === anaIdx}
                            onClick={() =>
                              setExpandedIdx(expandedIdx === anaIdx ? null : anaIdx)
                            }
                          >
                            <summary>
                              📚 Nguồn tham khảo ({analysis.sources.length})
                            </summary>
                            <div className="sources-list">
                              {analysis.sources.map((src, idx) => (
                                <div key={idx} className="source-item">
                                  <div className="source-header-compact">
                                    <strong>{idx + 1}. {src.title}</strong>
                                  </div>
                                  <div className="source-info">
                                    <div className="source-meta-item">
                                      <span className="label">Điều:</span>
                                      <span>{src.article}</span>
                                    </div>
                                    {src.legal_type && (
                                      <div className="source-meta-item">
                                        <span className="label">Loại:</span>
                                        <span>{src.legal_type}</span>
                                      </div>
                                    )}
                                  </div>
                                  {src.text && (
                                    <div className="source-text">
                                      <p>{src.text.substring(0, 400)}...</p>
                                    </div>
                                  )}
                                  <a
                                    href={src.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="source-url-link"
                                  >
                                    Xem đầy đủ →
                                  </a>
                                </div>
                              ))}
                            </div>
                          </details>
                        </div>
                      )}
                    </>
                  )}
                </div>
              ))}
              <div ref={chatEndRef} />
            </>
          )}
        </div>

        {error && <div className="error">{error}</div>}

        {/* Input form */}
        <form onSubmit={handleAnalyze} className="analysis-form">
          <div className="form-wrapper">
            <textarea
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Nhập chủ đề để phân tích xung đột pháp lệnh..."
              rows="2"
              disabled={loading}
              className="topic-input"
            />
            <div className="form-controls">
              <label className="topk-label">
                Top K:
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={topK}
                  onChange={(e) => setTopK(parseInt(e.target.value) || 5)}
                  disabled={loading}
                  className="topk-input"
                />
              </label>
              <button type="submit" disabled={loading} className="analyze-btn">
                {loading ? '⏳ Đang phân tích...' : '🔍 Phân tích'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}
