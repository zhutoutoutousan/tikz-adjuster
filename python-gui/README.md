# TikZ Diagram Editor - Desktop GUI

A desktop application for visually editing TikZ diagrams with drag-and-drop functionality.

## Features

- **Visual Editor**: Render TikZ diagrams and see them visually
- **Drag & Drop**: Reposition nodes by dragging them on the canvas
- **Grid System**: Snap to grid for precise alignment
- **Code Editor**: Edit TikZ code directly with syntax highlighting
- **Real-time Sync**: Visual changes update the code (on export)
- **Export**: Generate updated TikZ code from visual edits

## Installation

1. Install Python 3.8 or higher
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the application:
```bash
python main.py
```

### Building Executable

To create a standalone executable:
```bash
pyinstaller --onefile --windowed --name tikz-editor main.py
```

The executable will be in the `dist` folder.

## How to Use

1. **Load Code**: Paste or type your TikZ code in the left panel
2. **Render**: Click "Render Diagram" to visualize the diagram
3. **Edit Visually**: Drag nodes to reposition them on the canvas
4. **Export**: Click "Export Code" to get the updated TikZ code with new positions

## Limitations

- Currently supports basic node types (cloud, service, db, k8s, api)
- Connection editing is read-only (positions update automatically)
- Complex TikZ features may not be fully supported

## Future Improvements

- Full TikZ syntax support
- Edit node properties (text, colors, sizes)
- Add/remove nodes and connections
- Better LaTeX rendering integration
- Undo/redo functionality

