"""
Détermine la commande de démarrage à utiliser selon le type de projet.
"""
import sys
import json
import subprocess
from pathlib import Path
from .detect_project_type import ProjectType
from .find_free_port import find_free_port
from src.preview.steps.detect_project_type import ProjectType

# Determine Windows platform
is_windows = sys.platform.startswith("win")

def _win_fix(cmd):
    if is_windows and cmd and cmd[0] in ("npm", "npx"):
        cmd[0] = cmd[0] + ".cmd"
    return cmd

def get_start_command(project_dir: str, project_type: str, session_id: str = None):
    project_dir = Path(project_dir)
    env = None
    if project_type == ProjectType.FLASK or (isinstance(project_type, str) and project_type.lower() == "flask"):
        port = find_free_port()
        if port == 5000:
            port = find_free_port(start_port=5001)
        if port is None:
            port = 3000
        if session_id is not None:
            from src.preview.preview_manager import session_ports
            session_ports[session_id] = port
        import os
        # Définir FLASK_RUN_PORT et FLASK_APP pour flask run
        env = os.environ.copy()
        env["FLASK_RUN_PORT"] = str(port)
        # Cherche le fichier principal et configure FLASK_APP
        app_module = None
        for file in ["app.py", "main.py", "server.py", "run.py"]:
            if (project_dir / file).exists():
                app_module = file
                break
        if app_module:
            # Supprimer .py pour FLASK_APP
            env["FLASK_APP"] = app_module.replace('.py', '')
        # Utiliser flask run pour respecter FLASK_RUN_PORT
        # Commande flask run pour forcer le port
        return [sys.executable, "-m", "flask", "run", "--host", "0.0.0.0", "--port", str(port)], env
    # Streamlit projects: use 'streamlit run'
    elif project_type == "streamlit" or (isinstance(project_type, str) and project_type.lower() == "streamlit"):
        port = find_free_port()
        if session_id:
            from src.preview.preview_manager import session_ports
            session_ports[session_id] = port
        # find script
        script = None
        if (project_dir / "app.py").exists():
            script = str(project_dir / "app.py")
        else:
            pyfs = list(project_dir.glob("*.py"))
            if pyfs:
                script = str(pyfs[0])
        if script:
            cmd = ["streamlit", "run", script, "--server.port", str(port)]
            return _win_fix(cmd), env
        else:
            return [sys.executable, str(project_dir)], env
    elif project_type == ProjectType.EXPRESS:
        # Choose port and set environment
        port = find_free_port()
        if session_id:
            from src.preview.preview_manager import session_ports
            session_ports[session_id] = port
        import os
        env = os.environ.copy()
        env["PORT"] = str(port)
        # Direct node entrypoint if exists
        for main in ["server.js", "app.js", "index.js"]:
            if (project_dir / main).exists():
                return _win_fix(["node", str(project_dir / main)]), env
        # fallback on npm start if no entrypoint
        return _win_fix(["npm", "start"]), env
    # PHP projects: launch built-in server
    elif project_type == ProjectType.PHP or (isinstance(project_type, str) and project_type.lower() == "php"):
        port = find_free_port()
        if session_id is not None:
            from src.preview.preview_manager import session_ports
            session_ports[session_id] = port
        # Serve PHP built-in server
        return ["php", "-S", f"0.0.0.0:{port}", "-t", str(project_dir)], env
    elif project_type in [ProjectType.REACT, ProjectType.VUE, ProjectType.ANGULAR]:
        # Use free port for SPA frameworks
        port = find_free_port()
        if session_id:
            from src.preview.preview_manager import session_ports
            session_ports[session_id] = port
        import os
        env = os.environ.copy()
        env["PORT"] = str(port)
        if (project_dir / "package.json").exists():
            try:
                with open(project_dir / "package.json", "r", encoding="utf-8") as f:
                    package_json = json.load(f)
                    scripts = package_json.get("scripts", {})
                    if "start" in scripts:
                        return _win_fix(["npm", "start"]), env
                    elif "dev" in scripts:
                        return _win_fix(["npm", "run", "dev"]), env
                    elif "serve" in scripts:
                        return _win_fix(["npm", "run", "serve"]), env
            except:
                pass
        # Pass PORT env to npm scripts
        return _win_fix(["npm", "start"]), env
    elif project_type == ProjectType.STATIC:
        # Determine directory containing index.html
        serve_dir = project_dir
        for sub in ["public", "src"]:
            if (project_dir / sub / "index.html").exists():
                serve_dir = project_dir / sub
                break
        # If custom scripts available, use npm
        if (project_dir / "package.json").exists():
            try:
                with open(project_dir / "package.json", "r", encoding="utf-8") as f:
                    package_json = json.load(f)
                    scripts = package_json.get("scripts", {})
                    if "start" in scripts:
                        return _win_fix(["npm", "start"]), env
                    elif "dev" in scripts:
                        return _win_fix(["npm", "run", "dev"]), env
                    elif "serve" in scripts:
                        return _win_fix(["npm", "run", "serve"]), env
            except:
                pass
        # Serve via python http.server or npx serve
        port = find_free_port()
        if session_id is not None:
            from src.preview.preview_manager import session_ports
            session_ports[session_id] = port
        # Try python handler
        python_exec = sys.executable
        try:
            return [python_exec, "-m", "http.server", str(port), "--directory", str(serve_dir)], env
        except:
            return _win_fix(["npx", "serve", "-s", str(serve_dir), "-p", str(port)]), env
    else:
        if (project_dir / "package.json").exists():
            try:
                with open(project_dir / "package.json", "r", encoding="utf-8") as f:
                    package_json = json.load(f)
                    scripts = package_json.get("scripts", {})
                    if "start" in scripts:
                        return _win_fix(["npm", "start"]), env
                    elif "dev" in scripts:
                        return _win_fix(["npm", "run", "dev"]), env
                    elif "serve" in scripts:
                        return _win_fix(["npm", "run", "serve"]), env
            except Exception:
                return _win_fix(["npm", "start"]), env
        main_py_files = ["app.py", "main.py", "server.py", "run.py"]
        for file in main_py_files:
            if (project_dir / file).exists():
                return [sys.executable, str(project_dir / file)], env
        main_js_files = ["server.js", "app.js", "index.js", "main.js"]
        for file in main_js_files:
            if (project_dir / file).exists():
                return ["node", str(project_dir / file)], env
        if (project_dir / "index.html").exists() or (project_dir / "public" / "index.html").exists():
            return get_start_command(project_dir, ProjectType.STATIC, session_id)
        return _win_fix(["npm", "start"]), env
