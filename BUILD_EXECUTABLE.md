# Building an Executable

## Quick Start

### Option 1: Using the Build Script (Recommended)
```bash
python build_executable.py
```

### Option 2: Using PyInstaller Directly
```bash
pyinstaller QuantumB.spec
```

## Prerequisites

1. **Install PyInstaller:**
   ```bash
   pip install pyinstaller
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Output

The executable will be created in:
- `dist/QuantumB.exe` (single-file executable)

## Details

- **Single-file executable**: All dependencies bundled into one `.exe` file
- **Windowed mode**: No console window on startup (set `console=True` in `QuantumB.spec` if you want console)
- **Bundled folders**: `templates/`, `symbols/`, and `order_file/` are included in the executable

## Customization

Edit `QuantumB.spec` to:
- Add an icon: Set `icon='app.ico'` in the `EXE()` call
- Show console window: Set `console=True` in the `EXE()` call
- Add more hidden imports: Add to the `hiddenimports` list

## Troubleshooting

### "PySide6 not found"
If you have PySide6 installed at a custom location (`C:\pyside6`), you may need to add it to the spec file:
```python
sys.path.insert(0, r'C:\pyside6')
```

### Large file size
Single-file executables are larger (~150-300 MB). For smaller size, change `--onefile` to `--onedir` in `build_executable.py`.

### DLL/Plugin errors
Ensure `PySide6.QtCore`, `PySide6.QtGui`, and `PySide6.QtWidgets` are in the `hiddenimports` list.

## Distribution

Once built, you can distribute `dist/QuantumB.exe` to end users. They won't need Python or any dependencies installed.
