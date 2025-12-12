# Installation Guide

## Windows Installation Issues

If you encounter file lock errors during installation (like `pylupdate5.exe`), try these solutions:

### Solution 1: Close Python Processes (Recommended)
1. Close all Python processes, IDEs (VS Code, PyCharm), and terminals
2. Open a new terminal as Administrator
3. Run: `pip install -r requirements.txt`

### Solution 2: Use Virtual Environment (Best Practice)
```bash
# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Solution 3: Install with --user flag
```bash
pip install --user -r requirements.txt
```

### Solution 4: Manual Cleanup
If the error persists:
1. Navigate to `C:\Python312\Scripts\`
2. Manually delete `pylupdate5.exe` if it exists
3. Run installation again

## Running the Application

After successful installation:
```bash
python main.py
```

## Building Executable

To create a standalone .exe file:
```bash
pyinstaller --onefile --windowed --name tikz-editor main.py
```

The executable will be in the `dist` folder.

