# AutoCAD Electrical Drawing Generator - CLI Guide

## Overview

The AutoCAD Electrical Drawing Generator now supports both **GUI (interactive)** and **CLI (command-line)** modes. This allows you to:

- Use the graphical interface for design and configuration
- Run automated generation via command-line for batch processing, CI/CD pipelines, or server-side automation

## Usage Modes

### GUI Mode (Default)

Run the application without arguments to launch the graphical interface:

```bash
python app.py
```

This opens the interactive window where you can:
- Create and edit projects
- Configure circuits, I/O items, and rungs
- Preview templates
- Generate drawings with a visual progress indicator

### CLI Mode (Non-Interactive)

Run the application with command-line arguments to generate drawings automatically:

```bash
python app.py --project <project_file> --output <output_folder> [--format {dxf|dwg|both}]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--project` | Yes | Path to the `.aepj` project file |
| `--output` | Yes | Directory where generated files will be saved |
| `--format` | No | Output format: `dxf`, `dwg`, or `both` (default: `dxf`) |

#### Examples

**Generate DXF files (default):**
```bash
python app.py --project my_project.aepj --output ./output
```

**Generate DWG files (requires ODA Converter installed):**
```bash
python app.py --project my_project.aepj --output ./output --format dwg
```

**Generate both DXF and DWG files:**
```bash
python app.py --project my_project.aepj --output ./output --format both
```

**Windows PowerShell example:**
```powershell
& python app.py --project "C:\Projects\project.aepj" --output "C:\Output" --format both
```

## Project File Format

Project files use the `.aepj` extension (AutoCAD Electrical Project JSON). They contain:

```json
{
  "version": 1,
  "settings": {
    "title": "ELECTRICAL DRAWING",
    "project": "Project Name",
    "drawing_number": "001",
    "revision": "A",
    "drawn_by": "Engineer Name",
    "paper_size": "A3 Landscape"
  },
  "project_circuits": ["Circuit1", "Circuit2"],
  "io_items": [
    {
      "tag": "I001",
      "io_type": "Input",
      "io_type_name": "Discrete Input",
      "address": "1000",
      "description": "Start Button",
      ...
    }
  ],
  "rungs": [
    {
      "rung_number": 1,
      "description": "Start/Stop Logic",
      "components": [
        {
          "symbol": "NO_CONTACT",
          "tag": "S001",
          "description": "Start Switch",
          ...
        }
      ]
    }
  ]
}
```

## Creating a Project File

### Method 1: Using the GUI

1. Launch the application: `python app.py`
2. Configure your project settings, circuits, I/O items, and rungs
3. Save the project: **File → Save Project**
4. This creates a `.aepj` file that can be used with the CLI

### Method 2: Manual JSON Creation

Create a `.aepj` file with the structure shown above. Ensure all required fields are populated correctly.

## Output Formats

### DXF (AutoCAD DXF Format)
- Supported by all AutoCAD versions
- Recommended for maximum compatibility
- Smaller file sizes
- Default output format

### DWG (AutoCAD DWG Format)
- Native AutoCAD binary format
- Requires ODA Converter installation
- Provides better performance in AutoCAD
- Conversion happens automatically if ODA is available

#### Installing ODA Converter

To support DWG output:

1. Download ODA Converter from: https://www.opendesign.com/guestfiles/oda_file_converter
2. Install it with default settings
3. The application will auto-detect it on Windows

## Return Codes

The CLI returns standard exit codes:

| Code | Meaning |
|------|---------|
| 0 | Success - all files generated |
| 1 | Failure - see error messages |

## Error Handling

Errors are reported in two ways:

1. **Standard Output**: Progress messages and generation summary
2. **Standard Error**: Error details and stack traces (if `--debug` is used)

### Common Errors

**"Project file not found"**
- Verify the `--project` path is correct
- Use absolute paths to avoid confusion

**"Project has no circuits defined"**
- Add circuits to the project using the GUI
- Save the project and try again

**"Circuit 'X' not found in library"**
- Verify the circuit name exists in the circuit library
- Check for typos or case sensitivity

**"ODA Converter not found" (when using `--format dwg`)**
- Install ODA Converter (see Installation section)
- Or use `--format dxf` instead

## Batch Processing Examples

### Generate multiple projects (PowerShell)

```powershell
$projects = @("project1.aepj", "project2.aepj", "project3.aepj")
$outputBase = "C:\GeneratedDrawings"

foreach ($project in $projects) {
    $projectName = [System.IO.Path]::GetFileNameWithoutExtension($project)
    $outputDir = Join-Path $outputBase $projectName
    
    Write-Host "Generating $project..."
    python app.py --project $project --output $outputDir --format both
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to generate $project"
    }
}
```

### Generate multiple projects (Bash/Linux)

```bash
#!/bin/bash
for project in project1.aepj project2.aepj project3.aepj; do
    projectName="${project%.*}"
    outputDir="./output/$projectName"
    
    echo "Generating $project..."
    python app.py --project "$project" --output "$outputDir" --format both
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to generate $project" >&2
    fi
done
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Generate Electrical Drawings

on:
  push:
    paths:
      - '**.aepj'

jobs:
  generate:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Generate drawings
        run: |
          python app.py --project project.aepj --output ./generated --format both
      
      - name: Upload artifacts
        uses: actions/upload-artifact@v2
        with:
          name: generated-drawings
          path: generated/
```

## Performance Notes

- **Large projects**: May take several minutes to generate depending on:
  - Number of circuits
  - Number of I/O items
  - Number of rungs
  - DWG conversion (if enabled)
  
- **Memory usage**: Typically 100-500MB depending on template size

- **Disk space**: Ensure sufficient space for output files:
  - DXF: ~500KB - 2MB per page
  - DWG: ~1-5MB per page

## Troubleshooting

### CLI not detecting arguments
- Ensure arguments are provided before any other Python arguments
- Use `--project` and `--output` with the correct syntax

### Unicode/special characters in filenames
- Use absolute paths with proper quoting
- Ensure the output directory supports Unicode

### Output files not created
- Check the output directory permissions
- Verify disk space availability
- Review error messages in the console output

### Slow DWG conversion
- This is expected - ODA Converter is thorough
- Consider using DXF format for faster batch processing

## API for Programmatic Use

If you need to integrate the generator into Python scripts:

```python
from cli import CLIGenerator

# Create generator instance
generator = CLIGenerator(
    project_path="my_project.aepj",
    output_dir="./output",
    output_format="both"
)

# Generate drawings
success, message = generator.generate()

if success:
    print(f"Success: {message}")
else:
    print(f"Error: {message}")
```

## Additional Resources

- **Project Repository**: See the main README.md
- **GUI Help**: Press F1 or use the Help menu in GUI mode
- **Support**: For issues or feature requests, see the project documentation
