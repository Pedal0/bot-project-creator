import os
import sys
import subprocess
import logging
import json
from typing import Dict, Any, Optional, Tuple, List
from src.config import APP_FIXER_PROMPT

from .environment_setup import setup_environment
from .app_runner import try_start_application
from .dependency_detector import detect_javascript_dependencies
from .requirements_cleaner import create_clean_requirements_cmd
from .entry_point_finder import find_python_entry_point, find_js_entry_point
from .error_fixer import identify_error_file, fix_file_with_ai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AppValidator:
    def __init__(self, api_client):
        self.api_client = api_client
        self.max_fix_attempts = 3
        
    def validate_app(self, app_path: str, project_context: Dict[str, Any]) -> bool:
        language = project_context.get("architecture", {}).get("language", "python").lower()
        
        logger.info(f"Validating {language} application at {app_path}")
        
        js_dependencies = detect_javascript_dependencies(app_path, project_context)
        if js_dependencies and not os.path.exists(os.path.join(app_path, "package.json")):
            self._create_package_json(app_path, js_dependencies)
        
        env_setup_cmds, start_cmd = self._get_env_and_start_commands(app_path, language)
        
        if not setup_environment(app_path, env_setup_cmds):
            logger.error("Failed to setup environment")
            return False
            
        success, error_info = try_start_application(app_path, start_cmd)
        
        if success:
            logger.info("Application started successfully")
            return True
            
        return self._attempt_fix_application(app_path, error_info, project_context)

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
        
        for dep in dependencies:
            package["dependencies"][dep] = "latest"
        
        if "chart.js" in dependencies:
            package["dependencies"]["chart.js"] = "^4.0.0"
        
        if "react" in dependencies:
            package["dependencies"]["react-scripts"] = "5.0.1"
            package["scripts"]["start"] = "react-scripts start"
        
        if "vue" in dependencies:
            package["dependencies"]["vue-cli-service"] = "^5.0.0"
            package["scripts"]["start"] = "vue-cli-service serve"
        
        package_path = os.path.join(app_path, "package.json")
        with open(package_path, 'w', encoding='utf-8') as f:
            json.dump(package, f, indent=2)
        
        self._update_readme_with_js_dependencies(app_path, dependencies)

    def _update_readme_with_js_dependencies(self, app_path: str, dependencies: List[str]) -> None:
        """Update README.md with JavaScript dependencies installation instructions"""
        readme_path = os.path.join(app_path, "README.md")
        
        if not os.path.exists(readme_path):
            return
        
        try:
            with open(readme_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                
            if "npm install" in content:
                return
            
            js_section = "\n## JavaScript Dependencies\n\n"
            js_section += "This application uses JavaScript libraries that need to be installed separately:\n\n"
            js_section += "```bash\n"
            js_section += "# Install JavaScript dependencies\n"
            js_section += "npm install\n"
            js_section += "```\n\n"
            
            if "chart.js" in dependencies:
                js_section += "This will install Chart.js for data visualization.\n\n"
            
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
        """Get environment setup and application start commands based on language"""
        if language == "python":
            env_cmds = [
                f"{'python -m venv' if sys.platform != 'win32' else 'python -m venv'} .venv",
                f"{'source .venv/bin/activate' if sys.platform != 'win32' else '.venv\\Scripts\\activate'}"
            ]
            
            if os.path.exists(os.path.join(app_path, "requirements.txt")):
                env_cmds.append(create_clean_requirements_cmd(app_path))
            
            entry_point = find_python_entry_point(app_path)
            
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
                            entry_point = find_js_entry_point(app_path)
                            if entry_point:
                                rel_path = os.path.relpath(entry_point, app_path)
                                start_cmd = ["node", rel_path]
                                logger.info(f"Found JS entry point: {rel_path}")
                            else:
                                start_cmd = ["cmd", "/c", "echo", "No JS entry point found"]
                    except:
                        start_cmd = ["cmd", "/c", "echo", "Invalid package.json"]
            else:
                entry_point = find_js_entry_point(app_path)
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
    
    def _attempt_fix_application(self, app_path: str, error_info: Dict[str, Any], 
                               project_context: Dict[str, Any]) -> bool:
        """Attempt to fix application issues automatically"""
        for attempt in range(self.max_fix_attempts):
            logger.info(f"Fix attempt {attempt + 1}/{self.max_fix_attempts}")
            
            error_file = identify_error_file(app_path, error_info)
            if not error_file:
                logger.error("Could not identify the file causing the error")
                return False
                
            try:
                with open(error_file, 'r') as f:
                    file_content = f.read()
            except Exception as e:
                logger.error(f"Could not read file {error_file}: {str(e)}")
                return False
                
            fixed_content = fix_file_with_ai(
                self.api_client,
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
            
            success, new_error_info = try_start_application(app_path, start_cmd)
            
            if success:
                logger.info("Application fixed and started successfully")
                return True
                
            error_info = new_error_info
            
        logger.error(f"Failed to fix application after {self.max_fix_attempts} attempts")
        return False
