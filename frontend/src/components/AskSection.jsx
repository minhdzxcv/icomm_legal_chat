import React, { useState, useRef, useEffect } from 'react'
import { apiService } from '../api'
import './AskSection.css'

export default function AskSection() {
  // Multi-conversation management
  const [conversations, setConversations] = useState([])
  const [currentConversationId, setCurrentConversationId] = useState(null)

  // Current chat state
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [topK, setTopK] = useState(3)
  const [expandedIdx, setExpandedIdx] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const chatEndRef = useRef(null)

  // Load conversations from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('legalChatConversations')
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
    localStorage.setItem('legalChatConversations', JSON.stringify(conversations))
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
      title: `Cuộc trò chuyện ${conversations.length + 1}`,
      messages: [],
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

  const handleAsk = async (e) => {
    e.preventDefault()
    if (!question.trim()) {
      setError('Nhập câu hỏi trước')
      return
    }
    if (!currentConversationId) {
      createNewConversation()
      return
    }

    const userQuestion = question
    setQuestion('')
    setError(null)
    setLoading(true)

    try {
      // Add user message immediately
      const newMessage = {
        id: Date.now(),
        question: userQuestion,
        answer: null,
        sources: [],
        intent: 'legal',
        timestamp: new Date(),
        isLoading: true
      }

      setConversations((prev) =>
        prev.map((conv) => {
          if (conv.id === currentConversationId) {
            return {
              ...conv,
              messages: [...conv.messages, newMessage]
            }
          }
          return conv
        })
      )

      // Get response
      const response = await apiService.ask(userQuestion, topK)

      // Update with actual response
      setConversations((prevConversations) =>
        prevConversations.map((conv) => {
          if (conv.id === currentConversationId) {
            return {
              ...conv,
              title:
                conv.messages.length === 1
                  ? userQuestion.substring(0, 40)
                  : conv.title,
              messages: conv.messages.map((msg) => {
                if (msg.id === newMessage.id) {
                  return {
                    ...msg,
                    answer: response.data.answer,
                    sources: response.data.sources || [],
                    intent: response.data.intent || 'legal',
                    isLoading: false
                  }
                }
                return msg
              }),
              updatedAt: new Date().toLocaleString('vi-VN')
            }
          }
          return conv
        })
      )
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Có lỗi xảy ra')
      // Remove loading message on error
      setConversations((prev) =>
        prev.map((conv) => {
          if (conv.id === currentConversationId) {
            return {
              ...conv,
              messages: conv.messages.filter((msg) => !msg.isLoading)
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
    <div className="ask-section-wrapper">
      <div className={`ask-sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
        <div className="sidebar-header">
          <h3>💬 Hỏi đáp</h3>
          <button
            className="toggle-sidebar-btn"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            title="Ẩn/hiện thanh bên"
          >
            {sidebarOpen ? '◀' : '▶'}
          </button>
        </div>

        <button className="new-chat-btn" onClick={createNewConversation}>
          ➕ Chat mới
        </button>

        <div className="conversations-list">
          {conversations.length === 0 ? (
            <div className="empty-conversations">Chưa có cuộc trò chuyện nào</div>
          ) : (
            <>
              {conversations.length > 0 && (
                <div className="conversation-section">
                  <div className="section-label">Hiện tại</div>
                  {conversations[0] && (
                    <div
                      className={`conversation-item ${
                        currentConversationId === conversations[0].id ? 'active' : ''
                      }`}
                      onClick={() => switchConversation(conversations[0].id)}
                    >
                      <div className="conv-title">{conversations[0].title}</div>
                      <div className="conv-meta">{conversations[0].messages.length} tin nhắn</div>
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

              {conversations.length > 1 && (
                <div className="conversation-section">
                  <div className="section-label">Lịch sử</div>
                  {conversations.slice(1).map((conv) => (
                    <div
                      key={conv.id}
                      className={`conversation-item history-item ${
                        currentConversationId === conv.id ? 'active' : ''
                      }`}
                      onClick={() => switchConversation(conv.id)}
                    >
                      <div className="conv-title">{conv.title}</div>
                      <div className="conv-meta">{conv.messages.length} tin nhắn</div>
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

      <div className="ask-section">
        <h2>💬 Hỏi đáp Pháp luật</h2>

        <div className="chat-container">
          {!currentConv || currentConv.messages.length === 0 ? (
            <div className="empty-state">
              <p>
                {currentConv
                  ? 'Chưa có cuộc hội thoại nào. Hãy đặt câu hỏi đầu tiên!'
                  : 'Tạo cuộc trò chuyện mới để bắt đầu'}
              </p>
            </div>
          ) : (
            <>
              {currentConv.messages.map((chat, msgIdx) => (
                <div key={chat.id} className="chat-exchange">
                  <div className="message user-message">
                    <div className="message-content">
                      <strong>Bạn:</strong> {chat.question}
                    </div>
                    <span className="message-time">
                      {chat.timestamp.toLocaleTimeString('vi-VN', {
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </span>
                  </div>

                  {chat.isLoading ? (
                    <div className="message bot-message loading-message">
                      <div className="message-content">
                        <strong>Trợ lý:</strong>
                        <div className="typing-indicator">
                          <span></span>
                          <span></span>
                          <span></span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="message bot-message">
                        <div className="message-content">
                          <strong>Trợ lý:</strong>
                          <p style={{ whiteSpace: 'pre-wrap', marginTop: '8px' }}>{chat.answer}</p>
                        </div>
                      </div>

                      {chat.sources && chat.sources.length > 0 && chat.intent === 'legal_qa' && (
                        <div className="sources-compact">
                          <details
                            open={expandedIdx === msgIdx}
                            onClick={() => setExpandedIdx(expandedIdx === msgIdx ? null : msgIdx)}
                          >
                            <summary>📚 Nguồn tham khảo ({chat.sources.length})</summary>
                            <div className="sources-list">
                              {chat.sources.map((src, idx) => (
                                <div key={idx} className="source-item-compact">
                                  <div className="source-title">
                                    {src.evidence_id ? `[${src.evidence_id}] ` : `${idx + 1}. `}
                                    {src.title}
                                  </div>
                                  <div className="source-meta">
                                    <span className="article-label">{src.article}</span>
                                  </div>
                                  {src.text && <div className="source-preview">{src.text.substring(0, 300)}...</div>}
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

        <form onSubmit={handleAsk} className="chat-input-form">
          <div className="input-wrapper">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Nhập câu hỏi về pháp luật..."
              rows="2"
              disabled={loading}
              className="chat-input"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && e.ctrlKey) {
                  handleAsk(e)
                }
              }}
            />
            <div className="input-controls">
              <label className="top-k-label">
                Top K:
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={topK}
                  onChange={(e) => setTopK(parseInt(e.target.value, 10) || 3)}
                  disabled={loading}
                  className="top-k-input"
                />
              </label>
              <button type="submit" disabled={loading} className="send-btn">
                {loading ? '⏳ Đang gửi...' : '📤 Gửi'}
              </button>
            </div>
          </div>
          <small className="hint-text">💡 Ctrl+Enter để gửi nhanh</small>
        </form>
      </div>
    </div>
  )
}
