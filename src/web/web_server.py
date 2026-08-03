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

# Get the project root directory (this script lives in src/web/)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# Ensure the repo root is importable (this script may be run directly, e.g.
# `python src/web/web_server.py`, in which case sys.path[0] is src/web/).
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

import src.core.compressor_manager as compressor_manager
import src.core.workbook_manager as workbook_manager
import src.core.template_manager as template_manager

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

WEB_INTERFACE_DIR = PROJECT_ROOT / "web_interface" / "current"
OUTPUT_DIR = WEB_INTERFACE_DIR / "output"

# Configure Flask without built-in static routing so the custom web interface
# file handler below serves pages and assets consistently.
app = Flask(__name__, static_folder=None)
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


# ─────────────────────────────────────────────────────────────────────────────
# Compressor library API
# ─────────────────────────────────────────────────────────────────────────────

def _next_id(items: list[dict]) -> int:
    """Return an id one greater than the highest existing id (min 1)."""
    existing = [int(item.get("id", 0)) for item in items if isinstance(item.get("id"), (int, float))]
    return (max(existing) + 1) if existing else 1


def _norm_text(value: object) -> str:
    """Return a normalized lowercase string for loose matching."""
    return str(value or "").strip().lower()


def _to_float(value: object, default: float = 0.0) -> float:
    """Best-effort float conversion used for workbook capacity values."""
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _best_workbook_model(row: dict) -> str:
    """Pick the preferred compressor model value from workbook row voltages."""
    models = row.get("models_by_voltage") or {}
    return (
        str(models.get("400v") or "").strip()
        or str(models.get("200v") or "").strip()
        or str(models.get("600v") or "").strip()
        or str(row.get("skid_model_number") or "").strip()
    )


@app.route('/api/templates', methods=['GET'])
def get_templates():
    """Return all templates on disk, grouped by category."""
    try:
        return jsonify(template_manager.list_templates())
    except Exception as e:
        logger.error(f"Error listing templates: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Error listing templates: {str(e)}"}), 500


@app.route('/api/workbook/tables', methods=['GET'])
def get_workbook_tables():
    """Return the table catalog from the Excel workbook's Tables sheet."""
    try:
        return jsonify(workbook_manager.load_table_catalog())
    except Exception as e:
        logger.error(f"Error loading workbook tables: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Error loading workbook tables: {str(e)}"}), 500


@app.route('/api/workbook/compressors', methods=['GET'])
def get_workbook_compressors():
    """Return normalized compressor rows from the Tables sheet."""
    try:
        return jsonify(workbook_manager.load_compressor_rows())
    except Exception as e:
        logger.error(f"Error loading workbook compressors: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Error loading workbook compressors: {str(e)}"}), 500


@app.route('/api/workbook/generator-filters', methods=['GET'])
def get_workbook_generator_filters():
    """Return capacity/manufacturer/tension options for generator selection."""
    try:
        manufacturer = request.args.get('manufacturer')
        return jsonify(workbook_manager.load_generator_filters(manufacturer=manufacturer))
    except Exception as e:
        logger.error(f"Error loading generator filters: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Error loading generator filters: {str(e)}"}), 500


@app.route('/api/workbook/circuits', methods=['GET'])
def get_workbook_circuits():
    """Return circuits/compressors for a workbook-based generator selection."""
    try:
        capacity = request.args.get('capacity', type=float)
        manufacturer = (request.args.get('manufacturer') or '').strip()
        tension = (request.args.get('tension') or '').strip()

        if capacity is None or not manufacturer or not tension:
            return jsonify({
                "error": "Missing required query parameters: capacity, manufacturer, tension"
            }), 400

        payload = workbook_manager.load_circuits_for_selection(
            capacity=capacity,
            manufacturer=manufacturer,
            tension=tension,
        )
        return jsonify(payload)
    except Exception as e:
        logger.error(f"Error loading workbook circuits: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Error loading workbook circuits: {str(e)}"}), 500


@app.route('/api/compressors', methods=['GET'])
def get_compressors():
    """Return all compressors in the shared library."""
    try:
        return jsonify(compressor_manager.load_compressors())
    except Exception as e:
        logger.error(f"Error loading compressors: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Error loading compressors: {str(e)}"}), 500


@app.route('/api/compressors', methods=['POST'])
def create_compressor():
    """Create a new compressor in the shared library."""
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json()
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Compressor name is required"}), 400

        compressors = compressor_manager.load_compressors()
        new_compressor = {
            "id": _next_id(compressors),
            "name": name,
            "model": data.get("model", ""),
            "manufacturer": data.get("manufacturer", ""),
            "capacity": data.get("capacity", 0),
            "templates": data.get("templates", []) or [],
        }
        compressors.append(new_compressor)

        success, message = compressor_manager.save_compressors(compressors)
        if not success:
            return jsonify({"error": message}), 500

        return jsonify(new_compressor), 201
    except Exception as e:
        logger.error(f"Error creating compressor: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Error creating compressor: {str(e)}"}), 500


@app.route('/api/compressors/sync-workbook', methods=['POST'])
def sync_compressors_from_workbook():
    """Load all workbook compressors into the shared library (merge mode)."""
    try:
        workbook_rows = workbook_manager.load_compressor_rows()
        compressors = compressor_manager.load_compressors()

        # Workbook rows are identified by skid model name + manufacturer.
        # We do not key by model number because many distinct compressors share
        # the same compressor model across capacities.
        by_identity: dict[str, dict] = {}
        by_name: dict[str, dict] = {}
        for comp in compressors:
            name_key = _norm_text(comp.get("name"))
            manufacturer_key = _norm_text(comp.get("manufacturer"))
            identity_key = f"{manufacturer_key}|{name_key}" if name_key else ""
            if identity_key:
                by_identity[identity_key] = comp
            if name_key:
                by_name[name_key] = comp

        imported_count = 0
        updated_count = 0
        skipped_count = 0

        for row in workbook_rows:
            name = str(row.get("skid_model_number") or "").strip()
            model = _best_workbook_model(row)
            manufacturer = str(row.get("manufacturer") or "").strip()
            capacity = _to_float(row.get("nominal_capacity"), default=0.0)

            if not name and not model:
                skipped_count += 1
                continue

            if not name:
                name = model
            if not model:
                model = name

            name_key = _norm_text(name)
            manufacturer_key = _norm_text(manufacturer)
            identity_key = f"{manufacturer_key}|{name_key}" if name_key else ""

            existing = by_identity.get(identity_key) if identity_key else None
            if not existing and name_key:
                existing = by_name.get(name_key)

            if existing:
                # Keep existing template assignments; refresh workbook-driven fields.
                existing["name"] = name
                existing["model"] = model
                existing["manufacturer"] = manufacturer
                existing["capacity"] = capacity
                existing.setdefault("templates", [])
                updated_count += 1
                if identity_key:
                    by_identity[identity_key] = existing
                by_name[name_key] = existing
                continue

            new_comp = {
                "id": _next_id(compressors),
                "name": name,
                "model": model,
                "manufacturer": manufacturer,
                "capacity": capacity,
                "templates": [],
            }
            compressors.append(new_comp)
            imported_count += 1
            if identity_key:
                by_identity[identity_key] = new_comp
            by_name[name_key] = new_comp

        success, message = compressor_manager.save_compressors(compressors)
        if not success:
            return jsonify({"error": message}), 500

        return jsonify(
            {
                "imported": imported_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "compressors": compressors,
            }
        )
    except Exception as e:
        logger.error(f"Error syncing workbook compressors: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Error syncing workbook compressors: {str(e)}"}), 500


@app.route('/api/compressors/export', methods=['GET'])
def export_compressors():
    """Return the whole compressor library as a downloadable JSON file."""
    try:
        compressors = compressor_manager.load_compressors()
        export_data = {
            "version": "1.0",
            "exportDate": datetime.now().isoformat(),
            "compressors": compressors,
        }

        temp_dir = tempfile.mkdtemp(prefix="xnnov_export_")
        export_path = Path(temp_dir) / f"compressors_{datetime.now().strftime('%Y%m%d')}.json"
        export_path.write_text(json.dumps(export_data, indent=2, ensure_ascii=False), encoding="utf-8")

        return send_file(
            str(export_path),
            mimetype='application/json',
            as_attachment=True,
            download_name=export_path.name,
        )
    except Exception as e:
        logger.error(f"Error exporting compressors: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Error exporting compressors: {str(e)}"}), 500


@app.route('/api/compressors/import', methods=['POST'])
def import_compressors():
    """Import compressors from an uploaded JSON file, merging or replacing."""
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json()
        imported = data.get("compressors")
        if not isinstance(imported, list):
            return jsonify({"error": "Invalid file format. Expected a compressors array."}), 400

        mode = data.get("mode", "merge")  # "merge" or "replace"

        if mode == "replace":
            compressors = []
        else:
            compressors = compressor_manager.load_compressors()

        for item in imported:
            item = dict(item)
            item["id"] = _next_id(compressors)
            compressors.append(item)

        success, message = compressor_manager.save_compressors(compressors)
        if not success:
            return jsonify({"error": message}), 500

        return jsonify({"imported": len(imported), "compressors": compressors})
    except Exception as e:
        logger.error(f"Error importing compressors: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Error importing compressors: {str(e)}"}), 500


@app.route('/api/compressors/<int:compressor_id>', methods=['PUT'])
def update_compressor(compressor_id):
    """Replace an existing compressor's fields (name/model/manufacturer/capacity/templates)."""
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json()
        compressors = compressor_manager.load_compressors()

        for compressor in compressors:
            if int(compressor.get("id", -1)) == compressor_id:
                for field in ("name", "model", "manufacturer", "capacity", "templates"):
                    if field in data:
                        compressor[field] = data[field]

                success, message = compressor_manager.save_compressors(compressors)
                if not success:
                    return jsonify({"error": message}), 500
                return jsonify(compressor)

        return jsonify({"error": f"Compressor {compressor_id} not found"}), 404
    except Exception as e:
        logger.error(f"Error updating compressor: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Error updating compressor: {str(e)}"}), 500


@app.route('/api/compressors/<int:compressor_id>', methods=['DELETE'])
def delete_compressor(compressor_id):
    """Delete a compressor from the shared library."""
    try:
        compressors = compressor_manager.load_compressors()
        remaining = [c for c in compressors if int(c.get("id", -1)) != compressor_id]

        if len(remaining) == len(compressors):
            return jsonify({"error": f"Compressor {compressor_id} not found"}), 404

        success, message = compressor_manager.save_compressors(remaining)
        if not success:
            return jsonify({"error": message}), 500

        return jsonify({"deleted": compressor_id})
    except Exception as e:
        logger.error(f"Error deleting compressor: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Error deleting compressor: {str(e)}"}), 500


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
def serve_web_interface(path='base.html'):
    """Serve the web interface and static files."""
    if path == '':
        path = 'base.html'
    
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
    elif file_path_resolved.is_dir() and (file_path_resolved / 'base.html').is_file():
        logger.info(f"Serving directory index: {path}/base.html")
        return send_file(str(file_path_resolved / 'base.html'))
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
