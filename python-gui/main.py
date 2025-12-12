"""
TikZ Diagram Editor - Desktop GUI Application
A visual editor for TikZ diagrams with drag-and-drop functionality
"""

import sys
import re
import subprocess
import tempfile
import os
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QPushButton, QLabel, 
                             QSplitter, QMessageBox, QFileDialog, QMenuBar, 
                             QMenu, QAction, QStatusBar, QSpinBox, QCheckBox)
from PyQt5.QtCore import Qt, QPoint, QRect, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPixmap, QImage
import math


class TikZNode:
    """Represents a node in the TikZ diagram"""
    def __init__(self, name, x, y, text, style_type):
        self.name = name
        self.x = x
        self.y = y
        self.text = text
        self.style_type = style_type
        self.selected = False
        
        # Calculate size based on text content (text should already be cleaned)
        text_lines = [line.strip() for line in text.split('\n') if line.strip()]
        max_line_length = max([len(line) for line in text_lines]) if text_lines else 10
        
        # Adjust width and height based on content
        base_width = max(120, min(250, max_line_length * 8))
        base_height = max(50, len(text_lines) * 20 + 20)
        
        # Ellipses need more horizontal space than rectangles for the same text
        if style_type == "ellipse":
            self.width = int(base_width * 1.4)  # Ellipses are wider
            self.height = base_height
        else:
            self.width = base_width
            self.height = base_height
        
    def contains_point(self, px, py):
        """Check if point is within node bounds"""
        return (self.x - self.width/2 <= px <= self.x + self.width/2 and
                self.y - self.height/2 <= py <= self.y + self.height/2)
    
    def get_rect(self):
        """Get bounding rectangle"""
        return QRect(int(self.x - self.width/2), int(self.y - self.height/2),
                    int(self.width), int(self.height))


class TikZConnection:
    """Represents a connection/arrow between nodes"""
    def __init__(self, from_node, to_node, style="arrow"):
        self.from_node = from_node
        self.to_node = to_node
        self.style = style  # "arrow", "dashed", etc.


class TikZBackgroundGroup:
    """Represents a background grouping box (fit node)"""
    def __init__(self, name, x, y, width, height, style_str, fit_nodes, inner_sep=0.3):
        self.name = name
        self.x = x  # Center X
        self.y = y  # Center Y
        self.width = width
        self.height = height
        self.style_str = style_str  # Original style string (fill, draw, etc.)
        self.fit_nodes = fit_nodes  # List of node names this box fits around
        self.inner_sep = inner_sep  # Inner separation in cm
        self.selected = False
        self.is_resizing = False
        self.resize_handle = None  # Which corner/edge is being resized
        
    def contains_point(self, px, py):
        """Check if point is within box bounds"""
        return (self.x - self.width/2 <= px <= self.x + self.width/2 and
                self.y - self.height/2 <= py <= self.y + self.height/2)
    
    def get_rect(self):
        """Get bounding rectangle"""
        return QRect(int(self.x - self.width/2), int(self.y - self.height/2),
                    int(self.width), int(self.height))
    
    def get_resize_handle_at(self, px, py, handle_size=8):
        """Check if point is on a resize handle"""
        handles = {
            'nw': (self.x - self.width/2, self.y - self.height/2),  # Top-left
            'ne': (self.x + self.width/2, self.y - self.height/2),  # Top-right
            'sw': (self.x - self.width/2, self.y + self.height/2),  # Bottom-left
            'se': (self.x + self.width/2, self.y + self.height/2),  # Bottom-right
            'n': (self.x, self.y - self.height/2),  # Top
            's': (self.x, self.y + self.height/2),  # Bottom
            'w': (self.x - self.width/2, self.y),  # Left
            'e': (self.x + self.width/2, self.y),  # Right
        }
        for handle_name, (hx, hy) in handles.items():
            if abs(px - hx) < handle_size and abs(py - hy) < handle_size:
                return handle_name
        return None


class TikZCanvas(QWidget):
    """Canvas widget for rendering and editing TikZ diagrams"""
    
    node_selected = pyqtSignal(str)
    position_changed = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.nodes = []
        self.connections = []
        self.background_groups = []  # Background grouping boxes
        self.selected_node = None
        self.drag_node = None
        self.drag_group = None  # Dragging a background group
        self.drag_offset_x = 0.0  # Store as float for precision
        self.drag_offset_y = 0.0
        self.show_grid = True
        self.snap_to_grid = False  # Toggle for grid snapping during drag
        self.grid_size = 20
        self.snap_threshold = 10  # Pixels - distance threshold for alignment snapping
        self.alignment_guides = []  # Store alignment guides for visual feedback
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.setMinimumSize(800, 600)
        self.setMouseTracking(True)
        
        # Zoom and pan
        self.zoom_level = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0
        self.pan_start = QPoint(0, 0)
        self.pan_active = False
        self.pan_button = Qt.MiddleButton  # Middle mouse button for panning
        
    def parse_tikz_code(self, code):
        """Parse TikZ code and extract nodes and connections"""
        self.nodes = []
        self.connections = []
        self.background_groups = []  # Clear previous background groups
        # Store original code for export (preserve structure)
        self.original_code = code
        
        # First pass: Extract all node definitions (both absolute and relative)
        # Use manual parsing to handle nested braces in text content
        node_data = []
        found_names = set()
        
        # Debug: print found nodes
        print(f"Parsing TikZ code, looking for nodes...")
        
        # Find all \node[ patterns and parse manually to handle nested braces
        i = 0
        while i < len(code):
            # Find next \node[
            node_start = code.find('\\node[', i)
            if node_start == -1:
                break
            
            # Find the matching ]
            bracket_end = code.find(']', node_start)
            if bracket_end == -1:
                i = node_start + 1
                continue
            
            style_str = code[node_start + 6:bracket_end]  # Skip "\node["
            
            # Find the (name) part
            paren_start = code.find('(', bracket_end)
            if paren_start == -1:
                i = bracket_end + 1
                continue
            
            paren_end = code.find(')', paren_start)
            if paren_end == -1:
                i = paren_start + 1
                continue
            
            name = code[paren_start + 1:paren_end]
            
            # Find position string (everything between ) and {)
            brace_start = code.find('{', paren_end)
            if brace_start == -1:
                i = paren_end + 1
                continue
            
            position_str = code[paren_end + 1:brace_start].strip()
            
            # Now find the matching closing brace for the text content
            # We need to count braces to handle nested content like \textbf{AWS}\\small EC2 GPU
            brace_count = 1
            text_start = brace_start + 1
            text_end = text_start
            
            while text_end < len(code) and brace_count > 0:
                if code[text_end] == '{':
                    brace_count += 1
                elif code[text_end] == '}':
                    brace_count -= 1
                text_end += 1
            
            if brace_count == 0:
                text = code[text_start:text_end - 1]  # Exclude the closing }
            else:
                # Didn't find matching brace, skip this node
                i = brace_start + 1
                continue
            
            i = text_end  # Move past this node
            
            if name in found_names:
                continue  # Skip duplicates
            found_names.add(name)
            
            # Store original text before cleaning
            original_text = text
            
            print(f"  Raw node: {name}, position: '{position_str[:60]}', text: '{text[:60]}'")
            
            # Clean up text - handle LaTeX commands properly
            # Handle \textbf{} - extract text (will be bold in rendering)
            while '\\textbf{' in text or '\\textbf' in text:
                text = re.sub(r'\\textbf\{([^}]+)\}', r'\1', text)
                text = re.sub(r'\\textbf([^{])', r'\1', text)
            # Handle \small (can be \\small or \small) - convert to newline
            text = re.sub(r'\\+small\s*', '\n', text)
            # Replace \\ with newline (for line breaks) - but be careful with escaped backslashes
            # First handle double backslashes that are actual line breaks
            text = re.sub(r'\\\\(?!\\)', '\n', text)  # Replace \\ with \n, but not \\\\
            # Clean up any remaining LaTeX commands with braces
            text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', text)
            # Remove standalone LaTeX commands
            text = re.sub(r'\\[a-zA-Z]+\s*', '', text)
            # Remove any remaining single backslashes (escapes)
            text = text.replace('\\', '')
            text = text.strip()
            
            print(f"  Cleaned text: '{text}'")
            
            # Determine style type
            style_type = "rectangle"
            if "cloud" in style_str or "ellipse" in style_str:
                style_type = "ellipse"
            elif "cylinder" in style_str or "db" in style_str:
                style_type = "cylinder"
            elif "k8s" in style_str:
                style_type = "dashed_rect"
            elif "api" in style_str:
                style_type = "yellow_rect"
            
            # Parse position
            x, y = None, None
            relative_to = None
            xshift = 0
            yshift = 0
            
            # Check for absolute position: at (x,y)
            at_match = re.search(r'at\s*\(([^)]+)\)', position_str)
            if at_match:
                coords = at_match.group(1).replace('cm', '').strip()
                parts = coords.split(',')
                if len(parts) == 2:
                    try:
                        # Convert TikZ coordinates to pixel coordinates
                        # TikZ: (x_cm, y_cm) -> Pixel: (x_cm * 50 + 400, -y_cm * 50 + 300)
                        scale_factor = 50  # pixels per cm
                        canvas_center_x = 400
                        canvas_center_y = 300
                        x = float(parts[0].strip()) * scale_factor + canvas_center_x
                        y = -float(parts[1].strip()) * scale_factor + canvas_center_y
                    except:
                        pass
            
            # Check for relative positioning (can be combined with absolute)
            # Use more flexible regex to handle whitespace
            above_match = re.search(r'above=of\s+(\w+)', position_str)
            below_match = re.search(r'below=of\s+(\w+)', position_str)
            left_match = re.search(r'left=of\s+(\w+)', position_str)
            right_match = re.search(r'right=of\s+(\w+)', position_str)
            
            if above_match:
                relative_to = above_match.group(1).strip()
                if yshift == 0:  # Only set default if not already set
                    yshift = 1.5  # Default offset in cm
                print(f"    Found above=of {relative_to}")
            elif below_match:
                relative_to = below_match.group(1).strip()
                if yshift == 0:
                    yshift = -2.0  # Default offset in cm (negative = below) - increased for better spacing
                print(f"    Found below=of {relative_to}")
            elif left_match:
                relative_to = left_match.group(1).strip()
                if xshift == 0:
                    xshift = -2.0  # Default offset in cm (negative = left)
                print(f"    Found left=of {relative_to}")
            elif right_match:
                relative_to = right_match.group(1).strip()
                if xshift == 0:
                    xshift = 2.0  # Default offset in cm (positive = right)
                print(f"    Found right=of {relative_to}")
            
            # Parse shifts (must come AFTER relative positioning to override defaults)
            xshift_match = re.search(r'xshift=([-\d.]+)cm', position_str)
            yshift_match = re.search(r'yshift=([-\d.]+)cm', position_str)
            if xshift_match:
                xshift = float(xshift_match.group(1))
                print(f"    Found xshift: {xshift}cm = {xshift * 50}px")
            if yshift_match:
                yshift = float(yshift_match.group(1))
                print(f"    Found yshift: {yshift}cm = {-yshift * 50}px")
            
            node_data.append({
                'name': name,
                'style_type': style_type,
                'text': text,  # Cleaned text for display
                'x': x,
                'y': y,
                'relative_to': relative_to,
                'xshift': xshift * 50,  # Convert to pixels
                'yshift': -yshift * 50,  # Invert Y and convert
                'position_str': position_str,  # Keep original for debugging
                'original_style': style_str,  # Keep original style string
                'original_text': original_text  # Keep original text before cleaning
            })
            print(f"  Parsed node: {name}, x={x}, y={y}, relative_to={relative_to}, xshift={xshift*50:.1f}px, yshift={-yshift*50:.1f}px, pos='{position_str[:40]}'")
        
        # Second pass: Resolve relative positions
        node_dict = {}
        
        # First, add all nodes with absolute positions ONLY (no relative positioning)
        for data in node_data:
            if data['x'] is not None and data['y'] is not None and not data['relative_to']:
                # Absolute position without relative - add immediately
                node = TikZNode(data['name'], data['x'], data['y'], data['text'], data['style_type'])
                node_dict[data['name']] = node
                self.nodes.append(node)
                print(f"  Added absolute node: {data['name']} at ({data['x']}, {data['y']})")
        
        print(f"  Initial node_dict has {len(node_dict)} nodes: {list(node_dict.keys())}")
        
        # Third pass: Resolve relative positions iteratively
        max_iterations = 20
        for iteration in range(max_iterations):
            progress = False
            unresolved = []
            
            print(f"\n  Iteration {iteration + 1}:")
            for data in node_data:
                if data['name'] in node_dict:
                    continue  # Already resolved
                
                # If has relative_to, try to resolve
                if data.get('relative_to'):
                    ref_name = data['relative_to'].strip()
                    if ref_name in node_dict:
                        ref_node = node_dict[ref_name]
                        # Calculate position relative to reference node
                        # For below=of and above=of: center horizontally on reference, then apply xshift
                        # For left=of and right=of: center vertically on reference, then apply yshift
                        # The reference node's x,y is already its center point
                        x = ref_node.x + data['xshift']
                        y = ref_node.y + data['yshift']
                        node = TikZNode(data['name'], x, y, data['text'], data['style_type'])
                        node_dict[data['name']] = node
                        self.nodes.append(node)
                        print(f"    ✓ Resolved: {data['name']} relative to '{ref_name}' -> ({x:.1f}, {y:.1f})")
                        progress = True
                    else:
                        # Reference node not found yet, keep for next iteration
                        unresolved.append(data)
                        print(f"    ✗ Waiting: {data['name']} needs '{ref_name}' (available: {list(node_dict.keys())})")
                elif data['x'] is not None and data['y'] is not None:
                    # Absolute position (might have been skipped if it also had relative_to)
                    node = TikZNode(data['name'], data['x'], data['y'], data['text'], data['style_type'])
                    node_dict[data['name']] = node
                    self.nodes.append(node)
                    print(f"    ✓ Added absolute: {data['name']} at ({data['x']}, {data['y']})")
                    progress = True
                else:
                    unresolved.append(data)
                    print(f"    ✗ No position info for: {data['name']}")
            
            if not progress:
                print(f"  No progress in iteration {iteration + 1}, stopping")
                break
            if not unresolved:
                print(f"  All nodes resolved in iteration {iteration + 1}!")
                break
        
        # If still unresolved, use smart autolayout
        if unresolved:
            print(f"\n  Applying smart autolayout for {len(unresolved)} unresolved nodes...")
            self._apply_autolayout(unresolved, node_dict, node_data)
        
        # Store node dict for connection resolution
        self.node_dict = node_dict
        
        print(f"\nSummary: Found {len(node_data)} node definitions, resolved {len(self.nodes)} nodes")
        print(f"Resolved node names: {[n.name for n in self.nodes]}")
        print(f"Available reference nodes in dict: {list(node_dict.keys())}")
        
        # Check for unresolved nodes with relative positioning
        unresolved_with_ref = [d for d in node_data if d['name'] not in node_dict and d['relative_to']]
        if unresolved_with_ref:
            print(f"\nWARNING: {len(unresolved_with_ref)} nodes with relative positioning could not be resolved:")
            for d in unresolved_with_ref:
                print(f"  - {d['name']} (relative_to: '{d['relative_to']}') - reference node not found!")
        
        # Extract connections
        arrow_pattern = r'\\draw\[([^\]]*)\]\s*\(([^)]+)\)\s*--\s*\(([^)]+)\)'
        for match in re.finditer(arrow_pattern, code):
            style = match.group(1)
            from_name = match.group(2)
            to_name = match.group(3)
            
            from_node = next((n for n in self.nodes if n.name == from_name), None)
            to_node = next((n for n in self.nodes if n.name == to_name), None)
            
            if from_node and to_node:
                conn_style = "dashed" if "dashed" in style else "arrow"
                self.connections.append(TikZConnection(from_node, to_node, conn_style))
        
        # Parse background groups (fit nodes) after all nodes are resolved
        self._parse_background_groups(code)
        
        self.update()
    
    def _parse_background_groups(self, code):
        """Parse background grouping boxes (fit nodes) from TikZ code"""
        print(f"  Parsing background groups...")
        # Find scope blocks with on background layer
        scope_start = 0
        scope_count = 0
        while True:
            scope_start = code.find('\\begin{scope}', scope_start)
            if scope_start == -1:
                break
            
            scope_count += 1
            # Check if this scope has "on background layer"
            scope_end = code.find('\\end{scope}', scope_start)
            if scope_end == -1:
                break
            
            scope_content = code[scope_start:scope_end]
            print(f"  Found scope block {scope_count}, checking for 'on background layer'...")
            
            if 'on background layer' in scope_content:
                print(f"  Scope {scope_count} has 'on background layer'")
                # Find fit nodes in this scope
                # Pattern: fit= can be in style brackets: \node[..., fit=(nodes), ...] (name) {...}
                # OR after node name: \node[...] (name) fit=(nodes) {...}
                
                # First, find all \node[ patterns in the scope
                node_start = 0
                while True:
                    node_start = scope_content.find('\\node[', node_start)
                    if node_start == -1:
                        break
                    
                    # Find the matching closing bracket for style
                    bracket_start = node_start + 6  # Skip "\node["
                    bracket_end = scope_content.find(']', bracket_start)
                    if bracket_end == -1:
                        node_start += 1
                        continue
                    
                    style_str = scope_content[bracket_start:bracket_end]
                    
                    # Check if fit= is in the style string
                    fit_match = re.search(r'fit\s*=\s*\(([^)]+)\)', style_str)
                    if fit_match:
                        fit_nodes_str = fit_match.group(1)
                        
                        # Find the node name after the style bracket
                        name_start = scope_content.find('(', bracket_end)
                        if name_start == -1:
                            node_start = bracket_end + 1
                            continue
                        name_end = scope_content.find(')', name_start)
                        if name_end == -1:
                            node_start = bracket_end + 1
                            continue
                        
                        name = scope_content[name_start + 1:name_end]
                        
                        print(f"    Found fit node: {name}, fit_nodes_str: '{fit_nodes_str}'")
                        
                        # Parse fit node names (can be space or comma separated, with parentheses)
                        # Handle format: (api) (orchestrator) (chat) or api, orchestrator, chat
                        fit_nodes = []
                        # Try to extract node names from parentheses first
                        paren_matches = re.findall(r'\(([^)]+)\)', fit_nodes_str)
                        if paren_matches:
                            fit_nodes = [n.strip() for n in paren_matches if n.strip()]
                        else:
                            # Fallback: split by comma or space
                            fit_nodes = [n.strip() for n in re.split(r'[,\s]+', fit_nodes_str) if n.strip()]
                        
                        # Extract inner_sep if present
                        inner_sep_match = re.search(r'inner\s+sep=([\d.]+)cm', style_str)
                        inner_sep = float(inner_sep_match.group(1)) if inner_sep_match else 0.3
                        
                        # Calculate bounding box from fit nodes
                        if fit_nodes:
                            # Find all referenced nodes
                            referenced_nodes = [n for n in self.nodes if n.name in fit_nodes]
                            print(f"    Found {len(referenced_nodes)}/{len(fit_nodes)} referenced nodes: {[n.name for n in referenced_nodes]}")
                            
                            if referenced_nodes:
                                # Calculate bounding box
                                min_x = min(n.x - n.width/2 for n in referenced_nodes)
                                max_x = max(n.x + n.width/2 for n in referenced_nodes)
                                min_y = min(n.y - n.height/2 for n in referenced_nodes)
                                max_y = max(n.y + n.height/2 for n in referenced_nodes)
                                
                                # Add inner_sep padding (convert cm to pixels: 1cm = 50px)
                                padding = inner_sep * 50
                                width = (max_x - min_x) + 2 * padding
                                height = (max_y - min_y) + 2 * padding
                                center_x = (min_x + max_x) / 2
                                center_y = (min_y + max_y) / 2
                                
                                # Create background group
                                bg_group = TikZBackgroundGroup(
                                    name=name,
                                    x=center_x,
                                    y=center_y,
                                    width=width,
                                    height=height,
                                    style_str=style_str,
                                    fit_nodes=fit_nodes,
                                    inner_sep=inner_sep
                                )
                                self.background_groups.append(bg_group)
                                print(f"  ✓ Parsed background group: {name} fitting {fit_nodes} at ({center_x:.1f}, {center_y:.1f}), size ({width:.1f}, {height:.1f})")
                            else:
                                print(f"  ✗ No referenced nodes found for fit nodes: {fit_nodes}")
                                print(f"    Available node names: {[n.name for n in self.nodes]}")
                        else:
                            print(f"  ✗ No fit nodes parsed from: '{fit_nodes_str}'")
                    
                    node_start = bracket_end + 1
            
            scope_start = scope_end + 1
        
        print(f"  Total background groups parsed: {len(self.background_groups)}")
    
    def _apply_autolayout(self, unresolved, node_dict, all_node_data):
        """Apply smart autolayout for unresolved nodes based on their relationships"""
        # Try to resolve based on position_str parsing and relationships
        max_iterations = 10
        for iteration in range(max_iterations):
            progress = False
            still_unresolved = []
            
            for data in unresolved:
                if data['name'] in node_dict:
                    continue
                
                # First, try to parse relative positioning from position_str if relative_to wasn't set
                if not data.get('relative_to') and data.get('position_str'):
                    pos_str = data['position_str']
                    # Try to extract relative positioning
                    above_match = re.search(r'above=of\s+(\w+)', pos_str)
                    below_match = re.search(r'below=of\s+(\w+)', pos_str)
                    left_match = re.search(r'left=of\s+(\w+)', pos_str)
                    right_match = re.search(r'right=of\s+(\w+)', pos_str)
                    
                    ref_name = None
                    if above_match:
                        ref_name = above_match.group(1).strip()
                        if 'yshift' not in data or data.get('yshift', 0) == 0:
                            data['yshift'] = 75  # 1.5cm default in pixels
                    elif below_match:
                        ref_name = below_match.group(1).strip()
                        if 'yshift' not in data or data.get('yshift', 0) == 0:
                            data['yshift'] = -100  # -2.0cm default in pixels
                    elif left_match:
                        ref_name = left_match.group(1).strip()
                        if 'xshift' not in data or data.get('xshift', 0) == 0:
                            data['xshift'] = -100  # -2.0cm default in pixels
                    elif right_match:
                        ref_name = right_match.group(1).strip()
                        if 'xshift' not in data or data.get('xshift', 0) == 0:
                            data['xshift'] = 100  # 2.0cm default in pixels
                    
                    # Parse shifts from position string
                    xshift_match = re.search(r'xshift=([-\d.]+)cm', pos_str)
                    yshift_match = re.search(r'yshift=([-\d.]+)cm', pos_str)
                    if xshift_match:
                        data['xshift'] = float(xshift_match.group(1)) * 50
                    if yshift_match:
                        data['yshift'] = -float(yshift_match.group(1)) * 50
                    
                    if ref_name:
                        data['relative_to'] = ref_name
                        print(f"    Parsed relative positioning: {data['name']} -> {ref_name}")
                
                # Try to find reference node by name matching
                if data.get('relative_to'):
                    ref_name = data['relative_to'].strip()
                    # Try exact match first
                    if ref_name in node_dict:
                        ref_node = node_dict[ref_name]
                        x = ref_node.x + data.get('xshift', 0)
                        y = ref_node.y + data.get('yshift', 0)
                        # Snap to grid with alignment
                        x, y = self._snap_autolayout_position(x, y)
                        node = TikZNode(data['name'], x, y, data['text'], data['style_type'])
                        node_dict[data['name']] = node
                        self.nodes.append(node)
                        print(f"    ✓ Autolayout resolved: {data['name']} relative to '{ref_name}' -> ({x:.1f}, {y:.1f})")
                        progress = True
                        continue
                    # Try case-insensitive match
                    for existing_name in node_dict.keys():
                        if existing_name.lower() == ref_name.lower():
                            ref_node = node_dict[existing_name]
                            x = ref_node.x + data.get('xshift', 0)
                            y = ref_node.y + data.get('yshift', 0)
                            # Snap to grid with alignment
                            x, y = self._snap_autolayout_position(x, y)
                            node = TikZNode(data['name'], x, y, data['text'], data['style_type'])
                            node_dict[data['name']] = node
                            self.nodes.append(node)
                            print(f"    ✓ Autolayout resolved (case-insensitive): {data['name']} relative to '{existing_name}' -> ({x:.1f}, {y:.1f})")
                            progress = True
                            break
                    if data['name'] in node_dict:
                        continue
                
                # Try to infer position from connections
                connections_to_this = [c for c in self.connections if c.to_node.name == data['name']]
                connections_from_this = [c for c in self.connections if c.from_node.name == data['name']]
                
                if connections_to_this:
                    # Position relative to source node
                    source_node = connections_to_this[0].from_node
                    x = source_node.x + 150  # Default offset
                    y = source_node.y + 100
                    # Snap to grid with alignment
                    x, y = self._snap_autolayout_position(x, y)
                    node = TikZNode(data['name'], x, y, data['text'], data['style_type'])
                    node_dict[data['name']] = node
                    self.nodes.append(node)
                    print(f"    ✓ Autolayout from connection: {data['name']} -> ({x:.1f}, {y:.1f})")
                    progress = True
                    continue
                
                still_unresolved.append(data)
            
            unresolved = still_unresolved
            if not progress or not unresolved:
                break
        
        # Final fallback: position remaining nodes in a grid
        if unresolved:
            print(f"    Applying grid layout for {len(unresolved)} remaining nodes...")
            grid_cols = 4
            for i, data in enumerate(unresolved):
                if data['name'] not in node_dict:
                    col = i % grid_cols
                    row = i // grid_cols
                    x = 400 + (col - grid_cols/2) * 150
                    y = 500 + row * 100
                    # Snap to grid with alignment
                    x, y = self._snap_autolayout_position(x, y)
                    node = TikZNode(data['name'], x, y, data['text'], data['style_type'])
                    node_dict[data['name']] = node
                    self.nodes.append(node)
                    print(f"    ✓ Grid layout: {data['name']} -> ({x:.1f}, {y:.1f})")
    
    def _snap_autolayout_position(self, x, y):
        """Snap autolayout position to grid with alignment detection"""
        # First snap to grid
        x = round(x / self.grid_size) * self.grid_size
        y = round(y / self.grid_size) * self.grid_size
        
        # Then check for alignment with existing nodes (if snap_to_grid is enabled)
        if self.snap_to_grid:
            # Find alignment candidates
            candidates = self.find_alignment_candidates(x, y, None)
            
            # Prioritize horizontal alignment
            if candidates['horizontal']:
                # Use the most common Y coordinate
                y_values = [align_y for _, align_y in candidates['horizontal']]
                y = round(sum(y_values) / len(y_values) / self.grid_size) * self.grid_size
            
            # Then vertical alignment
            if candidates['vertical']:
                x_values = [align_x for _, align_x in candidates['vertical']]
                x = round(sum(x_values) / len(x_values) / self.grid_size) * self.grid_size
        
        return x, y
    
    def paintEvent(self, event):
        """Paint the canvas"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Save painter state and apply transformation
        painter.save()
        painter.translate(self.offset_x, self.offset_y)
        painter.scale(self.zoom_level, self.zoom_level)
        
        # Draw grid (in world coordinates)
        if self.show_grid:
            # Calculate visible area in world coordinates
            inv_zoom = 1.0 / self.zoom_level if self.zoom_level > 0 else 1.0
            world_left = -self.offset_x * inv_zoom
            world_right = (self.width() - self.offset_x) * inv_zoom
            world_top = -self.offset_y * inv_zoom
            world_bottom = (self.height() - self.offset_y) * inv_zoom
            
            # Draw grid lines
            pen = QPen(QColor(200, 200, 200), max(0.5, 1.0 * inv_zoom), Qt.DashLine)
            painter.setPen(pen)
            
            # Horizontal grid lines
            start_y = int(world_top // self.grid_size) * self.grid_size
            end_y = int(world_bottom) + self.grid_size
            for y in range(start_y, end_y, self.grid_size):
                painter.drawLine(int(world_left), y, int(world_right), y)
            
            # Vertical grid lines
            start_x = int(world_left // self.grid_size) * self.grid_size
            end_x = int(world_right) + self.grid_size
            for x in range(start_x, end_x, self.grid_size):
                painter.drawLine(x, int(world_top), x, int(world_bottom))
        
        # Draw background groups first (behind everything)
        for bg_group in self.background_groups:
            group_rect = bg_group.get_rect()
            
            # Parse style for fill and draw colors
            fill_color = QColor(173, 216, 230, 50)  # Default light blue with transparency
            draw_color = QColor(100, 150, 200, 150)  # Default blue border
            is_dashed = False
            
            # Extract fill color
            fill_match = re.search(r'fill=([^,}]+)', bg_group.style_str)
            if fill_match:
                fill_str = fill_match.group(1).strip()
                # Handle color!opacity format
                if '!' in fill_str:
                    color_name, opacity = fill_str.split('!')
                    opacity_val = int(opacity) if opacity.isdigit() else 20
                    if 'blue' in color_name.lower():
                        fill_color = QColor(173, 216, 230, int(255 * opacity_val / 100))
                    elif 'green' in color_name.lower():
                        fill_color = QColor(144, 238, 144, int(255 * opacity_val / 100))
                    else:
                        fill_color = QColor(200, 200, 200, int(255 * opacity_val / 100))
            
            # Extract draw color
            draw_match = re.search(r'draw=([^,}]+)', bg_group.style_str)
            if draw_match:
                draw_str = draw_match.group(1).strip()
                if 'blue' in draw_str.lower():
                    draw_color = QColor(100, 150, 200, 200)
                elif 'green' in draw_str.lower():
                    draw_color = QColor(50, 150, 50, 200)
            
            # Check for dashed
            if 'dashed' in bg_group.style_str:
                is_dashed = True
            
            # Draw filled rectangle
            brush = QBrush(fill_color)
            pen = QPen(draw_color, max(1, 2 * inv_zoom))
            if is_dashed:
                pen.setStyle(Qt.DashLine)
            painter.setBrush(brush)
            painter.setPen(pen)
            
            # Draw rounded rectangle if specified
            if 'rounded corners' in bg_group.style_str:
                corner_radius = max(2, 5 * inv_zoom)
                painter.drawRoundedRect(group_rect, corner_radius, corner_radius)
            else:
                painter.drawRect(group_rect)
            
            # Draw selection highlight and resize handles
            if bg_group.selected:
                highlight_pen = QPen(QColor(255, 0, 0), max(1, 3 * inv_zoom))
                painter.setPen(highlight_pen)
                painter.setBrush(QBrush())
                adjust = int(max(1, 2 * inv_zoom))
                painter.drawRect(group_rect.adjusted(-adjust, -adjust, adjust, adjust))
                
                # Draw resize handles
                handle_size = max(4, 6 * inv_zoom)
                handles = [
                    (group_rect.left(), group_rect.top()),  # NW
                    (group_rect.right(), group_rect.top()),  # NE
                    (group_rect.left(), group_rect.bottom()),  # SW
                    (group_rect.right(), group_rect.bottom()),  # SE
                ]
                painter.setBrush(QBrush(QColor(255, 0, 0)))
                for hx, hy in handles:
                    painter.drawRect(int(hx - handle_size/2), int(hy - handle_size/2),
                                    int(handle_size), int(handle_size))
        
        # Draw connections (behind nodes)
        for conn in self.connections:
            from_rect = conn.from_node.get_rect()
            to_rect = conn.to_node.get_rect()
            
            from_center = from_rect.center()
            to_center = to_rect.center()
            
            inv_zoom = 1.0 / self.zoom_level if self.zoom_level > 0 else 1.0
            pen = QPen(QColor(100, 100, 100), max(1, 2 * inv_zoom))
            if conn.style == "dashed":
                pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            
            # Draw arrow
            painter.drawLine(from_center, to_center)
            # Simple arrowhead (scale with zoom)
            angle = math.atan2(float(to_center.y() - from_center.y()), 
                             float(to_center.x() - from_center.x()))
            arrow_size = max(5, 10 * inv_zoom)
            arrow_x1 = int(to_center.x() - arrow_size * math.cos(angle - 0.5))
            arrow_y1 = int(to_center.y() - arrow_size * math.sin(angle - 0.5))
            arrow_x2 = int(to_center.x() - arrow_size * math.cos(angle + 0.5))
            arrow_y2 = int(to_center.y() - arrow_size * math.sin(angle + 0.5))
            painter.drawLine(to_center, QPoint(arrow_x1, arrow_y1))
            painter.drawLine(to_center, QPoint(arrow_x2, arrow_y2))
        
        # Draw nodes
        for node in self.nodes:
            rect = node.get_rect()
            
            # Select color based on style
            if node.style_type == "ellipse":
                color = QColor(173, 216, 230)  # Light blue
            elif node.style_type == "cylinder":
                color = QColor(221, 160, 221)  # Plum
            elif node.style_type == "dashed_rect":
                color = QColor(144, 238, 144)  # Light green
            elif node.style_type == "yellow_rect":
                color = QColor(255, 255, 200)  # Light yellow
            else:
                color = QColor(255, 218, 185)  # Peach
            
            # Draw node shape
            brush = QBrush(color)
            inv_zoom = 1.0 / self.zoom_level if self.zoom_level > 0 else 1.0
            pen = QPen(QColor(0, 0, 0), max(1, 2 * inv_zoom))
            if node.style_type == "dashed_rect":
                pen.setStyle(Qt.DashLine)
            
            painter.setBrush(brush)
            painter.setPen(pen)
            
            if node.style_type == "ellipse":
                painter.drawEllipse(rect)
            elif node.style_type == "cylinder":
                # Draw cylinder shape
                painter.drawEllipse(rect.x(), rect.y(), rect.width(), rect.height() // 3)
                painter.drawRect(rect.x(), rect.y() + rect.height() // 6, 
                               rect.width(), rect.height() * 2 // 3)
            else:
                corner_radius = max(2, 5 * inv_zoom)
                painter.drawRoundedRect(rect, corner_radius, corner_radius)
            
            # Draw text (scale font size with zoom - keep readable)
            painter.setPen(QPen(QColor(0, 0, 0)))
            # Font size should scale with zoom but have reasonable min/max
            base_font_size = 9
            font_size = max(6, min(24, int(base_font_size * self.zoom_level)))
            font = QFont("Arial", font_size)
            painter.setFont(font)
            
            # Handle multi-line text (split by \n)
            # Clean text one more time in case any LaTeX commands slipped through
            clean_text = node.text
            # Remove any remaining LaTeX commands
            clean_text = re.sub(r'\\textbf\{([^}]+)\}', r'\1', clean_text)
            clean_text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', clean_text)
            clean_text = re.sub(r'\\[a-zA-Z]+\s*', '', clean_text)
            clean_text = clean_text.replace('\\', '')
            
            text_lines = [line.strip() for line in clean_text.split('\n') if line.strip()]
            
            if text_lines:
                # Calculate text height
                line_height = 14
                total_height = len(text_lines) * line_height
                start_y = rect.y() + (rect.height() - total_height) / 2 + line_height
                
                for i, line in enumerate(text_lines):
                    # Make first line bold if it looks like a title (and has multiple lines)
                    if i == 0 and len(text_lines) > 1:
                        bold_font = QFont(font)
                        bold_font.setBold(True)
                        bold_font.setPointSize(10)
                        painter.setFont(bold_font)
                    else:
                        small_font = QFont(font)
                        small_font.setPointSize(8)
                        painter.setFont(small_font)
                    
                    painter.drawText(rect.x(), int(start_y + i * line_height), 
                                   rect.width(), line_height,
                                   Qt.AlignCenter | Qt.AlignVCenter, line)
            
            # Draw selection highlight
            if node.selected:
                inv_zoom = 1.0 / self.zoom_level if self.zoom_level > 0 else 1.0
                highlight_width = max(1, 3 * inv_zoom)
                painter.setPen(QPen(QColor(255, 0, 0), highlight_width))
                painter.setBrush(QBrush())
                adjust = int(max(1, 2 * inv_zoom))
                painter.drawRect(rect.adjusted(-adjust, -adjust, adjust, adjust))
        
        # Draw alignment guides if snapping and dragging
        if self.snap_to_grid and self.drag_node:
            guide_pen = QPen(QColor(0, 150, 255), max(1, 2 / self.zoom_level), Qt.DashLine)
            painter.setPen(guide_pen)
            
            candidates = self.find_alignment_candidates(self.drag_node.x, self.drag_node.y, self.drag_node)
            
            # Calculate visible area in world coordinates
            inv_zoom = 1.0 / self.zoom_level if self.zoom_level > 0 else 1.0
            world_left = -self.offset_x * inv_zoom
            world_right = (self.width() - self.offset_x) * inv_zoom
            world_top = -self.offset_y * inv_zoom
            world_bottom = (self.height() - self.offset_y) * inv_zoom
            
            # Draw horizontal guides
            for node, align_y in candidates['horizontal']:
                painter.drawLine(int(world_left), int(align_y), int(world_right), int(align_y))
            
            # Draw vertical guides
            for node, align_x in candidates['vertical']:
                painter.drawLine(int(align_x), int(world_top), int(align_x), int(world_bottom))
            
            # Draw diagonal guides (45 and 135 degrees) - simplified for now
            for node, align_x, align_y in candidates['diagonal_45']:
                # 45-degree line: y = x + c, where c = align_y - align_x
                c = align_y - align_x
                # Draw line segment within visible area
                x1 = max(world_left, world_top - c)
                y1 = x1 + c
                x2 = min(world_right, world_bottom - c)
                y2 = x2 + c
                if x1 < x2 and y1 >= world_top and y2 <= world_bottom:
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))
            
            for node, align_x, align_y in candidates['diagonal_135']:
                # 135-degree line: y = -x + c, where c = align_y + align_x
                c = align_y + align_x
                # Draw line segment within visible area
                x1 = max(world_left, c - world_bottom)
                y1 = -x1 + c
                x2 = min(world_right, c - world_top)
                y2 = -x2 + c
                if x1 < x2 and y1 >= world_top and y2 <= world_bottom:
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        
        # Restore painter state
        painter.restore()
    
    def mousePressEvent(self, event):
        """Handle mouse press"""
        # Convert screen coordinates to world coordinates
        world_x, world_y = self.screen_to_world(event.x(), event.y())
        
        if event.button() == Qt.LeftButton:
            # First check for background group resize handles
            clicked_group = None
            resize_handle = None
            for bg_group in reversed(self.background_groups):
                handle = bg_group.get_resize_handle_at(world_x, world_y, handle_size=8 / self.zoom_level)
                if handle:
                    clicked_group = bg_group
                    resize_handle = handle
                    bg_group.is_resizing = True
                    bg_group.resize_handle = handle
                    break
            
            if clicked_group and resize_handle:
                # Deselect all
                for node in self.nodes:
                    node.selected = False
                for bg in self.background_groups:
                    bg.selected = False
                clicked_group.selected = True
                self.drag_group = clicked_group
                self.drag_offset_x = world_x - clicked_group.x
                self.drag_offset_y = world_y - clicked_group.y
                self.update()
                return
            
            # Check for background group click (but not on resize handle)
            if not clicked_group:
                for bg_group in reversed(self.background_groups):
                    if bg_group.contains_point(world_x, world_y):
                        clicked_group = bg_group
                        break
            
            if clicked_group:
                # Deselect all
                for node in self.nodes:
                    node.selected = False
                for bg in self.background_groups:
                    bg.selected = False
                clicked_group.selected = True
                self.drag_group = clicked_group
                self.drag_offset_x = world_x - clicked_group.x
                self.drag_offset_y = world_y - clicked_group.y
                self.update()
                return
            
            # Find clicked node
            clicked_node = None
            for node in reversed(self.nodes):  # Check from top to bottom
                if node.contains_point(world_x, world_y):
                    clicked_node = node
                    break
            
            if clicked_node:
                # Deselect all
                for node in self.nodes:
                    node.selected = False
                for bg in self.background_groups:
                    bg.selected = False
                clicked_node.selected = True
                self.selected_node = clicked_node
                self.drag_node = clicked_node
                
                # Calculate drag offset in world coordinates (store as float for precision)
                self.drag_offset_x = world_x - clicked_node.x
                self.drag_offset_y = world_y - clicked_node.y
                self.node_selected.emit(clicked_node.name)
            else:
                # Deselect all
                for node in self.nodes:
                    node.selected = False
                for bg in self.background_groups:
                    bg.selected = False
                self.selected_node = None
            
            self.update()
        elif event.button() == self.pan_button:
            # Start panning
            self.pan_active = True
            self.pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move (dragging)"""
        if self.pan_active and event.buttons() & self.pan_button:
            # Pan the canvas
            delta = event.pos() - self.pan_start
            self.offset_x += delta.x()
            self.offset_y += delta.y()
            self.pan_start = event.pos()
            self.update()
        elif self.drag_group and event.buttons() & Qt.LeftButton:
            # Convert screen coordinates to world coordinates
            world_x, world_y = self.screen_to_world(event.x(), event.y())
            
            if self.drag_group.is_resizing:
                # Resize the group
                handle = self.drag_group.resize_handle
                group_left = self.drag_group.x - self.drag_group.width/2
                group_right = self.drag_group.x + self.drag_group.width/2
                group_top = self.drag_group.y - self.drag_group.height/2
                group_bottom = self.drag_group.y + self.drag_group.height/2
                
                if 'n' in handle:  # North (top)
                    new_top = world_y
                    new_height = group_bottom - new_top
                    if new_height >= 20:
                        self.drag_group.height = new_height
                        self.drag_group.y = new_top + self.drag_group.height/2
                if 's' in handle:  # South (bottom)
                    new_bottom = world_y
                    new_height = new_bottom - group_top
                    if new_height >= 20:
                        self.drag_group.height = new_height
                        self.drag_group.y = group_top + self.drag_group.height/2
                if 'w' in handle:  # West (left)
                    new_left = world_x
                    new_width = group_right - new_left
                    if new_width >= 20:
                        self.drag_group.width = new_width
                        self.drag_group.x = new_left + self.drag_group.width/2
                if 'e' in handle:  # East (right)
                    new_right = world_x
                    new_width = new_right - group_left
                    if new_width >= 20:
                        self.drag_group.width = new_width
                        self.drag_group.x = group_left + self.drag_group.width/2
                
                # Apply strict alignment if enabled
                if self.snap_to_grid:
                    # Snap center position
                    self.drag_group.x, self.drag_group.y = self.apply_strict_alignment(
                        self.drag_group.x, self.drag_group.y)
                    # Snap dimensions to grid
                    self.drag_group.width = round(self.drag_group.width / self.grid_size) * self.grid_size
                    self.drag_group.height = round(self.drag_group.height / self.grid_size) * self.grid_size
                    
                    # Update fit_nodes after resize
                    self._update_group_fit_nodes(self.drag_group)
            else:
                # Move the group
                new_x = world_x - self.drag_offset_x
                new_y = world_y - self.drag_offset_y
                
                # Apply strict alignment if enabled
                if self.snap_to_grid:
                    new_x, new_y = self.apply_strict_alignment(new_x, new_y)
                
                self.drag_group.x = new_x
                self.drag_group.y = new_y
                
                # Update fit_nodes list based on which nodes are now within bounds
                self._update_group_fit_nodes(self.drag_group)
            
            self.position_changed.emit()
            self.update()
        elif self.drag_node and event.buttons() & Qt.LeftButton:
            # Convert screen coordinates to world coordinates
            world_x, world_y = self.screen_to_world(event.x(), event.y())
            
            # Apply drag offset to maintain relative position from click point
            # Use stored float offsets for precision
            new_x = world_x - self.drag_offset_x
            new_y = world_y - self.drag_offset_y
            
            # Apply strict alignment snapping if enabled
            if self.snap_to_grid:
                new_x, new_y = self.apply_strict_alignment(new_x, new_y)
            
            self.drag_node.x = new_x
            self.drag_node.y = new_y
            
            # Update background groups that contain this node
            self._update_background_groups_for_node(self.drag_node)
            
            self.position_changed.emit()
            self.update()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if event.button() == self.pan_button:
            self.pan_active = False
            self.setCursor(Qt.ArrowCursor)
        self.drag_node = None
        if self.drag_group:
            was_resizing = self.drag_group.is_resizing
            self.drag_group.is_resizing = False
            self.drag_group.resize_handle = None
            # Update fit_nodes when resizing or dragging is done
            if was_resizing:
                self._update_group_fit_nodes(self.drag_group)
        self.drag_group = None
        self.drag_offset_x = 0.0
        self.drag_offset_y = 0.0
    
    def _update_background_groups_for_node(self, node):
        """Update background groups when a node moves - recalculate bounds if node is in fit_nodes"""
        for bg_group in self.background_groups:
            if node.name in bg_group.fit_nodes:
                # Node is part of this group - recalculate bounding box
                referenced_nodes = [n for n in self.nodes if n.name in bg_group.fit_nodes]
                if referenced_nodes:
                    min_x = min(n.x - n.width/2 for n in referenced_nodes)
                    max_x = max(n.x + n.width/2 for n in referenced_nodes)
                    min_y = min(n.y - n.height/2 for n in referenced_nodes)
                    max_y = max(n.y + n.height/2 for n in referenced_nodes)
                    
                    padding = bg_group.inner_sep * 50
                    bg_group.width = (max_x - min_x) + 2 * padding
                    bg_group.height = (max_y - min_y) + 2 * padding
                    bg_group.x = (min_x + max_x) / 2
                    bg_group.y = (min_y + max_y) / 2
    
    def _update_group_fit_nodes(self, bg_group):
        """Update which nodes are within the background group's bounds"""
        group_rect = bg_group.get_rect()
        updated_fit_nodes = []
        
        for node in self.nodes:
            node_rect = node.get_rect()
            # Check if node center is within group bounds (with some tolerance)
            node_center = node_rect.center()
            if group_rect.contains(node_center):
                updated_fit_nodes.append(node.name)
        
        # Update fit_nodes if changed
        if set(updated_fit_nodes) != set(bg_group.fit_nodes):
            print(f"  Updated fit_nodes for {bg_group.name}: {bg_group.fit_nodes} -> {updated_fit_nodes}")
            bg_group.fit_nodes = updated_fit_nodes
    
    def wheelEvent(self, event):
        """Handle mouse wheel for zooming"""
        # Zoom factor
        zoom_factor = 1.15
        if event.angleDelta().y() < 0:
            zoom_factor = 1.0 / zoom_factor
        
        # Calculate zoom point in world coordinates (before zoom)
        screen_x = event.x()
        screen_y = event.y()
        world_x = (screen_x - self.offset_x) / self.zoom_level
        world_y = (screen_y - self.offset_y) / self.zoom_level
        
        # Apply zoom
        old_zoom = self.zoom_level
        self.zoom_level = max(self.min_zoom, min(self.max_zoom, self.zoom_level * zoom_factor))
        
        # Adjust offset to zoom towards mouse position
        if self.zoom_level != old_zoom:
            # Calculate new screen position for the same world point
            new_screen_x = world_x * self.zoom_level + self.offset_x
            new_screen_y = world_y * self.zoom_level + self.offset_y
            # Adjust offset to keep the world point under the mouse
            self.offset_x += screen_x - new_screen_x
            self.offset_y += screen_y - new_screen_y
            
            # Emit signal to update zoom label (if connected)
            if hasattr(self, 'zoom_changed'):
                self.zoom_changed.emit()
            
            self.update()
    
    def screen_to_world(self, screen_x, screen_y):
        """Convert screen coordinates to world coordinates"""
        world_x = (screen_x - self.offset_x) / self.zoom_level
        world_y = (screen_y - self.offset_y) / self.zoom_level
        return world_x, world_y
    
    def world_to_screen(self, world_x, world_y):
        """Convert world coordinates to screen coordinates"""
        screen_x = world_x * self.zoom_level + self.offset_x
        screen_y = world_y * self.zoom_level + self.offset_y
        return screen_x, screen_y
    
    def find_alignment_candidates(self, node_x, node_y, exclude_node=None):
        """Find nodes that align horizontally, vertically, or diagonally with the given position"""
        candidates = {
            'horizontal': [],  # Same Y coordinate
            'vertical': [],    # Same X coordinate
            'diagonal_45': [],  # 45 degree diagonal
            'diagonal_135': []  # 135 degree diagonal
        }
        
        for node in self.nodes:
            if exclude_node and node == exclude_node:
                continue
            
            # Horizontal alignment (same Y)
            if abs(node.y - node_y) < self.snap_threshold:
                candidates['horizontal'].append((node, node.y))
            
            # Vertical alignment (same X)
            if abs(node.x - node_x) < self.snap_threshold:
                candidates['vertical'].append((node, node.x))
            
            # Diagonal alignment (45 degrees: y = x + c)
            # Check if node is on a 45-degree line through (node_x, node_y)
            # Line: y - node_y = (x - node_x) * 1
            expected_y_45 = node_y + (node.x - node_x)
            if abs(node.y - expected_y_45) < self.snap_threshold:
                candidates['diagonal_45'].append((node, node.x, node.y))
            
            # Diagonal alignment (135 degrees: y = -x + c)
            # Line: y - node_y = -(x - node_x)
            expected_y_135 = node_y - (node.x - node_x)
            if abs(node.y - expected_y_135) < self.snap_threshold:
                candidates['diagonal_135'].append((node, node.x, node.y))
        
        return candidates
    
    def apply_strict_alignment(self, new_x, new_y):
        """Apply strict alignment snapping to horizontal, vertical, and diagonal lines"""
        if not self.snap_to_grid:
            return new_x, new_y
        
        candidates = self.find_alignment_candidates(new_x, new_y, self.drag_node)
        
        # Priority: horizontal > vertical > diagonal
        best_snap = None
        best_distance = float('inf')
        
        # Check horizontal alignment
        if candidates['horizontal']:
            # Find the closest horizontal alignment
            for node, align_y in candidates['horizontal']:
                distance = abs(new_y - align_y)
                if distance < best_distance:
                    best_distance = distance
                    best_snap = ('horizontal', new_x, align_y)
        
        # Check vertical alignment
        if candidates['vertical']:
            for node, align_x in candidates['vertical']:
                distance = abs(new_x - align_x)
                if distance < best_distance:
                    best_distance = distance
                    best_snap = ('vertical', align_x, new_y)
        
        # Check diagonal 45 degrees
        if candidates['diagonal_45']:
            for node, align_x, align_y in candidates['diagonal_45']:
                # Calculate the 45-degree line: y = x + c, where c = align_y - align_x
                c = align_y - align_x
                # Project new position onto this line
                # For point (new_x, new_y) and line y = x + c:
                # Projected point: ((new_x + new_y - c) / 2, (new_x + new_y + c) / 2)
                proj_x = (new_x + new_y - c) / 2
                proj_y = proj_x + c
                distance = math.sqrt((new_x - proj_x)**2 + (new_y - proj_y)**2)
                if distance < best_distance:
                    best_distance = distance
                    best_snap = ('diagonal_45', proj_x, proj_y)
        
        # Check diagonal 135 degrees
        if candidates['diagonal_135']:
            for node, align_x, align_y in candidates['diagonal_135']:
                # Calculate the 135-degree line: y = -x + c, where c = align_y + align_x
                c = align_y + align_x
                # Project new position onto this line
                # For point (new_x, new_y) and line y = -x + c:
                # Projected point: ((new_x - new_y + c) / 2, (-new_x + new_y + c) / 2)
                proj_x = (new_x - new_y + c) / 2
                proj_y = -proj_x + c
                distance = math.sqrt((new_x - proj_x)**2 + (new_y - proj_y)**2)
                if distance < best_distance:
                    best_distance = distance
                    best_snap = ('diagonal_135', proj_x, proj_y)
        
        # Apply the best snap if found
        if best_snap and best_distance < self.snap_threshold:
            snap_type, snap_x, snap_y = best_snap
            # Also snap to grid for precision
            snap_x = round(snap_x / self.grid_size) * self.grid_size
            snap_y = round(snap_y / self.grid_size) * self.grid_size
            return snap_x, snap_y
        
        # Fallback: just snap to grid
        return round(new_x / self.grid_size) * self.grid_size, round(new_y / self.grid_size) * self.grid_size
    
    def get_tikz_code(self):
        """Generate TikZ code from current node positions, preserving original structure"""
        if not hasattr(self, 'original_code') or not self.original_code:
            # Fallback to simple generation if no original code
            return self._generate_simple_code()
        
        # Parse original code to preserve structure
        original = self.original_code
        
        # Verify that original code contains the nodes we have (sanity check)
        if self.nodes:
            first_node_name = self.nodes[0].name
            if first_node_name not in original:
                # Original code doesn't match current nodes - this shouldn't happen
                # but if it does, fall back to simple generation
                print(f"Warning: Original code doesn't contain node '{first_node_name}', using simple generation")
                return self._generate_simple_code()
        lines = original.split('\n')
        result_lines = []
        in_tikzpicture = False
        style_defs = []
        node_updates = {}  # Map node name to new position string
        
        # Build map of node positions
        # Use canvas center for coordinate conversion (same as parsing)
        canvas_center_x = 400
        canvas_center_y = 300
        scale_factor = 50  # pixels per cm
        grid_size_pixels = self.grid_size  # Grid size in pixels (20)
        grid_size_tikz = grid_size_pixels / scale_factor  # Grid size in TikZ cm (0.4cm)
        
        # First pass: convert all coordinates and detect horizontal/vertical alignment
        node_coords = {}
        alignment_threshold_pixels = 2  # Consider nodes aligned if within 2 pixels
        alignment_threshold_tikz = alignment_threshold_pixels / scale_factor  # ~0.04cm
        
        for node in self.nodes:
            # Convert from pixel coordinates to TikZ coordinates
            tikz_x = (node.x - canvas_center_x) / scale_factor
            tikz_y = -(node.y - canvas_center_y) / scale_factor
            
            # If snap_to_grid was used, align to TikZ grid to preserve alignment
            if self.snap_to_grid:
                # Snap to nearest grid point in TikZ coordinates
                tikz_x = round(tikz_x / grid_size_tikz) * grid_size_tikz
                tikz_y = round(tikz_y / grid_size_tikz) * grid_size_tikz
            
            node_coords[node.name] = {'x': tikz_x, 'y': tikz_y, 'pixel_y': node.y}
        
        # Second pass: detect and preserve horizontal and vertical alignment
        # Use a more aggressive threshold for alignment detection (0.5cm = 25 pixels)
        # This helps catch nodes that are visually aligned but have small coordinate differences
        alignment_threshold_tikz_aggressive = 0.5  # 25 pixels = 0.5cm
        
        # Group nodes by similar Y coordinates (horizontal alignment)
        # Use clustering approach: group nodes that are close together
        y_groups = {}
        for name, coords in node_coords.items():
            # Try to find existing group within threshold
            found_group = None
            for group_y in y_groups.keys():
                if abs(coords['y'] - group_y) < alignment_threshold_tikz_aggressive:
                    found_group = group_y
                    break
            
            if found_group is not None:
                y_groups[found_group].append(name)
            else:
                # Create new group - use rounded value for cleaner coordinates
                if self.snap_to_grid:
                    group_key = round(coords['y'] / grid_size_tikz) * grid_size_tikz
                else:
                    group_key = round(coords['y'] * 2) / 2  # Round to 0.5cm
                y_groups[group_key] = [name]
        
        # Refine groups: merge groups that are very close together
        y_group_list = sorted(y_groups.items())
        merged_y_groups = {}
        for group_y, node_names in y_group_list:
            merged = False
            for existing_y in merged_y_groups.keys():
                if abs(group_y - existing_y) < alignment_threshold_tikz_aggressive:
                    # Merge into existing group
                    merged_y_groups[existing_y].extend(node_names)
                    merged = True
                    break
            if not merged:
                merged_y_groups[group_y] = node_names
        
        # Apply horizontal alignment: if multiple nodes are in the same group, use the group's Y
        for group_y, node_names in merged_y_groups.items():
            if len(node_names) > 1:
                # Calculate average Y for better alignment
                avg_y = sum(node_coords[name]['y'] for name in node_names) / len(node_names)
                # Round to grid if snapping
                if self.snap_to_grid:
                    avg_y = round(avg_y / grid_size_tikz) * grid_size_tikz
                else:
                    avg_y = round(avg_y * 2) / 2  # Round to 0.5cm
                # Use the group's Y for all nodes
                for name in node_names:
                    node_coords[name]['y'] = avg_y
        
        # Group nodes by similar X coordinates (vertical alignment)
        # Use clustering approach: group nodes that are close together
        x_groups = {}
        for name, coords in node_coords.items():
            # Try to find existing group within threshold
            found_group = None
            for group_x in x_groups.keys():
                if abs(coords['x'] - group_x) < alignment_threshold_tikz_aggressive:
                    found_group = group_x
                    break
            
            if found_group is not None:
                x_groups[found_group].append(name)
            else:
                # Create new group - use rounded value for cleaner coordinates
                if self.snap_to_grid:
                    group_key = round(coords['x'] / grid_size_tikz) * grid_size_tikz
                else:
                    group_key = round(coords['x'] * 2) / 2  # Round to 0.5cm
                x_groups[group_key] = [name]
        
        # Refine groups: merge groups that are very close together
        x_group_list = sorted(x_groups.items())
        merged_x_groups = {}
        for group_x, node_names in x_group_list:
            merged = False
            for existing_x in merged_x_groups.keys():
                if abs(group_x - existing_x) < alignment_threshold_tikz_aggressive:
                    # Merge into existing group
                    merged_x_groups[existing_x].extend(node_names)
                    merged = True
                    break
            if not merged:
                merged_x_groups[group_x] = node_names
        
        # Apply vertical alignment: if multiple nodes are in the same group, use the group's X
        for group_x, node_names in merged_x_groups.items():
            if len(node_names) > 1:
                # Calculate average X for better alignment
                avg_x = sum(node_coords[name]['x'] for name in node_names) / len(node_names)
                # Round to grid if snapping
                if self.snap_to_grid:
                    avg_x = round(avg_x / grid_size_tikz) * grid_size_tikz
                else:
                    avg_x = round(avg_x * 2) / 2  # Round to 0.5cm
                # Use the group's X for all nodes
                for name in node_names:
                    node_coords[name]['x'] = avg_x
        
        # Final pass: format coordinates
        for node in self.nodes:
            coords = node_coords[node.name]
            tikz_x = coords['x']
            tikz_y = coords['y']
            
            # Use precision that matches grid size
            precision = 1 if self.snap_to_grid else 2
            node_updates[node.name] = f"at ({tikz_x:.{precision}f}cm,{tikz_y:.{precision}f}cm)"
            print(f"Export: Node '{node.name}' - pixel: ({node.x:.2f}, {node.y:.2f}) -> TikZ: ({tikz_x:.{precision}f}cm, {tikz_y:.{precision}f}cm)")
        
        print(f"Export: Found {len(node_updates)} nodes to update: {list(node_updates.keys())}")
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Preserve tikzpicture opening with styles (may span multiple lines)
            if '\\begin{tikzpicture}' in stripped:
                in_tikzpicture = True
                result_lines.append(line)
                i += 1
                # Continue reading style definitions until closing bracket
                while i < len(lines) and ']' not in lines[i]:
                    result_lines.append(lines[i])
                    i += 1
                if i < len(lines):
                    result_lines.append(lines[i])  # Add the line with closing bracket
                i += 1
                continue
            
            if '\\end{tikzpicture' in stripped:
                in_tikzpicture = False
                # Fix malformed \end{tikzpicture} (missing closing brace)
                if not stripped.rstrip().endswith('}'):
                    # Remove any trailing whitespace/newlines and add closing brace directly
                    fixed_line = stripped.rstrip() + '}'
                    if line.endswith('\n'):
                        fixed_line += '\n'
                    result_lines.append(fixed_line)
                else:
                    result_lines.append(line)
                i += 1
                continue
            
            # Preserve style definitions (even if inside tikzpicture)
            if '/.style=' in stripped or 'node distance=' in stripped:
                result_lines.append(line)
                i += 1
                continue
            
            # Preserve comments
            if stripped.startswith('%'):
                result_lines.append(line)
                i += 1
                continue
            
            # Preserve scope blocks, labels, background grouping, etc.
            if any(keyword in stripped for keyword in ['\\begin{scope}', '\\end{scope}', 
                                                       '\\node[font=', '\\draw[arrow', '\\draw[dashed',
                                                       'on background layer', 'fit=']):
                result_lines.append(line)
                i += 1
                continue
            
            # Update background groups (fit nodes) - these are editable now
            if '\\node[' in stripped and 'fit=' in stripped:
                # Extract group name and fit nodes
                fit_match = re.search(r'\\node\[([^\]]*)\]\s*\(([^)]+)\)\s*fit=\(([^)]+)\)', stripped)
                if fit_match:
                    group_name = fit_match.group(2)
                    # Find matching background group
                    bg_group = next((bg for bg in self.background_groups if bg.name == group_name), None)
                    if bg_group:
                        # Update fit nodes based on current group position and size
                        # Find nodes that are now within the group's bounds
                        updated_fit_nodes = []
                        group_rect = bg_group.get_rect()
                        for node in self.nodes:
                            node_rect = node.get_rect()
                            # Check if node overlaps with group (with some tolerance)
                            if (node_rect.intersects(group_rect) or 
                                group_rect.contains(node_rect.center())):
                                updated_fit_nodes.append(node.name)
                        
                        # If no nodes found, keep original fit nodes
                        if not updated_fit_nodes:
                            updated_fit_nodes = bg_group.fit_nodes
                        
                        # Reconstruct the line with updated fit nodes
                        fit_nodes_str = ' '.join(updated_fit_nodes)
                        # Preserve the style and other attributes
                        style_str = fit_match.group(1)
                        # Reconstruct: \node[style] (name) fit=(nodes) {text}
                        text_match = re.search(r'\{([^}]*)\}', stripped)
                        text_content = text_match.group(1) if text_match else ""
                        indent = len(line) - len(line.lstrip())
                        new_line = f"\\node[{style_str}] ({group_name}) fit=({fit_nodes_str}) {{{text_content}}}"
                        result_lines.append(' ' * indent + new_line)
                        i += 1
                        continue
                
                # If not matched or not found, preserve as-is
                result_lines.append(line)
                i += 1
                continue
            
            # Update node positions - surgical approach: just replace the position part
            if in_tikzpicture and '\\node[' in stripped and '(' in stripped:
                # Extract node name - be more careful with the regex to ensure we match correctly
                node_match = re.search(r'\\node\[([^\]]*)\]\s*\(([^)]+)\)', stripped)
                if node_match:
                    node_name = node_match.group(2).strip()
                    
                    # Validate that we have a proper node match
                    if not node_name:
                        # Invalid node name - preserve line as-is
                        result_lines.append(line)
                        i += 1
                        continue
                    
                    if node_name in node_updates:
                        print(f"Export: Surgically updating node '{node_name}' position to {node_updates[node_name]}")
                        
                        # Surgical approach: find the node name pattern and replace only the position part
                        # Pattern: \node[style] (name) [position/attributes] {text}
                        
                        # Get the original style string from the match - preserve it exactly
                        original_style_str = node_match.group(1)
                        
                        # First, try to replace ALL existing "at (x,y)" positions (remove duplicates)
                        # Replace all occurrences to prevent stacking, but preserve everything else
                        new_line = re.sub(r'\s+at\s*\([^)]+\)', '', stripped)  # Remove all existing positions first
                        # Then add the new position once
                        if new_line != stripped:
                            # Had existing position(s) - add new one before text brace or semicolon
                            # Make sure we preserve the node structure: \node[style] (name) ...
                            if '{' in new_line:
                                # Insert position before text brace
                                new_line = re.sub(r'(\([^)]+\))\s*(\{)', f"\\1 {node_updates[node_name]} \\2", new_line, count=1)
                            elif ';' in new_line:
                                # Insert position before semicolon
                                new_line = re.sub(r'(\([^)]+\))\s*;', f"\\1 {node_updates[node_name]};", new_line, count=1)
                            else:
                                # No text or semicolon - add position at end
                                new_line = new_line.rstrip() + f" {node_updates[node_name]}"
                            # Ensure line ends with semicolon if it should
                            if '{' not in new_line and not new_line.rstrip().endswith(';'):
                                new_line = new_line.rstrip() + ';'
                            # Preserve original indentation
                            indent = len(line) - len(line.lstrip())
                            result_lines.append(' ' * indent + new_line)
                            i += 1
                            continue
                        
                        # No "at (x,y)" found - need to remove relative positioning and insert absolute
                        # Extract what comes after node name
                        name_end_pos = node_match.end()
                        after_name = stripped[name_end_pos:].strip()
                        
                        # Check if relative positioning is in style brackets
                        # Relative positioning keywords can appear in style brackets like: [code, below=of code-gen, yshift=-0.5cm]
                        has_relative_in_style = any(kw in original_style_str for kw in ['above=of', 'below=of', 'left=of', 'right=of', 'xshift', 'yshift'])
                        
                        # Clean style if needed - extract only the base style name(s), remove relative positioning
                        if has_relative_in_style:
                            # Split by comma and filter out relative positioning
                            style_parts = [part.strip() for part in original_style_str.split(',')]
                            # Keep only parts that are NOT relative positioning
                            base_style_parts = []
                            for part in style_parts:
                                part_stripped = part.strip()
                                # Skip relative positioning keywords (handle node names with hyphens, underscores, etc.)
                                if not (part_stripped.startswith('above=of') or 
                                        part_stripped.startswith('below=of') or 
                                        part_stripped.startswith('left=of') or 
                                        part_stripped.startswith('right=of') or 
                                        part_stripped.startswith('xshift') or 
                                        part_stripped.startswith('yshift')):
                                    base_style_parts.append(part_stripped)
                            cleaned_style = ', '.join(base_style_parts) if base_style_parts else ''
                        else:
                            # Preserve original style exactly - don't modify it
                            cleaned_style = original_style_str
                        
                        # Clean after_name - but preserve text content (everything starting with {)
                        # Find where text content starts
                        text_start = after_name.find('{')
                        if text_start >= 0:
                            # Has text content - separate attributes from text
                            before_text = after_name[:text_start].strip()
                            text_content = after_name[text_start:]  # Keep everything from { onwards
                            
                            # Remove relative positioning from before_text only
                            # Use more precise regex that handles node names with hyphens, underscores, etc.
                            before_text_clean = before_text
                            before_text_clean = re.sub(r',\s*above=of\s+[\w-]+', '', before_text_clean)
                            before_text_clean = re.sub(r',\s*below=of\s+[\w-]+', '', before_text_clean)
                            before_text_clean = re.sub(r',\s*left=of\s+[\w-]+', '', before_text_clean)
                            before_text_clean = re.sub(r',\s*right=of\s+[\w-]+', '', before_text_clean)
                            before_text_clean = re.sub(r',\s*xshift=[^,{]+', '', before_text_clean)
                            before_text_clean = re.sub(r',\s*yshift=[^,{]+', '', before_text_clean)
                            before_text_clean = re.sub(r'^[\s,]+', '', before_text_clean)
                            
                            # Reconstruct: \node[style] (name) at (x,y) [before_text] {text}
                            # Ensure style brackets are properly closed - style must be in brackets
                            if not cleaned_style.strip():
                                # Empty style - use empty brackets (valid TikZ syntax)
                                new_line = f"\\node[] ({node_name}) {node_updates[node_name]}"
                            else:
                                # Ensure style doesn't have unclosed brackets
                                new_line = f"\\node[{cleaned_style}] ({node_name}) {node_updates[node_name]}"
                            if before_text_clean:
                                new_line += f" {before_text_clean}"
                            new_line += f" {text_content}"
                            # Ensure line ends with semicolon if text_content doesn't have it
                            if not new_line.rstrip().endswith(';'):
                                new_line = new_line.rstrip() + ';'
                        else:
                            # No text content - just attributes or semicolon
                            # Use more precise regex that handles node names with hyphens, underscores, etc.
                            after_name_clean = after_name
                            after_name_clean = re.sub(r',\s*above=of\s+[\w-]+', '', after_name_clean)
                            after_name_clean = re.sub(r',\s*below=of\s+[\w-]+', '', after_name_clean)
                            after_name_clean = re.sub(r',\s*left=of\s+[\w-]+', '', after_name_clean)
                            after_name_clean = re.sub(r',\s*right=of\s+[\w-]+', '', after_name_clean)
                            after_name_clean = re.sub(r',\s*xshift=[^,{]+', '', after_name_clean)
                            after_name_clean = re.sub(r',\s*yshift=[^,{]+', '', after_name_clean)
                            after_name_clean = re.sub(r'^[\s,]+', '', after_name_clean)
                            
                            # Reconstruct: \node[style] (name) at (x,y) [rest]
                            # Ensure style brackets are properly closed
                            if not cleaned_style.strip():
                                # Empty style - use empty brackets
                                new_line = f"\\node[] ({node_name}) {node_updates[node_name]}"
                            else:
                                new_line = f"\\node[{cleaned_style}] ({node_name}) {node_updates[node_name]}"
                            if after_name_clean:
                                new_line += f" {after_name_clean}"
                            # Ensure line ends with semicolon
                            if not new_line.rstrip().endswith(';'):
                                new_line = new_line.rstrip() + ';'
                        
                        # Preserve original indentation
                        indent = len(line) - len(line.lstrip())
                        result_lines.append(' ' * indent + new_line)
                        i += 1
                        continue
                    else:
                        # Node exists in original code but wasn't parsed - try to give it a position
                        # Check if we can find a similar node name or try to resolve relative positioning
                        print(f"Export: Node '{node_name}' wasn't parsed - attempting to resolve position")
                        
                        # Try to find if there's a node with a similar name (case-insensitive, partial match)
                        matching_node = None
                        for node in self.nodes:
                            if node.name.lower() == node_name.lower() or node.name.lower().endswith(node_name.lower()) or node_name.lower().endswith(node.name.lower()):
                                matching_node = node
                                break
                        
                        if matching_node:
                            # Use the matching node's position
                            tikz_x = (matching_node.x - 400) / 50
                            tikz_y = -(matching_node.y - 300) / 50
                            precision = 1 if self.snap_to_grid else 2
                            position_str = f"at ({tikz_x:.{precision}f}cm,{tikz_y:.{precision}f}cm)"
                            
                            # Get the original style from the node_match - preserve it exactly
                            original_style_from_match = node_match.group(1)
                            
                            # Try to update the line with absolute position
                            # First, remove all existing positions
                            cleaned_line = re.sub(r'\s+at\s*\([^)]+\)', '', stripped)
                            
                            # Remove relative positioning from AFTER the node name, not from style brackets
                            # Find where node name ends
                            name_end_pos = node_match.end()
                            after_name = stripped[name_end_pos:].strip()
                            
                            # Remove relative positioning from after_name only
                            # Use more precise regex that handles node names with hyphens, underscores, etc.
                            after_name_clean = after_name
                            after_name_clean = re.sub(r',\s*above=of\s+[\w-]+', '', after_name_clean)
                            after_name_clean = re.sub(r',\s*below=of\s+[\w-]+', '', after_name_clean)
                            after_name_clean = re.sub(r',\s*left=of\s+[\w-]+', '', after_name_clean)
                            after_name_clean = re.sub(r',\s*right=of\s+[\w-]+', '', after_name_clean)
                            after_name_clean = re.sub(r',\s*xshift=[^,{]+', '', after_name_clean)
                            after_name_clean = re.sub(r',\s*yshift=[^,{]+', '', after_name_clean)
                            after_name_clean = re.sub(r'^[\s,]+', '', after_name_clean)
                            
                            # Reconstruct: \node[original_style] (name) at (x,y) [after_name_clean]
                            new_line = f"\\node[{original_style_from_match}] ({node_name}) {position_str}"
                            if after_name_clean:
                                new_line += f" {after_name_clean}"
                            if not new_line.rstrip().endswith(';'):
                                new_line = new_line.rstrip() + ';'
                            
                            indent = len(line) - len(line.lstrip())
                            result_lines.append(' ' * indent + new_line)
                            print(f"  Resolved unparsed node '{node_name}' using position from '{matching_node.name}'")
                        else:
                            # Can't find matching node - preserve original line but add default position
                            # Use center of canvas as fallback
                            print(f"  Warning: Could not find matching node for '{node_name}', using default position")
                            default_x = 0.0
                            default_y = 0.0
                            precision = 1 if self.snap_to_grid else 2
                            position_str = f"at ({default_x:.{precision}f}cm,{default_y:.{precision}f}cm)"
                            
                            # Get the original style from the node_match - preserve it exactly
                            original_style_from_match = node_match.group(1)
                            
                            # Remove all existing positions first
                            cleaned_line = re.sub(r'\s+at\s*\([^)]+\)', '', stripped)
                            
                            # Find where node name ends
                            name_end_pos = node_match.end()
                            after_name = stripped[name_end_pos:].strip()
                            
                            # Remove relative positioning from after_name only (not from style)
                            # Use more precise regex that handles node names with hyphens, underscores, etc.
                            after_name_clean = after_name
                            after_name_clean = re.sub(r',\s*above=of\s+[\w-]+', '', after_name_clean)
                            after_name_clean = re.sub(r',\s*below=of\s+[\w-]+', '', after_name_clean)
                            after_name_clean = re.sub(r',\s*left=of\s+[\w-]+', '', after_name_clean)
                            after_name_clean = re.sub(r',\s*right=of\s+[\w-]+', '', after_name_clean)
                            after_name_clean = re.sub(r',\s*xshift=[^,{]+', '', after_name_clean)
                            after_name_clean = re.sub(r',\s*yshift=[^,{]+', '', after_name_clean)
                            after_name_clean = re.sub(r'^[\s,]+', '', after_name_clean)
                            
                            # Reconstruct: \node[original_style] (name) at (x,y) [after_name_clean]
                            new_line = f"\\node[{original_style_from_match}] ({node_name}) {position_str}"
                            if after_name_clean:
                                new_line += f" {after_name_clean}"
                            if not new_line.rstrip().endswith(';'):
                                new_line = new_line.rstrip() + ';'
                            
                            indent = len(line) - len(line.lstrip())
                            result_lines.append(' ' * indent + new_line)
                        i += 1
                        continue
            
            # Preserve draw commands (connections) - all draw commands
            if '\\draw[' in stripped or stripped.startswith('\\draw'):
                result_lines.append(line)
                i += 1
                continue
            
            # Preserve empty lines and other content
            result_lines.append(line)
            i += 1
        
        return '\n'.join(result_lines)
    
    def _generate_simple_code(self):
        """Fallback simple code generation"""
        code = "\\begin{tikzpicture}\n"
        
        for node in self.nodes:
            # Convert pixel coordinates back to TikZ coordinates
            tikz_x = (node.x - 400) / 50
            tikz_y = -(node.y - 300) / 50
            
            style_map = {
                "ellipse": "cloud",
                "cylinder": "db",
                "dashed_rect": "k8s",
                "yellow_rect": "api",
                "rectangle": "service"
            }
            style = style_map.get(node.style_type, "service")
            
            code += f"    \\node[{style}] ({node.name}) at ({tikz_x:.2f}cm,{tikz_y:.2f}cm) {{{node.text}}};\n"
        
        for conn in self.connections:
            style_str = "dashed" if conn.style == "dashed" else ""
            code += f"    \\draw[{style_str}] ({conn.from_node.name}) -- ({conn.to_node.name});\n"
        
        code += "\\end{tikzpicture}\n"
        return code


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TikZ Diagram Editor")
        self.setGeometry(100, 100, 1400, 900)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create layout
        layout = QVBoxLayout(central_widget)
        
        # Create splitter for code and canvas
        splitter = QSplitter(Qt.Horizontal)
        
        # Code editor
        code_widget = QWidget()
        code_layout = QVBoxLayout(code_widget)
        code_layout.addWidget(QLabel("TikZ Code:"))
        self.code_editor = QTextEdit()
        self.code_editor.setFont(QFont("Courier", 10))
        code_layout.addWidget(self.code_editor)
        
        # Code editor buttons
        code_buttons = QHBoxLayout()
        self.load_btn = QPushButton("Load Code")
        self.load_btn.clicked.connect(self.load_code)
        self.render_btn = QPushButton("Render Diagram")
        self.render_btn.clicked.connect(self.render_diagram)
        self.export_btn = QPushButton("Export Code")
        self.export_btn.clicked.connect(self.export_code)
        code_buttons.addWidget(self.load_btn)
        code_buttons.addWidget(self.render_btn)
        code_buttons.addWidget(self.export_btn)
        code_buttons.addStretch()
        code_layout.addLayout(code_buttons)
        
        # Canvas
        canvas_widget = QWidget()
        canvas_layout = QVBoxLayout(canvas_widget)
        canvas_layout.addWidget(QLabel("Visual Editor (Drag nodes to reposition):"))
        
        # Canvas controls
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Grid:"))
        self.grid_checkbox = QCheckBox()
        self.grid_checkbox.setText("Show")
        self.grid_checkbox.setChecked(True)
        self.grid_checkbox.stateChanged.connect(self.toggle_grid)
        controls.addWidget(self.grid_checkbox)
        
        self.snap_checkbox = QCheckBox()
        self.snap_checkbox.setText("Snap")
        self.snap_checkbox.setChecked(False)
        self.snap_checkbox.stateChanged.connect(self.toggle_snap)
        controls.addWidget(self.snap_checkbox)
        
        controls.addWidget(QLabel("Zoom:"))
        self.zoom_label = QLabel("100%")
        controls.addWidget(self.zoom_label)
        
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setMaximumWidth(30)
        zoom_in_btn.clicked.connect(self.zoom_in)
        controls.addWidget(zoom_in_btn)
        
        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setMaximumWidth(30)
        zoom_out_btn.clicked.connect(self.zoom_out)
        controls.addWidget(zoom_out_btn)
        
        reset_zoom_btn = QPushButton("Reset")
        reset_zoom_btn.clicked.connect(self.reset_zoom)
        controls.addWidget(reset_zoom_btn)
        
        controls.addStretch()
        canvas_layout.addLayout(controls)
        
        self.canvas = TikZCanvas()
        canvas_layout.addWidget(self.canvas)
        
        # Connect signals
        self.canvas.position_changed.connect(self.update_code_from_canvas)
        
        # Store reference to main window in canvas for zoom label updates
        self.canvas.main_window = self
        
        # Update zoom label initially
        self.zoom_label.setText("100%")
        
        # Add to splitter
        splitter.addWidget(code_widget)
        splitter.addWidget(canvas_widget)
        splitter.setSizes([600, 800])
        
        layout.addWidget(splitter)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready")
        
        # Load default example
        self.load_example()
    
    def create_menu_bar(self):
        """Create menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        open_action = QAction("Open...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        save_action = QAction("Save...", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        clear_action = QAction("Clear", self)
        clear_action.triggered.connect(self.clear_all)
        edit_menu.addAction(clear_action)
    
    def load_example(self):
        """Load example TikZ code"""
        example_code = """\\begin{tikzpicture}[
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
\\end{tikzpicture}"""
        self.code_editor.setPlainText(example_code)
        self.render_diagram()
    
    def load_code(self):
        """Load code from editor to canvas"""
        self.render_diagram()
    
    def render_diagram(self):
        """Render TikZ code to canvas"""
        code = self.code_editor.toPlainText()
        try:
            # Always update original_code when rendering a new diagram
            self.canvas.parse_tikz_code(code)
            node_count = len(self.canvas.nodes)
            conn_count = len(self.canvas.connections)
            self.statusBar.showMessage(f"Diagram rendered: {node_count} nodes, {conn_count} connections")
        except Exception as e:
            import traceback
            error_msg = f"Failed to parse TikZ code: {str(e)}\n{traceback.format_exc()}"
            QMessageBox.warning(self, "Error", error_msg)
            self.statusBar.showMessage(f"Error: {str(e)}")
    
    def update_code_from_canvas(self):
        """Update code editor when canvas changes"""
        # This would update the code based on visual changes
        # For now, we'll just show a message
        self.statusBar.showMessage("Position updated - code will be regenerated on export")
    
    def toggle_grid(self, state):
        """Toggle grid display"""
        self.canvas.show_grid = (state == Qt.Checked)
        self.canvas.update()
    
    def toggle_snap(self, state):
        """Toggle grid snapping during drag"""
        self.canvas.snap_to_grid = (state == Qt.Checked)
    
    def zoom_in(self):
        """Zoom in"""
        self.canvas.zoom_level = min(self.canvas.max_zoom, self.canvas.zoom_level * 1.2)
        self.zoom_label.setText(f"{int(self.canvas.zoom_level * 100)}%")
        self.canvas.update()
    
    def zoom_out(self):
        """Zoom out"""
        self.canvas.zoom_level = max(self.canvas.min_zoom, self.canvas.zoom_level / 1.2)
        self.zoom_label.setText(f"{int(self.canvas.zoom_level * 100)}%")
        self.canvas.update()
    
    def reset_zoom(self):
        """Reset zoom and pan"""
        self.canvas.zoom_level = 1.0
        self.canvas.offset_x = 0
        self.canvas.offset_y = 0
        self.zoom_label.setText("100%")
        self.canvas.update()
    
    def export_code(self):
        """Export updated TikZ code"""
        # IMPORTANT: Use the ORIGINAL code structure, but current node positions from canvas
        # Don't re-parse from editor if it has been modified by previous exports
        # Only re-parse if we don't have original_code yet
        if not hasattr(self.canvas, 'original_code') or not self.canvas.original_code:
            # No original code stored, parse from editor
            current_code = self.code_editor.toPlainText()
            self.canvas.parse_tikz_code(current_code)
        
        # Always use current node positions from canvas (user's edits)
        # get_tikz_code will use self.nodes which has the current positions
        code = self.canvas.get_tikz_code()
        self.code_editor.setPlainText(code)
        # Update original_code to the newly exported code so next export uses it as base
        self.canvas.original_code = code
        self.statusBar.showMessage("Code updated from visual editor")
    
    def open_file(self):
        """Open TikZ file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open TikZ File", "", "LaTeX Files (*.tex);;All Files (*)")
        if filename:
            with open(filename, 'r', encoding='utf-8') as f:
                self.code_editor.setPlainText(f.read())
            self.render_diagram()
    
    def save_file(self):
        """Save TikZ file"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save TikZ File", "", "LaTeX Files (*.tex);;All Files (*)")
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.code_editor.toPlainText())
            self.statusBar.showMessage(f"Saved to {filename}")
    
    def clear_all(self):
        """Clear all content"""
        self.code_editor.clear()
        self.canvas.nodes = []
        self.canvas.connections = []
        self.canvas.update()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

