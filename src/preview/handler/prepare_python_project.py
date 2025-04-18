"""
Prépare et lance un projet Python (venv, install, run).
"""
import subprocess
import sys
import os
from pathlib import Path

def prepare_python_project(project_dir, main_file=None):
    """
    Crée un venv, installe les dépendances et lance le projet python.
    Args:
        project_dir (str or Path): Dossier du projet
        main_file (str, optional): Fichier principal à lancer
    Returns:
        tuple: (succès, message)
    """
    project_dir = Path(project_dir)
    venv_dir = project_dir / 'venv'
    try:
        if not venv_dir.exists():
            subprocess.check_call([sys.executable, '-m', 'venv', str(venv_dir)])
        pip_path = venv_dir / ('Scripts' if sys.platform == 'win32' else 'bin') / 'pip'
        req = project_dir / 'requirements.txt'
        if req.exists():
            subprocess.check_call([str(pip_path), 'install', '-r', str(req)])
        # Dependencies installed; script execution will be handled by start_preview
        return True, "Environnement Python préparé et dépendances installées."
    except Exception as e:
        return False, f"Erreur Python: {e}"
