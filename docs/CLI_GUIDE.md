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

**Standard Mode (from existing project file):**
```bash
python app.py --project <project_file> --output <output_folder> [--format {dxf|dwg|both}]
```

**Selection Tool Mode (from XNNOV Selection Tool JSON):**
```bash
python app.py --generate-from-selection <selection_json> --output <output_folder> [--format {dxf|dwg|both}]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--project` | Yes* | Path to the `.aepj` project file |
| `--generate-from-selection` | Yes* | Path to XNNOV Selection Tool JSON file |
| `--output` | Yes | Directory where generated files will be saved |
| `--format` | No | Output format: `dxf`, `dwg`, or `both` (default: `dxf`) |

*Either `--project` or `--generate-from-selection` is required (mutually exclusive)

#### Examples

**Generate DXF files from project (default):**
```bash
python app.py --project my_project.aepj --output ./output
```

**Generate from XNNOV Selection Tool JSON:**
```bash
python app.py --generate-from-selection selection_data.json --output ./output
```

**Generate both DXF and DWG from selection:**
```bash
python app.py --generate-from-selection selection_data.json --output ./output --format both
```

**Generate DWG files from project (requires ODA Converter installed):**
```bash
python app.py --project my_project.aepj --output ./output --format dwg
```

**Generate both DXF and DWG files from project:**
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

## XNNOV Selection Tool Integration

The CLI can generate drawings directly from **XNNOV Selection Tool** data without requiring a pre-made `.aepj` file.

### Selection Tool JSON Format

The XNNOV Selection Tool exports a JSON file with circuit selections, compressors, and drawing references:

```json
{
  "project_name": "My XNNOV Project",
  "project_number": "PRJ-001",
  "revision": "A",
  "drawn_by": "Engineer Name",
  "circuits": [
    {
      "name": "CU001",
      "description": "Condensing Unit 1",
      "compressors": [
        {
          "model_number": "COMP-001",
          "description": "First Compressor",
          "templates": [
            {"name": "p1.dxf", "quantity": 1},
            {"name": "p2.dxf", "quantity": 2}
          ]
        },
        {
          "model_number": "COMP-002",
          "description": "Second Compressor",
          "templates": [
            {"name": "p3.dxf", "quantity": 1}
          ]
        }
      ]
    },
    {
      "name": "CU002",
      "description": "Condensing Unit 2",
      "compressors": [
        {
          "model_number": "COMP-003",
          "description": "Single Compressor",
          "templates": [
            {"name": "p4.dxf", "quantity": 1}
          ]
        }
      ]
    }
  ]
}
```

#### Selection JSON Fields

- **project_name**: Project name (becomes the project name in the .aepj)
- **project_number**: Project identifier (drawing number)
- **revision**: Drawing revision (e.g., "A", "B")
- **drawn_by**: Engineer/drafter name
- **circuits**: Array of XNNOV unit selections
  - **name**: Circuit identifier (e.g., "CU001")
  - **description**: Human-readable circuit name
  - **compressors**: Array of compressors in this circuit
    - **model_number**: Compressor model/identifier (e.g., "COMP-001")
    - **description**: Compressor description
    - **templates**: Array of templates with quantities
      - **name**: DXF template filename to render
      - **quantity**: Number of times to generate this template (e.g., 2 = two pages of this template)

#### Excel Format for Selection Tool

The Selection Tool reads from an Excel file with the following structure:

| Circuit_ID | Compressor_Model | Compressor_Description | Template_Name | Quantity |
|---|---|---|---|---|
| CU001 | COMP-001 | First Compressor | p1.dxf | 1 |
| CU001 | COMP-001 | First Compressor | p2.dxf | 2 |
| CU001 | COMP-002 | Second Compressor | p3.dxf | 1 |
| CU002 | COMP-003 | Single Compressor | p4.dxf | 1 |

**Column Descriptions:**
- **Circuit_ID**: Circuit identifier (e.g., CU001, CU002)
- **Compressor_Model**: Compressor model number or identifier
- **Compressor_Description**: Human-readable compressor name
- **Template_Name**: DXF template filename (e.g., p1.dxf)
- **Quantity**: Number of pages to generate for this template

### Workflow

1. User selects XNNOV units in the Selection Tool
2. For each circuit, specify compressors (by model number)
3. For each compressor, specify templates and quantities needed
4. Selection Tool exports data to a JSON file
5. Run CLI: `python app.py --generate-from-selection selection.json --output ./output`
6. CLI automatically:
   - Creates a temporary `.aepj` project with dummy circuits
   - Processes each circuit → compressor → template with quantity
   - Generates drawings for all pages in order
   - Outputs DXF/DWG files (E001.dxf, E002.dxf, etc.)

#### Page Generation Example

**Input:** Circuit CU001 with:
- Compressor COMP-001: p1.dxf (qty 1) + p2.dxf (qty 2)
- Compressor COMP-002: p3.dxf (qty 1)

**Output:** 4 files
- E001.dxf (from p1.dxf × 1)
- E002.dxf (from p2.dxf × 1)
- E003.dxf (from p2.dxf × 1, second copy)
- E004.dxf (from p3.dxf × 1)

### Example: Generate from Selection

```bash
# Excel-based workflow: Selection Tool → Export JSON → Generate DXF
python app.py --generate-from-selection XNNOV_Selection_2026-07.json --output ./CU_Drawings --format both
```

The output will contain all circuit pages as separate DXF (and optionally DWG) files, organized sequentially (E001.dxf, E002.dxf, etc.) across all compressors and circuits.

**Workflow:**
1. Edit Excel file: Add circuits, compressors, templates, and quantities
2. Selection Tool: Parses Excel and exports JSON
3. CLI: `python app.py --generate-from-selection selection.json --output ./output`
4. Result: All pages generated in sequential order

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
