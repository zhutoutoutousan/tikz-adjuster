# TikZ Diagram Editor - Frontend

React-based web interface for editing TikZ diagrams with visual drag-and-drop functionality.

## Features

- **Visual Editor**: Drag and drop nodes to reposition them
- **Code Editor**: Monaco editor with LaTeX syntax highlighting
- **Real-time Sync**: Code and visual editor stay in sync
- **User Authentication**: Login and registration
- **Diagram Management**: Save, load, and manage multiple diagrams
- **Grid System**: Optional grid for precise alignment

## Installation

1. Install Node.js 18+ and npm
2. Install dependencies:
```bash
npm install
```

## Configuration

Create a `.env` file in the frontend directory:
```
VITE_API_URL=http://localhost:8000
```

## Running the Application

Development:
```bash
npm run dev
```

The app will be available at http://localhost:3000

Build for production:
```bash
npm run build
```

Preview production build:
```bash
npm run preview
```

## Usage

1. **Register/Login**: Create an account or login
2. **Create Diagram**: Click "New Diagram" to start editing
3. **Edit Code**: Write or paste TikZ code in the left panel
4. **Visual Edit**: Drag nodes in the right panel to reposition them
5. **Save**: Click "Save" to store your diagram
6. **Manage**: View all your diagrams in the Dashboard

## Features in Detail

### Visual Editor
- Drag nodes to reposition them
- Grid snapping for alignment
- Visual representation of different node types (clouds, services, databases, etc.)
- Connections between nodes are automatically drawn

### Code Editor
- Monaco editor with LaTeX syntax highlighting
- Real-time code updates when nodes are moved
- Full TikZ syntax support

## Tech Stack

- **React 18**: UI framework
- **React Router**: Navigation
- **Monaco Editor**: Code editing
- **React Draggable**: Drag and drop functionality
- **Axios**: HTTP client
- **Vite**: Build tool

## Future Improvements

- Full TikZ syntax parsing
- Edit node properties (text, colors, sizes)
- Add/remove nodes and connections visually
- Export to PDF/PNG
- Collaboration features
- Template library

