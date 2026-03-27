import React, { useState, useRef } from 'react'
import { apiService } from '../api'

export default function FileUpload() {
  const [file, setFile] = useState(null)
  const [title, setTitle] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)

  const handleFileChange = (e) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      const ext = selectedFile.name.split('.').pop().toLowerCase()
      if (['.pdf', '.docx', '.txt', '.md'].includes(`.${ext}`)) {
        setFile(selectedFile)
        setError(null)
      } else {
        setError('Chỉ hỗ trợ: PDF, DOCX, TXT, MD')
        setFile(null)
      }
    }
  }

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!file) {
      setError('Chọn file trước')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await apiService.uploadFile(file, title)
      setResult(response.data)
      setFile(null)
      setTitle('')
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Có lỗi xảy ra')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="section">
      <h2>Tải lên File Pháp luật</h2>
      <form onSubmit={handleUpload}>
        <div className="form-group">
          <label>Chọn file (PDF, DOCX, TXT, MD):</label>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.txt,.md"
            onChange={handleFileChange}
            disabled={loading}
          />
          {file && <p style={{ marginTop: '8px', color: '#4caf50' }}>✓ {file.name}</p>}
        </div>

        <div className="form-group">
          <label>
            Tiêu đề (tùy chọn):
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Nhập tiêu đề cho document"
              disabled={loading}
            />
          </label>
        </div>

        <button type="submit" disabled={loading || !file}>
          {loading ? 'Đang tải...' : 'Tải lên'}
        </button>
      </form>

      {error && <div className="error">{error}</div>}

      {result && (
        <div className="result">
          <div className="answer-box">
            <h3>Tải lên thành công!</h3>
            <p>File: <strong>{result.title}</strong></p>
            <p>Số chunk được thêm: <strong>{result.added_chunks}</strong></p>
          </div>
        </div>
      )}
    </div>
  )
}
