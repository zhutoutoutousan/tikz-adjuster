# TikZ Diagram Editor

A comprehensive tool for visually editing TikZ diagrams with drag-and-drop functionality. Available as a desktop application (Python GUI) and web service (React frontend + FastAPI backend).

## Project Structure

```
tikz-adjuster/
├── python-gui/          # Desktop application (PyQt5)
├── backend/             # FastAPI backend service
└── frontend/            # React web frontend
```

## Features

- **Visual Editor**: Render TikZ diagrams and edit them visually
- **Drag & Drop**: Reposition nodes by dragging on canvas
- **Grid System**: Snap to grid for precise alignment
- **Code Editor**: Edit TikZ code with syntax highlighting
- **Real-time Sync**: Visual changes update code automatically
- **User Accounts**: Register, login, and manage diagrams
- **Premium Subscriptions**: Stripe integration for monthly subscriptions
- **Multi-platform**: Desktop app (Windows/Mac/Linux) and web service

## Quick Start

### Desktop Application (Python GUI)

```bash
cd python-gui
pip install -r requirements.txt
python main.py
```

To build executable:
```bash
pyinstaller --onefile --windowed --name tikz-editor main.py
```

### Web Service

**Backend:**
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration
uvicorn main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:3000

## Documentation

- [Python GUI README](python-gui/README.md)
- [Backend README](backend/README.md)
- [Frontend README](frontend/README.md)

## Architecture

### Desktop Application
- **PyQt5**: GUI framework
- **TikZ Parsing**: Custom parser for node and connection extraction
- **Canvas Rendering**: Custom widget for visual editing

### Backend Service
- **FastAPI**: REST API framework
- **SQLAlchemy**: Database ORM
- **JWT**: Authentication
- **Stripe**: Payment processing
- **PostgreSQL/SQLite**: Database

### Web Frontend
- **React**: UI framework
- **Monaco Editor**: Code editing
- **React Draggable**: Drag and drop
- **Axios**: API client

## Configuration

### Backend Environment Variables

See `backend/.env.example` for required variables:
- `DATABASE_URL`: Database connection string
- `SECRET_KEY`: JWT secret key
- `STRIPE_SECRET_KEY`: Stripe API key
- `STRIPE_WEBHOOK_SECRET`: Stripe webhook secret

### Frontend Environment Variables

Create `frontend/.env`:
```
VITE_API_URL=http://localhost:8000
```

## Development Roadmap

- [x] Basic TikZ parsing and rendering
- [x] Drag and drop functionality
- [x] User authentication
- [x] Diagram storage
- [x] Stripe integration
- [ ] Full TikZ syntax support
- [ ] Node property editing
- [ ] Add/remove nodes visually
- [ ] Export to PDF/PNG
- [ ] LaTeX compilation service
- [ ] Template library
- [ ] Collaboration features

## License

MIT License

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

