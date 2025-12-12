import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import './Dashboard.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const Dashboard = () => {
  const [diagrams, setDiagrams] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    loadDiagrams()
  }, [])

  const loadDiagrams = async () => {
    try {
      const response = await axios.get(`${API_URL}/diagrams`)
      setDiagrams(response.data)
    } catch (error) {
      console.error('Failed to load diagrams:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id, e) => {
    e.stopPropagation()
    if (!window.confirm('Are you sure you want to delete this diagram?')) {
      return
    }

    try {
      await axios.delete(`${API_URL}/diagrams/${id}`)
      setDiagrams(diagrams.filter(d => d.id !== id))
    } catch (error) {
      alert('Failed to delete diagram: ' + (error.response?.data?.detail || error.message))
    }
  }

  if (loading) {
    return <div className="dashboard-loading">Loading...</div>
  }

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <h1>My Diagrams</h1>
        <button onClick={() => navigate('/editor')} className="new-diagram-btn">
          + New Diagram
        </button>
      </div>

      {diagrams.length === 0 ? (
        <div className="empty-state">
          <p>No diagrams yet. Create your first diagram!</p>
          <button onClick={() => navigate('/editor')}>Create Diagram</button>
        </div>
      ) : (
        <div className="diagrams-grid">
          {diagrams.map((diagram) => (
            <div
              key={diagram.id}
              className="diagram-card"
              onClick={() => navigate(`/editor/${diagram.id}`)}
            >
              <h3>{diagram.title}</h3>
              <p className="diagram-meta">
                Created: {new Date(diagram.created_at).toLocaleDateString()}
                {diagram.updated_at !== diagram.created_at && (
                  <span> • Updated: {new Date(diagram.updated_at).toLocaleDateString()}</span>
                )}
              </p>
              <div className="diagram-actions">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    navigate(`/editor/${diagram.id}`)
                  }}
                >
                  Edit
                </button>
                <button
                  onClick={(e) => handleDelete(diagram.id, e)}
                  className="delete-btn"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default Dashboard

