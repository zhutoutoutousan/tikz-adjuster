import React, { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Editor from '@monaco-editor/react'
import Draggable from 'react-draggable'
import axios from 'axios'
import './Editor.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const TikZEditor = () => {
  const { id } = useParams()
  const navigate = useNavigate()
  const [tikzCode, setTikzCode] = useState('')
  const [title, setTitle] = useState('New Diagram')
  const [nodes, setNodes] = useState([])
  const [connections, setConnections] = useState([])
  const [selectedNode, setSelectedNode] = useState(null)
  const [showGrid, setShowGrid] = useState(true)
  const canvasRef = useRef(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (id) {
      loadDiagram(id)
    } else {
      loadExample()
    }
  }, [id])

  useEffect(() => {
    parseTikZCode(tikzCode)
  }, [tikzCode])

  const loadExample = () => {
    const example = `\\begin{tikzpicture}[
    node distance=1.5cm and 2cm,
    cloud/.style={ellipse, draw, fill=blue!20, text width=3cm, text centered, minimum height=1.5cm, rounded corners, drop shadow},
    service/.style={rectangle, draw, fill=orange!20, text width=2.5cm, text centered, minimum height=1cm, rounded corners},
    db/.style={cylinder, draw, fill=purple!20, text width=2cm, text centered, minimum height=1.2cm, aspect=0.3},
    k8s/.style={rectangle, draw, fill=green!20, text width=3cm, text centered, minimum height=1.5cm, rounded corners, dashed},
    arrow/.style={->, >=stealth, thick},
    api/.style={rectangle, draw, fill=yellow!20, text width=2.5cm, text centered, minimum height=1cm, rounded corners}
]
    \\node[cloud] (aws) at (-6,3) {\\textbf{AWS}\\\\small EC2 GPU};
    \\node[cloud] (gcp) at (-1.3,3) {\\textbf{GCP}\\\\small Compute};
    \\node[cloud] (azure) at (1.3,3) {\\textbf{Azure}\\\\small NC VMs};
    \\node[cloud] (aliyun) at (6,3) {\\textbf{阿里云}\\\\small Alibaba};
    \\node[cloud] (tencent) at (-6,1.5) {\\textbf{腾讯云}\\\\small Tencent};
    \\node[cloud] (huawei) at (6,1.5) {\\textbf{华为云}\\\\small Huawei};
    \\node[cloud, above=of gcp, yshift=0.5cm] (openai) {OpenAI\\\\GPT-4};
    \\node[cloud, right=of openai, xshift=1cm] (anthropic) {Anthropic\\\\Claude};
    \\node[k8s] (k8s) at (0,0) {\\textbf{Kubernetes}\\\\small Multi-Cloud};
    \\node[service, below=of k8s, xshift=-2.5cm] (llama) {Llama 3.1\\\\70B (vLLM)};
    \\node[service, below=of k8s, xshift=-0.8cm] (langflow) {LangFlow\\\\Orchestrator};
    \\node[service, below=of k8s, xshift=0.8cm] (fastapi) {FastAPI\\\\Service};
    \\node[service, below=of k8s, xshift=2.5cm] (ollama) {Ollama\\\\Models};
    \\node[api, above=of k8s, yshift=-0.3cm] (gateway) {\\textbf{API Gateway}\\\\small Multi-Cloud};
    \\node[db, below=of llama, yshift=-0.5cm] (weaviate) {Weaviate\\\\Vector DB};
    \\node[db, below=of fastapi, yshift=-0.5cm] (postgres) {PostgreSQL\\\\Managed};
    \\node[db, below=of ollama, yshift=-0.5cm] (storage) {Object\\\\Storage};
    \\draw[arrow, dashed] (aws) -- (k8s);
    \\draw[arrow, dashed] (gcp) -- (k8s);
    \\draw[arrow, dashed] (azure) -- (k8s);
    \\draw[arrow, dashed] (aliyun) -- (k8s);
    \\draw[arrow, dashed] (tencent) -- (k8s);
    \\draw[arrow, dashed] (huawei) -- (k8s);
    \\draw[arrow] (gateway) -- (k8s);
    \\draw[arrow] (k8s) -- (llama);
    \\draw[arrow] (k8s) -- (langflow);
    \\draw[arrow] (k8s) -- (fastapi);
    \\draw[arrow] (k8s) -- (ollama);
    \\draw[arrow] (langflow) -- (openai);
    \\draw[arrow] (langflow) -- (anthropic);
    \\draw[arrow] (llama) -- (weaviate);
    \\draw[arrow] (fastapi) -- (postgres);
    \\draw[arrow] (ollama) -- (storage);
\\end{tikzpicture}`
    setTikzCode(example)
  }

  const loadDiagram = async (diagramId) => {
    try {
      const response = await axios.get(`${API_URL}/diagrams/${diagramId}`)
      setTikzCode(response.data.tikz_code)
      setTitle(response.data.title)
    } catch (error) {
      console.error('Failed to load diagram:', error)
    }
  }

  const parseTikZCode = (code) => {
    const nodeRegex = /\\node\[([^\]]*)\]\s*\(([^)]+)\)\s*at\s*\(([^)]+)\)\s*\{([^}]*)\}/g
    const nodes = []
    const connections = []

    let match
    while ((match = nodeRegex.exec(code)) !== null) {
      const style = match[1]
      const name = match[2]
      const coords = match[3].replace(/cm/g, '').trim().split(',')
      const text = match[4].replace(/\\textbf\{([^}]+)\}/g, '$1').replace(/\\\\/g, '\n')

      if (coords.length === 2) {
        const x = parseFloat(coords[0].trim()) * 50 + 400
        const y = -parseFloat(coords[1].trim()) * 50 + 300

        let styleType = 'rectangle'
        if (style.includes('cloud') || style.includes('ellipse')) styleType = 'ellipse'
        else if (style.includes('db') || style.includes('cylinder')) styleType = 'cylinder'
        else if (style.includes('k8s')) styleType = 'dashed_rect'
        else if (style.includes('api')) styleType = 'yellow_rect'

        nodes.push({ name, x, y, text, styleType })
      }
    }

    // Parse connections
    const arrowRegex = /\\draw\[([^\]]*)\]\s*\(([^)]+)\)\s*--\s*\(([^)]+)\)/g
    while ((match = arrowRegex.exec(code)) !== null) {
      const fromName = match[2]
      const toName = match[3]
      const fromNode = nodes.find(n => n.name === fromName)
      const toNode = nodes.find(n => n.name === toName)
      if (fromNode && toNode) {
        connections.push({ from: fromName, to: toName, dashed: match[1].includes('dashed') })
      }
    }

    setNodes(nodes)
    setConnections(connections)
  }

  const handleNodeDrag = (nodeName, data) => {
    setNodes(prevNodes =>
      prevNodes.map(node =>
        node.name === nodeName
          ? { ...node, x: data.x + 400, y: data.y + 300 }
          : node
      )
    )
    updateCodeFromNodes()
  }

  const updateCodeFromNodes = () => {
    // Update TikZ code with new positions
    let updatedCode = tikzCode
    nodes.forEach(node => {
      const tikzX = ((node.x - 400) / 50).toFixed(2)
      const tikzY = (-(node.y - 300) / 50).toFixed(2)
      const regex = new RegExp(`\\(${node.name}\\)\\s*at\\s*\\([^)]+\\)`, 'g')
      updatedCode = updatedCode.replace(regex, `(${node.name}) at (${tikzX}cm,${tikzY}cm)`)
    })
    setTikzCode(updatedCode)
  }

  const saveDiagram = async () => {
    setSaving(true)
    try {
      if (id) {
        await axios.put(`${API_URL}/diagrams/${id}`, {
          title,
          tikz_code: tikzCode
        })
      } else {
        const response = await axios.post(`${API_URL}/diagrams`, {
          title,
          tikz_code: tikzCode
        })
        navigate(`/editor/${response.data.id}`)
      }
      alert('Diagram saved successfully!')
    } catch (error) {
      alert('Failed to save diagram: ' + (error.response?.data?.detail || error.message))
    } finally {
      setSaving(false)
    }
  }

  const getNodeStyle = (styleType) => {
    const styles = {
      ellipse: { backgroundColor: '#ADD8E6', borderRadius: '50%' },
      cylinder: { backgroundColor: '#DDA0DD' },
      dashed_rect: { backgroundColor: '#90EE90', borderStyle: 'dashed' },
      yellow_rect: { backgroundColor: '#FFFFC8' },
      rectangle: { backgroundColor: '#FFDAB9' }
    }
    return styles[styleType] || styles.rectangle
  }

  return (
    <div className="editor-container">
      <div className="editor-header">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="title-input"
          placeholder="Diagram Title"
        />
        <div className="editor-controls">
          <label>
            <input
              type="checkbox"
              checked={showGrid}
              onChange={(e) => setShowGrid(e.target.checked)}
            />
            Show Grid
          </label>
          <button onClick={saveDiagram} disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
      <div className="editor-split">
        <div className="code-panel">
          <h3>TikZ Code</h3>
          <Editor
            height="100%"
            defaultLanguage="latex"
            value={tikzCode}
            onChange={setTikzCode}
            theme="vs-dark"
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              wordWrap: 'on'
            }}
          />
        </div>
        <div className="canvas-panel">
          <h3>Visual Editor</h3>
          <div
            ref={canvasRef}
            className="tikz-canvas"
            style={{
              backgroundImage: showGrid
                ? 'linear-gradient(to right, #f0f0f0 1px, transparent 1px), linear-gradient(to bottom, #f0f0f0 1px, transparent 1px)'
                : 'none',
              backgroundSize: '20px 20px'
            }}
          >
            {/* Draw connections */}
            <svg className="connections-layer" style={{ position: 'absolute', width: '100%', height: '100%', pointerEvents: 'none' }}>
              {connections.map((conn, idx) => {
                const fromNode = nodes.find(n => n.name === conn.from)
                const toNode = nodes.find(n => n.name === conn.to)
                if (!fromNode || !toNode) return null
                return (
                  <line
                    key={idx}
                    x1={fromNode.x}
                    y1={fromNode.y}
                    x2={toNode.x}
                    y2={toNode.y}
                    stroke={conn.dashed ? '#999' : '#666'}
                    strokeWidth="2"
                    strokeDasharray={conn.dashed ? '5,5' : '0'}
                    markerEnd="url(#arrowhead)"
                  />
                )
              })}
              <defs>
                <marker id="arrowhead" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
                  <polygon points="0 0, 10 3, 0 6" fill="#666" />
                </marker>
              </defs>
            </svg>

            {/* Draw nodes */}
            {nodes.map((node) => (
              <Draggable
                key={node.name}
                position={{ x: node.x - 400, y: node.y - 300 }}
                onDrag={(e, data) => handleNodeDrag(node.name, data)}
                grid={[20, 20]}
              >
                <div
                  className={`tikz-node ${selectedNode === node.name ? 'selected' : ''}`}
                  style={{
                    left: '50%',
                    top: '50%',
                    transform: 'translate(-50%, -50%)',
                    ...getNodeStyle(node.styleType)
                  }}
                  onClick={() => setSelectedNode(node.name)}
                >
                  <div className="node-text">
                    {node.text.split('\n').map((line, i) => (
                      <div key={i}>{line}</div>
                    ))}
                  </div>
                </div>
              </Draggable>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default TikZEditor

