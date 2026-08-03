"""
Web server for XNNOV Selection Tool
Provides backend API for generating AutoCAD drawings from selection data.

Usage:
    python web_server.py [--port 5000] [--host 0.0.0.0]

Features:
    - Accepts selection JSON via POST to /api/generate
    - Runs CLI generator in background
    - Returns generated files as ZIP for download
    - Includes CORS support for browser requests
"""

from __future__ import annotations

import json
import tempfile
import subprocess
import shutil
import sys
import os
from pathlib import Path
from datetime import datetime
import logging
import traceback
import argparse

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get the project root directory (this script lives in src/web/)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
WEB_INTERFACE_DIR = PROJECT_ROOT / "web_interface" / "legacy"
OUTPUT_DIR = WEB_INTERFACE_DIR / "output"

# Configure Flask to serve static files from Web Interface
app = Flask(__name__, static_folder=str(WEB_INTERFACE_DIR), static_url_path='')
CORS(app)  # Enable CORS for all routes


def run_cli_generator(selection_json: dict, output_dir: str) -> tuple[bool, str]:
    """
    Run the CLI generator with the given selection data.
    
    Parameters
    ----------
    selection_json : dict
        Selection tool configuration
    output_dir : str
        Directory where generated files will be saved
    
    Returns
    -------
    tuple[bool, str]
        (success, message)
    """
    try:
        # Create temporary JSON file for CLI
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False,
            dir=str(PROJECT_ROOT)
        ) as tmp:
            json.dump(selection_json, tmp)
            tmp_json_path = tmp.name
        
        logger.info(f"Created temporary selection file: {tmp_json_path}")
        
        # Prepare the CLI command
        python_exe = sys.executable
        cmd = [
            python_exe,
            str(PROJECT_ROOT / "app.py"),
            "--generate-from-selection",
            tmp_json_path,
            "--output",
            output_dir
        ]
        
        logger.info(f"Running CLI command: {' '.join(cmd)}")
        
        # Run the CLI generator
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        
        # Clean up temporary JSON file
        try:
            os.remove(tmp_json_path)
        except Exception as e:
            logger.warning(f"Failed to clean up temp file: {e}")
        
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            logger.error(f"CLI generator failed: {error_msg}")
            return False, f"Generation failed: {error_msg}"
        
        logger.info(f"CLI generator completed successfully")
        logger.info(f"STDOUT: {result.stdout}")
        
        return True, "Generation completed successfully"
    
    except subprocess.TimeoutExpired:
        logger.error("CLI generator timed out")
        return False, "Generation timed out (exceeded 2 minutes)"
    except Exception as e:
        logger.error(f"Error running CLI generator: {e}\n{traceback.format_exc()}")
        return False, f"Error: {str(e)}"


def zip_directory(source_dir: str, zip_path: str) -> bool:
    """
    Zip a directory into a single file.
    
    Parameters
    ----------
    source_dir : str
        Directory to zip
    zip_path : str
        Output zip file path
    
    Returns
    -------
    bool
        True if successful
    """
    try:
        logger.info(f"Zipping directory: {source_dir} → {zip_path}")
        shutil.make_archive(
            str(Path(zip_path).with_suffix('')),
            'zip',
            source_dir
        )
        logger.info(f"Successfully created zip: {zip_path}")
        return True
    except Exception as e:
        logger.error(f"Error zipping directory: {e}")
        return False


@app.route('/api/generate', methods=['POST'])
def generate_drawings():
    """
    API endpoint to generate AutoCAD drawings from selection data.
    
    Expected POST body:
    {
        "project_name": "Project Name",
        "project_number": "001",
        "revision": "A",
        "drawn_by": "Name",
        "circuits": [...]
    }
    
    Returns:
        ZIP file download on success, error JSON on failure
    """
    try:
        # Get JSON data from request
        if not request.is_json:
            logger.warning("Request is not JSON")
            return jsonify({"error": "Request must be JSON"}), 400
        
        selection_data = request.get_json()
        
        # Validate required fields
        if not selection_data.get('circuits'):
            logger.warning("No circuits in selection data")
            return jsonify({"error": "No circuits defined in selection data"}), 400
        
        # Create temporary directories
        temp_dir = tempfile.mkdtemp(prefix="xnnov_gen_")
        output_dir = Path(temp_dir) / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Created temporary work directory: {temp_dir}")
        
        try:
            # Run the CLI generator
            success, message = run_cli_generator(selection_data, str(output_dir))
            
            if not success:
                logger.error(f"Generation failed: {message}")
                return jsonify({"error": message}), 500
            
            # Save selection arguments for traceability and reproducibility
            args_filename = "selection_arguments.json"
            args_file_path = os.path.join(str(output_dir), args_filename)
            
            try:
                with open(args_file_path, 'w', encoding='utf-8') as f:
                    json.dump(selection_data, f, indent=2)
                logger.info(f"Saved selection arguments to: {args_file_path}")
                if os.path.exists(args_file_path):
                    file_size = os.path.getsize(args_file_path)
                    logger.info(f"Arguments file created successfully, size: {file_size} bytes")
                else:
                    logger.warning(f"Arguments file was not created at {args_file_path}")
            except Exception as e:
                logger.warning(f"Failed to save selection arguments: {e}")
                import traceback
                logger.warning(traceback.format_exc())
            
            # Check if output directory has files
            output_files = list(output_dir.glob("*"))
            if not output_files:
                logger.warning("No files were generated")
                return jsonify({"error": "No files were generated"}), 500
            
            logger.info(f"Generated {len(output_files)} file(s)")
            
            # Create zip file
            project_name = (selection_data.get('project_name', 'project')
                           .replace(' ', '_')
                           .replace('/', '_'))
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            zip_filename = f"{project_name}_{timestamp}.zip"
            zip_path = Path(temp_dir) / zip_filename
            
            if not zip_directory(str(output_dir), str(zip_path)):
                return jsonify({"error": "Failed to create zip file"}), 500
            
            # Send the zip file
            logger.info(f"Sending zip file: {zip_path}")
            return send_file(
                str(zip_path),
                mimetype='application/zip',
                as_attachment=True,
                download_name=zip_filename
            )
        
        finally:
            # Note: We don't delete the temp directory immediately because
            # the file is still being served. Flask will handle cleanup after
            # the response is sent. In production, consider implementing a
            # cleanup task that removes old temp directories.
            pass
    
    except Exception as e:
        logger.error(f"Unexpected error in /api/generate: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "XNNOV Selection Tool Generator",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/', methods=['GET'])
@app.route('/<path:path>', methods=['GET'])
def serve_web_interface(path='index.html'):
    """Serve the web interface and static files."""
    if path == '':
        path = 'index.html'
    
    file_path = WEB_INTERFACE_DIR / path
    
    # Check if file exists and is within the web interface directory
    try:
        file_path_resolved = file_path.resolve()
        web_dir_resolved = WEB_INTERFACE_DIR.resolve()
        # Ensure the resolved path is within the web directory
        file_path_resolved.relative_to(web_dir_resolved)
    except (ValueError, OSError):
        logger.warning(f"Access denied to: {path}")
        return "Not found", 404
    
    if file_path_resolved.is_file():
        logger.info(f"Serving file: {path}")
        return send_file(str(file_path_resolved))
    elif file_path_resolved.is_dir() and (file_path_resolved / 'index.html').is_file():
        logger.info(f"Serving directory index: {path}/index.html")
        return send_file(str(file_path_resolved / 'index.html'))
    else:
        logger.warning(f"File not found: {path} (resolved: {file_path_resolved})")
        return "Not found", 404


def main():
    """Main entry point for the web server."""
    parser = argparse.ArgumentParser(
        description="XNNOV Selection Tool Web Server"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to run server on (default: 5000)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("XNNOV Selection Tool - Web Server")
    print("=" * 60)
    print(f"Starting server on http://{args.host}:{args.port}")
    print(f"Web interface: http://{args.host}:{args.port}/")
    print(f"API endpoint: http://{args.host}:{args.port}/api/generate")
    print("=" * 60)
    print()
    
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug
    )


if __name__ == '__main__':
    main()
