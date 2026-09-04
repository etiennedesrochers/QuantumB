#!/usr/bin/env python3
"""
Quick Reference: CLI Command Examples
Run this to see all available CLI options and examples
"""

CLI_COMMANDS = {
    "Get Help": {
        "command": "python app.py --help",
        "description": "Show all available options and examples"
    },
    
    "Generate DXF (Default)": {
        "command": "python app.py --project project.aepj --output ./output",
        "description": "Generate AutoCAD DXF files (fastest)"
    },
    
    "Generate DWG": {
        "command": "python app.py --project project.aepj --output ./output --format dwg",
        "description": "Generate AutoCAD DWG files (requires ODA Converter)"
    },
    
    "Generate Both": {
        "command": "python app.py --project project.aepj --output ./output --format both",
        "description": "Generate both DXF and DWG files"
    },
    
    "GUI Mode": {
        "command": "python app.py",
        "description": "Launch the graphical interface (default when no CLI args)"
    },
}

BATCH_PROCESSING = {
    "PowerShell - All .aepj files": """
$projects = Get-ChildItem *.aepj
foreach ($project in $projects) {
    $name = $project.BaseName
    python app.py --project $project --output "./output/$name" --format both
}
""",
    
    "Bash - Loop through projects": """
#!/bin/bash
for project in *.aepj; do
    name="${project%.*}"
    python app.py --project "$project" --output "./output/$name" --format both
done
""",
    
    "Windows Batch - Loop": """
@echo off
for %%f in (*.aepj) do (
    python app.py --project "%%f" --output "./output/%%~nf" --format both
)
""",
}

CI_CD_EXAMPLES = {
    "GitHub Actions": """
name: Generate Drawings
on: [push]
jobs:
  generate:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - run: pip install -r requirements.txt
      - run: python app.py --project project.aepj --output ./generated --format both
      - uses: actions/upload-artifact@v2
        with:
          name: drawings
          path: generated/
""",
    
    "GitLab CI": """
generate_drawings:
  image: python:3.11
  script:
    - pip install -r requirements.txt
    - python app.py --project project.aepj --output ./generated --format both
  artifacts:
    paths:
      - generated/
""",
}

def print_section(title, content):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")
    print(content)

if __name__ == "__main__":
    print("\n" + "="*60)
    print(" AUTOCAD ELECTRICAL DRAWING GENERATOR - CLI QUICK REFERENCE")
    print("="*60)
    
    # Commands
    print_section("BASIC COMMANDS", "")
    for name, info in CLI_COMMANDS.items():
        print(f"\n{name}:")
        print(f"  Command: {info['command']}")
        print(f"  → {info['description']}")
    
    # Batch processing
    print_section("BATCH PROCESSING EXAMPLES", "")
    for name, script in BATCH_PROCESSING.items():
        print(f"\n{name}:")
        print(script)
    
    # CI/CD
    print_section("CI/CD INTEGRATION", "")
    for name, config in CI_CD_EXAMPLES.items():
        print(f"\n{name}:")
        print(config)
    
    # Tips
    print_section("QUICK TIPS", """
1. Use --format dxf for fastest generation
2. Use --format dwg for AutoCAD native format (slower, needs ODA)
3. Use --format both for maximum compatibility
4. Exit code 0 = success, 1 = failure (use for scripts)
5. Always use full paths to avoid confusion
6. Create .aepj files from the GUI, then automate with CLI
7. Check CLI_GUIDE.md for detailed documentation
8. No GUI needed - run CLI on headless servers
    """)
    
    print("\n" + "="*60)
    print(" For more info: python app.py --help")
    print(" Full documentation: CLI_GUIDE.md")
    print("="*60 + "\n")
