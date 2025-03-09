import os
import sys
import subprocess
import logging
import tempfile
import json
import time
import shutil
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from src.config import (
    APP_FIXER_PROMPT,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AppValidator:
    def __init__(self, api_client):
        self.api_client = api_client
        self.max_fix_attempts = 3
        
    def validate_app(self, app_path: str, project_context: Dict[str, Any]) -> bool:
        language = project_context.get("architecture", {}).get("language", "python").lower()
        
        logger.info(f"Validating {language} application at {app_path}")
        
        # Améliorer la détection des dépendances JavaScript
        js_dependencies = self._detect_javascript_dependencies(app_path, project_context)
        if js_dependencies and not os.path.exists(os.path.join(app_path, "package.json")):
            self._create_package_json(app_path, js_dependencies)
        
        env_setup_cmds, start_cmd = self._get_env_and_start_commands(app_path, language)
        
        if not self._setup_environment(app_path, env_setup_cmds):
            logger.error("Failed to setup environment")
            return False
            
        success, error_info = self._try_start_application(app_path, start_cmd)
        
        if success:
            logger.info("Application started successfully")
            return True
            
        return self._attempt_fix_application(app_path, error_info, project_context)

    def _detect_javascript_dependencies(self, app_path: str, project_context: Dict[str, Any]) -> List[str]:
        """Detect JavaScript dependencies from project content"""
        js_dependencies = []
        
        # Check for JavaScript libraries in requirements.txt
        req_path = os.path.join(app_path, "requirements.txt")
        if os.path.exists(req_path):
            with open(req_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read().lower()
                if 'chart.js' in content or 'chartjs' in content:
                    js_dependencies.append("chart.js")
                if 'react' in content:
                    js_dependencies.append("react")
                    js_dependencies.append("react-dom")
                if 'vue' in content:
                    js_dependencies.append("vue")
                if 'angular' in content:
                    js_dependencies.append("@angular/core")
        
        # Check for JavaScript libraries in code files
        for root, dirs, files in os.walk(app_path):
            for file in files:
                if file.endswith(('.js', '.html', '.py')):
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8', errors='replace') as f:
                            content = f.read().lower()
                            if 'chart.js' in content or 'chartjs' in content:
                                js_dependencies.append("chart.js")
                            if 'import react' in content or 'from react' in content:
                                js_dependencies.append("react")
                                js_dependencies.append("react-dom")
                            if 'import vue' in content or 'from vue' in content:
                                js_dependencies.append("vue")
                            if 'import { component }' in content and 'angular' in content:
                                js_dependencies.append("@angular/core")
                    except:
                        pass
        
        # Remove duplicates
        return list(set(js_dependencies))

    def _create_package_json(self, app_path: str, dependencies: List[str]) -> None:
        """Create a package.json file with the detected dependencies"""
        logger.info(f"Creating package.json with dependencies: {dependencies}")
        
        package = {
            "name": os.path.basename(app_path),
            "version": "1.0.0",
            "description": "Generated application",
            "scripts": {
                "start": "node index.js"
            },
            "dependencies": {}
        }
        
        # Add detected dependencies
        for dep in dependencies:
            package["dependencies"][dep] = "latest"
        
        # Add additional dependencies based on what was detected
        if "chart.js" in dependencies:
            package["dependencies"]["chart.js"] = "^4.0.0"
        
        if "react" in dependencies:
            package["dependencies"]["react-scripts"] = "5.0.1"
            package["scripts"]["start"] = "react-scripts start"
        
        if "vue" in dependencies:
            package["dependencies"]["vue-cli-service"] = "^5.0.0"
            package["scripts"]["start"] = "vue-cli-service serve"
        
        # Write the package.json file
        package_path = os.path.join(app_path, "package.json")
        with open(package_path, 'w', encoding='utf-8') as f:
            json.dump(package, f, indent=2)
        
        # Also update README with instructions
        self._update_readme_with_js_dependencies(app_path, dependencies)

    def _update_readme_with_js_dependencies(self, app_path: str, dependencies: List[str]) -> None:
        """Update README.md with JavaScript dependencies installation instructions"""
        readme_path = os.path.join(app_path, "README.md")
        
        if not os.path.exists(readme_path):
            return
        
        try:
            with open(readme_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                
            # Check if there's a JavaScript section already
            if "npm install" in content:
                return
            
            # Add a JavaScript dependencies section
            js_section = "\n## JavaScript Dependencies\n\n"
            js_section += "This application uses JavaScript libraries that need to be installed separately:\n\n"
            js_section += "```bash\n"
            js_section += "# Install JavaScript dependencies\n"
            js_section += "npm install\n"
            js_section += "```\n\n"
            
            if "chart.js" in dependencies:
                js_section += "This will install Chart.js for data visualization.\n\n"
            
            # Find a good place to insert this section - after installation but before usage
            if "## Usage" in content:
                content = content.replace("## Usage", js_section + "## Usage")
            elif "## Installation" in content:
                content = content.replace("## Installation", "## Installation" + js_section)
            else:
                content += js_section
            
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        except Exception as e:
            logger.error(f"Failed to update README with JS dependencies: {str(e)}")

    def _get_env_and_start_commands(self, app_path: str, language: str) -> Tuple[List[str], List[str]]:
        
        if language == "python":
            env_cmds = [
                f"{'python -m venv' if sys.platform != 'win32' else 'python -m venv'} .venv",
                f"{'source .venv/bin/activate' if sys.platform != 'win32' else '.venv\\Scripts\\activate'}"
            ]
            
            # Clean requirements.txt to remove JS dependencies before installing
            if os.path.exists(os.path.join(app_path, "requirements.txt")):
                env_cmds.append(self._create_clean_requirements_cmd(app_path))
            
            entry_point = self._find_python_entry_point(app_path)
            
            if entry_point:
                rel_path = os.path.relpath(entry_point, app_path)
                start_cmd = ["python", rel_path]
                logger.info(f"Found Python entry point: {rel_path}")
            else:
                logger.warning("No Python entry point found.")
                start_cmd = ["cmd", "/c", "echo", "No Python entry point found"]
                
        elif language in ["node", "javascript", "typescript"]:
            env_cmds = [
                "npm install"
            ]
            
            if os.path.exists(os.path.join(app_path, "package.json")):
                with open(os.path.join(app_path, "package.json")) as f:
                    try:
                        pkg_json = json.load(f)
                        if "scripts" in pkg_json and "start" in pkg_json["scripts"]:
                            start_cmd = ["npm", "start"]
                            logger.info("Using 'npm start' from package.json")
                        else:
                            entry_point = self._find_js_entry_point(app_path)
                            if entry_point:
                                rel_path = os.path.relpath(entry_point, app_path)
                                start_cmd = ["node", rel_path]
                                logger.info(f"Found JS entry point: {rel_path}")
                            else:
                                start_cmd = ["cmd", "/c", "echo", "No JS entry point found"]
                    except:
                        start_cmd = ["cmd", "/c", "echo", "Invalid package.json"]
            else:
                entry_point = self._find_js_entry_point(app_path)
                if entry_point:
                    rel_path = os.path.relpath(entry_point, app_path)
                    start_cmd = ["node", rel_path]
                    logger.info(f"Found JS entry point: {rel_path}")
                else:
                    start_cmd = ["cmd", "/c", "echo", "No JS entry point found"]
                
        else:
            env_cmds = []
            start_cmd = ["cmd", "/c", "echo", f"Validation not supported for {language}"]
            
        return env_cmds, start_cmd

    def _create_clean_requirements_cmd(self, app_path: str) -> str:
        """Clean requirements.txt of JavaScript dependencies and fix package casing"""
        try:
            req_path = os.path.join(app_path, "requirements.txt")
            
            with open(req_path, 'r', encoding='utf-8', errors='replace') as f:
                requirements = []
                for line in f:
                    line = line.strip()
                    # Skip markdown formatting artifacts, empty lines, comments, and JavaScript dependencies
                    if (not line or line.startswith('#') or line.startswith('```') or 
                        any(js_lib in line.lower() for js_lib in ['chart.js', 'react', 'vue', 'angular', '.js', 
                                                                 'webpack', 'babel', 'jquery', 'npm', 'node'])):
                        continue
                    
                    # Correct Flask casing
                    if line.lower() == 'flask' or line.lower().startswith('flask=') or line.lower().startswith('flask=='):
                        line = line.replace('Flask', 'flask')
                    
                    requirements.append(line)
            
            # Write back to the original requirements file
            with open(req_path, 'w', encoding='utf-8') as f:
                for req in requirements:
                    f.write(f"{req}\n")
                    
            return f"pip install -r requirements.txt"
        except Exception as e:
            logger.error(f"Failed to clean requirements.txt: {str(e)}")
            return "echo 'Failed to clean requirements.txt'"

    def _find_python_entry_point(self, app_path: str) -> Optional[str]:
        priority_files = [
            "app.py", "main.py", "server.py", "run.py", "manage.py",
            "wsgi.py", "asgi.py", "index.py", "application.py"
        ]
        
        for filename in priority_files:
            path = os.path.join(app_path, filename)
            if os.path.exists(path):
                return path
        
        backend_dirs = ["backend", "server", "api", "src"]
        for dirname in backend_dirs:
            subdir = os.path.join(app_path, dirname)
            if os.path.isdir(subdir):
                for filename in priority_files:
                    path = os.path.join(subdir, filename)
                    if os.path.exists(path):
                        return path
        
        for root, dirs, files in os.walk(app_path):
            dirs[:] = [d for d in dirs if d not in ["node_modules", ".venv", "venv", ".git", "__pycache__"]]
            
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read().lower()
                            if ("if __name__ == '__main__'" in content or 
                                "app.run(" in content or
                                "runserver" in content):
                                return path
                    except:
                        pass
        
        return None
        
    def _find_js_entry_point(self, app_path: str) -> Optional[str]:
        priority_files = [
            "index.js", "server.js", "app.js", "main.js", "start.js"
        ]
        
        for filename in priority_files:
            path = os.path.join(app_path, filename)
            if os.path.exists(path):
                return path
                
        js_dirs = ["src", "server", "backend", "api"]
        for dirname in js_dirs:
            subdir = os.path.join(app_path, dirname)
            if os.path.isdir(subdir):
                for filename in priority_files:
                    path = os.path.join(subdir, filename)
                    if os.path.exists(path):
                        return path
        
        return None
    
    def _setup_environment(self, app_path: str, setup_cmds: List[str]) -> bool:
        try:
            for cmd in setup_cmds:
                logger.info(f"Running: {cmd}")
                shell = True if sys.platform == "win32" else False
                process = subprocess.run(
                    cmd, 
                    shell=shell, 
                    cwd=app_path,
                    capture_output=True,
                    text=True,
                    timeout=180  
                )
                
                if process.returncode != 0:
                    logger.error(f"Command failed: {cmd}")
                    logger.error(f"Error: {process.stderr}")
                    return False
                    
            return True
        except Exception as e:
            logger.error(f"Environment setup failed: {str(e)}")
            return False
    
    def _try_start_application(self, app_path: str, start_cmd: List[str]) -> Tuple[bool, Dict[str, Any]]:
        logger.info(f"Starting application with: {' '.join(start_cmd)}")
        
        try:
            if start_cmd[0] in ["cmd", "echo"]:
                logger.warning("Using fallback command, skipping execution test")
                return False, {"error": "No suitable entry point found", "cmd": start_cmd}
                
            process = subprocess.Popen(
                start_cmd,
                cwd=app_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            time.sleep(5)
            
            if process.poll() is None:
                process.terminate()
                return True, {}
            else:
                stdout, stderr = process.communicate()
                
                error_info = {
                    "returncode": process.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "cmd": start_cmd
                }
                
                logger.error(f"Application failed to start. Error: {stderr}")
                return False, error_info
                
        except Exception as e:
            logger.error(f"Exception during application start: {str(e)}")
            return False, {"error": str(e), "cmd": start_cmd}
    
    def _attempt_fix_application(self, app_path: str, error_info: Dict[str, Any], 
                               project_context: Dict[str, Any]) -> bool:
        """
        Tente de corriger l'application en fonction des erreurs détectées
        """
        for attempt in range(self.max_fix_attempts):
            logger.info(f"Fix attempt {attempt + 1}/{self.max_fix_attempts}")
            
            error_file = self._identify_error_file(app_path, error_info)
            if not error_file:
                logger.error("Could not identify the file causing the error")
                return False
                
            try:
                with open(error_file, 'r') as f:
                    file_content = f.read()
            except Exception as e:
                logger.error(f"Could not read file {error_file}: {str(e)}")
                return False
                
            fixed_content = self._fix_file_with_ai(
                error_file, 
                file_content, 
                error_info, 
                project_context
            )
            
            if not fixed_content:
                logger.error("Failed to get fixed content from AI")
                return False
                
            try:
                with open(error_file, 'w') as f:
                    f.write(fixed_content)
            except Exception as e:
                logger.error(f"Could not write fixed content to {error_file}: {str(e)}")
                return False
                
            env_setup_cmds, start_cmd = self._get_env_and_start_commands(
                app_path, 
                project_context.get("architecture", {}).get("language", "python").lower()
            )
            
            success, new_error_info = self._try_start_application(app_path, start_cmd)
            
            if success:
                logger.info("Application fixed and started successfully")
                return True
                
            error_info = new_error_info
            
        logger.error(f"Failed to fix application after {self.max_fix_attempts} attempts")
        return False
    
    def _identify_error_file(self, app_path: str, error_info: Dict[str, Any]) -> Optional[str]:
        if "stderr" not in error_info:
            return None
            
        error_text = error_info.get("stderr", "") + error_info.get("stdout", "")
        
        lines = error_text.split('\n')
        for line in lines:
            if "File " in line and ".py" in line:
                parts = line.split('File "', 1)
                if len(parts) > 1:
                    file_path = parts[1].split('"', 1)[0]
                    
                    if not os.path.isabs(file_path):
                        file_path = os.path.join(app_path, file_path)
                        
                    if os.path.exists(file_path):
                        return file_path
            
            elif ".js:" in line or ".ts:" in line:
                parts = line.split(":", 1)
                file_path = parts[0]
                
                if os.path.exists(file_path):
                    return file_path
                
                rel_path = os.path.join(app_path, file_path)
                if os.path.exists(rel_path):
                    return rel_path
        main_files = ["app.py", "main.py", "index.js", "server.js"]
        for file in main_files:
            file_path = os.path.join(app_path, file)
            if os.path.exists(file_path):
                return file_path
                
        return None
    
    def _fix_file_with_ai(self, file_path: str, file_content: str, 
                        error_info: Dict[str, Any], project_context: Dict[str, Any]) -> Optional[str]:
        
        fix_context = {
            "file_path": os.path.basename(file_path),
            "file_content": file_content,
            "error_message": error_info.get("stderr", "") + "\n" + error_info.get("stdout", ""),
            "project_context": project_context
        }
        
        response = self.api_client.call_agent(
            APP_FIXER_PROMPT,
            json.dumps(fix_context),
            max_tokens=4096
        )
        
        if not response:
            return None
            
        return self._extract_code_content(response, os.path.basename(file_path))
        
    def _extract_code_content(self, response: str, file_path: str) -> Optional[str]:
        if "```" in response:
            start_markers = ["```python", "```javascript", "```java", "```typescript", "```"]
            for marker in start_markers:
                if marker in response:
                    parts = response.split(marker, 1)
                    if len(parts) > 1:
                        code_part = parts[1]
                        end_marker_pos = code_part.find("```")
                        if end_marker_pos != -1:
                            return code_part[:end_marker_pos].strip()
                            
        if file_path in response:
            lines = response.split('\n')
            for i, line in enumerate(lines):
                if file_path in line and i+1 < len(lines):
                    return '\n'.join(lines[i+1:])
                    
        return response