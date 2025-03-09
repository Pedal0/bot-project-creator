import os
import json
import time
import logging
from src.api.api_client import AIAppGeneratorAPI
from src.file_manager.file_manager import FileSystemManager
from src.config import FILE_SIGNATURE_EXTRACTOR_PROMPT, CROSS_FILE_REVIEWER_PROMPT, MAX_TOKENS_DEFAULT, MAX_TOKENS_LARGE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AppGenerator:
    def __init__(self, api_key):
        self._api_client = AIAppGeneratorAPI(api_key)
        self.file_manager = FileSystemManager()
        self._requirements_spec = None
        self._architecture = None
        self._database_schema = None
        self._api_spec = None

    @property
    def api_client(self):
        return self._api_client

    @property
    def project_context(self):
        if not hasattr(self, '_requirements_spec') or self._requirements_spec is None:
            return {}

        return {
            "requirements": self._requirements_spec,
            "architecture": self._architecture,
            "database": self._database_schema,
            "api": self._api_spec
        }

    def _build_requirements_spec(self, user_prompt, include_tests=False, create_docker=False, add_ci_cd=False, app_name=None):
        """Analyze user prompt to build requirements specification"""
        print(f"Analyzing requirements from prompt: '{user_prompt[:50]}...'")

        requirements = self._api_client.analyze_requirements(user_prompt)

        if not requirements:
            raise Exception("Failed to analyze requirements")

        requirements["generate_tests"] = include_tests
        requirements["create_docker"] = create_docker
        requirements["add_ci_cd"] = add_ci_cd

        tech_stack = requirements.get('technical_stack', {})
        if isinstance(tech_stack, dict):
            language = tech_stack.get('language', '').lower()
            framework = tech_stack.get('framework', '').lower()

            if ((language == 'python' and framework in ['flask', 'django']) or
                (language == 'php') or
                (language == 'javascript' and framework in ['express', 'next', 'nuxt']) or
                    (framework in ['laravel', 'symfony', 'rails', 'asp.net'])):

                requirements["unified_frontend_backend"] = True
                print(
                    f"Detected {framework if framework else language} as a unified frontend/backend framework")

        return requirements

    def _design_architecture(self):
        """Design the application architecture based on requirements"""
        if not self._requirements_spec:
            raise Exception("Requirements specification is missing")

        architecture = self._api_client.design_architecture(
            self._requirements_spec)

        if not architecture:
            raise Exception("Failed to design architecture")

        if not isinstance(architecture, dict):
            logger.error(
                f"Architecture design returned invalid format: {type(architecture)}")
            logger.error(f"Architecture content: {architecture[:200]}..." if isinstance(
                architecture, str) else str(architecture))
            raise Exception(
                "Architecture design returned invalid format (not a dict)")

        if 'dependencies' in architecture and isinstance(architecture['dependencies'], list):
            for i, dep in enumerate(architecture['dependencies']):
                if isinstance(dep, dict) and dep.get('name') == 'Flask':
                    architecture['dependencies'][i]['name'] = 'flask'
                elif isinstance(dep, str) and dep == 'Flask':
                    architecture['dependencies'][i] = 'flask'

        return architecture

    def _design_database(self):
        """Design database schema if required by the application"""
        if not self._requirements_spec or not self._architecture:
            raise Exception("Requirements or architecture is missing")

        database_schema = self._api_client.design_database(
            self._requirements_spec, self._architecture)

        if not database_schema:
            logger.warning(
                "Failed to design database schema, continuing without it")
            return {}

        return database_schema

    def _design_api(self):
        """Design API if required by the application"""
        if not self._requirements_spec or not self._architecture:
            raise Exception("Requirements or architecture is missing")

        api_spec = self._api_client.design_api(
            self._requirements_spec, self._architecture)

        if not api_spec:
            logger.warning("Failed to design API, continuing without it")
            return {}

        return api_spec

    def _generate_file_code(self, file_spec):
        """Generate code for a specific file"""
        if not file_spec:
            raise Exception("File specification is missing")

        project_context = {
            "requirements": self._requirements_spec,
            "architecture": self._architecture,
            "database": getattr(self, "_database_design", None),
            "api": getattr(self, "_api_design", None),
            "file": file_spec
        }

        code = self._api_client.generate_code(file_spec, project_context)

        if not code:
            raise Exception(
                f"Failed to generate code for {file_spec.get('path')}")

        return code

    def generate_application(self, user_prompt, output_path, include_tests=False, create_docker=False, add_ci_cd=False, app_name=None):
        """Generate a complete application based on user's description"""
        # Build requirements specification
        self._requirements_spec = self._build_requirements_spec(
            user_prompt, include_tests, create_docker, add_ci_cd)

        # Override app name if provided
        if app_name and isinstance(self._requirements_spec, dict):
            self._requirements_spec["app_name"] = app_name
            print(f"Using custom application name: {app_name}")

        if not isinstance(self._requirements_spec, dict):
            logger.error(
                f"Requirements returned invalid format: {type(self._requirements_spec)}")
            raise Exception(
                "Requirements analysis returned invalid format (not a dict)")

        app_name = self._requirements_spec.get('app_name', 'Unnamed App')
        print(f"Designing architecture for {app_name}")
        self._architecture = self._design_architecture()

        is_unified_framework = self._requirements_spec.get(
            "unified_frontend_backend", False)
        tech_stack = self._requirements_spec.get('technical_stack', {})
        language = tech_stack.get('language', '').lower(
        ) if isinstance(tech_stack, dict) else ''
        framework = tech_stack.get('framework', '').lower(
        ) if isinstance(tech_stack, dict) else ''

        has_flask = False
        has_django = False
        has_php = False
        has_express_with_views = False

        if isinstance(self._architecture.get('dependencies'), list):
            for dep in self._architecture.get('dependencies'):
                dep_name = dep.get('name', '').lower() if isinstance(
                    dep, dict) else str(dep).lower()
                if 'flask' in dep_name:
                    has_flask = True
                    is_unified_framework = True
                elif 'django' in dep_name:
                    has_django = True
                    is_unified_framework = True
                elif 'express' in dep_name and ('ejs' in str(self._architecture) or 'pug' in str(self._architecture) or 'handlebars' in str(self._architecture)):
                    has_express_with_views = True
                    is_unified_framework = True

        if language == 'php':
            has_php = True
            is_unified_framework = True

        if is_unified_framework:
            print(
                f"Using unified frontend/backend architecture for {framework or language}")
            if has_flask or framework == 'flask':
                self._adjust_architecture_for_templates('flask')
            elif has_django or framework == 'django':
                self._adjust_architecture_for_templates('django')
            elif has_php or language == 'php':
                self._adjust_architecture_for_templates('php')
            elif has_express_with_views or (framework == 'express' and 'view' in str(self._architecture)):
                self._adjust_architecture_for_templates('express')
            else:
                self._adjust_architecture_for_templates('generic')

        if isinstance(self._requirements_spec.get('components', []), list) and any('database' in comp.get('type', '')
                                                                                   for comp in self._requirements_spec.get('components', []) if isinstance(comp, dict)):
            print("Designing database schema")
            self._database_schema = self._design_database()
        else:
            self._database_schema = {}

        if isinstance(self._requirements_spec.get('components', []), list) and any('api' in comp.get('type', '')
                                                                                   for comp in self._requirements_spec.get('components', []) if isinstance(comp, dict)):
            print("Designing API interfaces")
            self._api_spec = self._design_api()
        else:
            self._api_spec = {}

        tech_stack = self._requirements_spec.get('technical_stack', {})
        language = tech_stack.get('language', '').lower(
        ) if isinstance(tech_stack, dict) else ''
        framework = tech_stack.get('framework', '').lower(
        ) if isinstance(tech_stack, dict) else ''

        has_flask = False
        if isinstance(self._architecture.get('dependencies'), list):
            for dep in self._architecture.get('dependencies'):
                if isinstance(dep, dict) and dep.get('name', '').lower() == 'flask':
                    has_flask = True
                    break
                elif isinstance(dep, str) and dep.lower() == 'flask':
                    has_flask = True
                    break

        if language == 'python' and not framework and has_flask:
            print(
                "Detected Python backend with HTML/JS frontend - assuming Flask framework")
            framework = 'flask'
            if isinstance(tech_stack, dict):
                tech_stack['framework'] = 'flask'
                self._requirements_spec['technical_stack'] = tech_stack

        if language == 'python' and ('flask' in framework or 'django' in framework):
            print(
                f"Detected {framework.capitalize()} framework - integrating frontend into templates")
            self._adjust_architecture_for_templates(
                'flask' if 'flask' in framework else 'django')
        elif language == 'php':
            print("Detected PHP - embedding HTML in PHP files")
            self._adjust_architecture_for_templates('php')

        print(f"Creating project structure at {output_path}")
        files_to_generate = self.file_manager.create_project_structure(
            output_path, self._architecture)
        print(f"Generating {len(files_to_generate)} files")

        generated_files = []
        file_counter = 0

        for file_spec in files_to_generate:
            file_counter += 1
            file_path = file_spec.get("path", "")
            if not file_path:
                continue

            print(
                f"Generating file: {file_path} ({file_counter}/{len(files_to_generate)})")
            file_code = self._generate_file_code(file_spec)
            absolute_path = self.file_manager.write_code_to_file(
                output_path, file_path, file_code)
            generated_files.append({
                "path": file_path,
                "absolute_path": absolute_path,
                "spec": file_spec
            })

        file_structure = []
        for root, dirs, files in os.walk(output_path):
            rel_root = os.path.relpath(root, output_path)
            if rel_root == ".":
                rel_root = ""
            for file in files:
                file_path = os.path.join(rel_root, file) if rel_root else file
                file_structure.append(file_path)

        print("Generating configuration and documentation files")

        tech_stack = self._requirements_spec.get('technical_stack', {})
        language = tech_stack.get('language', '').lower(
        ) if isinstance(tech_stack, dict) else ''

        if language not in ['javascript', 'typescript', 'node', 'react', 'vue', 'angular']:
            print("Generating requirements.txt")
            requirements_content = self._api_client.generate_project_file(
                'requirements.txt',
                self.project_context,
                file_structure
            )
            with open(os.path.join(output_path, "requirements.txt"), 'w', encoding='utf-8') as f:
                f.write(requirements_content)

        if language in ['javascript', 'typescript', 'node', 'react', 'vue', 'angular']:
            print("Generating package.json")
            package_json_content = self._api_client.generate_project_file(
                'package.json',
                self.project_context,
                file_structure
            )
            with open(os.path.join(output_path, "package.json"), 'w', encoding='utf-8') as f:
                f.write(package_json_content)

        print("Generating README.md")
        readme_content = self._api_client.generate_project_file(
            'README.md',
            self.project_context,
            file_structure
        )
        with open(os.path.join(output_path, "README.md"), 'w', encoding='utf-8') as f:
            f.write(readme_content)

        print("Extracting file signatures for comprehensive validation")
        file_signatures = {}
        all_file_contents = {}

        for file_info in generated_files:
            if file_info["path"].endswith(('.py', '.js', '.ts', '.jsx', '.tsx')):
                try:
                    with open(file_info["absolute_path"], 'r', encoding='utf-8') as f:
                        file_content = f.read()
                        all_file_contents[file_info["path"]] = file_content
                except Exception as e:
                    print(
                        f"Warning: Could not read {file_info['path']}: {str(e)}")

        if all_file_contents:
            print("Performing cross-file validation on all files")
            try:
                results = self._api_client.cross_file_code_reviewer(
                    all_file_contents, self.project_context)

                for file_path, fixed_content in results.items():
                    if fixed_content != "PARFAIT":
                        print(f"Fixing issues in {file_path}")
                        self.file_manager.write_code_to_file(
                            output_path, file_path, fixed_content)
            except Exception as e:
                print(f"Warning: Cross-file validation failed: {str(e)}")

        print(f"Project successfully generated at {output_path}")
        return output_path

    def _adjust_architecture_for_templates(self, framework):
        if not self._architecture or not isinstance(self._architecture, dict):
            logger.warning("No valid architecture to adjust")
            return

        files = self._architecture.get('files', [])
        if not files:
            logger.warning("No files found in architecture to adjust")
            return

        frontend_files = []
        backend_files = []
        other_files = []

        for file in files:
            if not isinstance(file, dict):
                other_files.append(file)
                continue

            file_path = file.get('path', '')
            file_type = file.get('type', '').lower()
            file_purpose = file.get('purpose', '').lower()

            if (file_path.endswith(('.html', '.css', '.js')) and not file_path.endswith('.min.js') and
                not '/static/' in file_path and not '/assets/' in file_path) or \
               'frontend' in file_path.lower() or \
               any(kw in file_purpose for kw in ['frontend', 'ui', 'interface', 'html', 'template']):
                frontend_files.append(file)
            elif (framework == 'flask' and 'flask' in file_purpose) or \
                 (framework == 'django' and 'django' in file_purpose) or \
                 (framework == 'php' and file_path.endswith('.php')) or \
                'backend' in file_path.lower() or \
                'api' in file_path.lower() or \
                    'server' in file_path.lower():
                backend_files.append(file)
            else:
                other_files.append(file)

        if framework == 'flask':
            self._adjust_for_flask(frontend_files, backend_files, other_files)
        elif framework == 'django':
            self._adjust_for_django(frontend_files, backend_files, other_files)
        elif framework == 'php':
            self._adjust_for_php(frontend_files, backend_files, other_files)
        elif framework == 'express':
            self._adjust_for_express(
                frontend_files, backend_files, other_files)
        else:
            self._adjust_for_generic(
                frontend_files, backend_files, other_files)

    def _adjust_for_flask(self, frontend_files, backend_files, other_files):
        templates_dir = "templates"
        static_dir = "static"

        templates_exists = False
        static_exists = False

        for file in backend_files:
            if isinstance(file, dict) and file.get('path', '').startswith(templates_dir + '/'):
                templates_exists = True
            if isinstance(file, dict) and file.get('path', '').startswith(static_dir + '/'):
                static_exists = True

        new_files = other_files

        for file in frontend_files:
            if isinstance(file, dict):
                path = file.get('path', '')
                file_name = os.path.basename(path)

                if path.startswith('frontend/'):
                    path = path.replace('frontend/', '', 1)
                    file_name = os.path.basename(path)

                if path.endswith('.html'):
                    file['path'] = f"{templates_dir}/{file_name}"
                    new_files.append(file)
                elif path.endswith(('.css', '.js')):
                    file['path'] = f"{static_dir}/{file_name}"
                    new_files.append(file)
                else:
                    new_files.append(file)
            else:
                new_files.append(file)

        for file in backend_files:
            if isinstance(file, dict):
                path = file.get('path', '')

                if path.startswith('backend/'):
                    parts = path.split('/')
                    if len(parts) > 1:
                        new_path = '/'.join(parts[1:])
                        file['path'] = new_path

                new_files.append(file)
            else:
                new_files.append(file)

        self._architecture['files'] = new_files

        directories = self._architecture.get('directories', [])

        if 'frontend' in directories:
            directories.remove('frontend')

        if 'backend' in directories:
            directories.remove('backend')

        if templates_dir not in directories and not templates_exists:
            directories.append(templates_dir)
        if static_dir not in directories and not static_exists:
            directories.append(static_dir)

        self._architecture['directories'] = directories

    def _adjust_for_django(self, frontend_files, backend_files, other_files):
        app_name = self._requirements_spec.get(
            'app_name', 'main').lower().replace(' ', '_')
        templates_dir = f"{app_name}/templates/{app_name}"
        static_dir = f"{app_name}/static/{app_name}"

        new_files = backend_files + other_files

        for file in frontend_files:
            if isinstance(file, dict):
                path = file.get('path', '')
                file_name = os.path.basename(path)

                if path.endswith('.html'):
                    file['path'] = f"{templates_dir}/{file_name}"
                    new_files.append(file)
                elif path.endswith(('.css', '.js')):
                    file['path'] = f"{static_dir}/{file_name}"
                    new_files.append(file)
                else:
                    new_files.append(file)
            else:
                new_files.append(file)

        self._architecture['files'] = new_files

        directories = self._architecture.get('directories', [])
        for dir_path in [templates_dir, static_dir]:
            parts = dir_path.split('/')
            current_path = ""
            for part in parts:
                current_path = current_path + \
                    part if current_path == "" else f"{current_path}/{part}"
                if current_path not in directories:
                    directories.append(current_path)

        self._architecture['directories'] = directories

    def _adjust_for_php(self, frontend_files, backend_files, other_files):
        html_to_php_map = {}

        for html_file in frontend_files:
            if isinstance(html_file, dict) and html_file.get('path', '').endswith('.html'):
                html_path = html_file.get('path', '')
                html_name = os.path.splitext(os.path.basename(html_path))[0]

                for php_file in backend_files:
                    if isinstance(php_file, dict):
                        php_path = php_file.get('path', '')
                        php_name = os.path.splitext(
                            os.path.basename(php_path))[0]

                        if php_name == html_name or php_path.endswith(f"{html_name}.php"):
                            html_to_php_map[html_path] = php_path
                            break

        new_files = other_files
        for file in backend_files:
            new_files.append(file)

        for file in frontend_files:
            if isinstance(file, dict):
                path = file.get('path', '')

                if path in html_to_php_map:
                    continue

                if path.endswith('.html'):
                    new_path = path.replace('.html', '.php')
                    file['path'] = new_path
                    file['type'] = 'php'
                    new_files.append(file)
                else:
                    new_files.append(file)
            else:
                new_files.append(file)

        self._architecture['files'] = new_files

    def _adjust_for_express(self, frontend_files, backend_files, other_files):
        views_dir = "views"
        public_dir = "public"

        new_files = other_files

        for file in frontend_files:
            if isinstance(file, dict):
                path = file.get('path', '')
                file_name = os.path.basename(path)

                if path.endswith(('.html', '.ejs', '.pug', '.hbs')):
                    file['path'] = f"{views_dir}/{file_name}"
                    new_files.append(file)
                elif path.endswith(('.css', '.js', '.jpg', '.png')):
                    file['path'] = f"{public_dir}/{file_name}"
                    new_files.append(file)
                else:
                    new_files.append(file)
            else:
                new_files.append(file)

        for file in backend_files:
            if isinstance(file, dict):
                path = file.get('path', '')

                if path.startswith('backend/'):
                    file['path'] = path.replace('backend/', '', 1)

                new_files.append(file)
            else:
                new_files.append(file)

        self._architecture['files'] = new_files

        directories = self._architecture.get('directories', [])

        if 'frontend' in directories:
            directories.remove('frontend')
        if 'backend' in directories:
            directories.remove('backend')

        if views_dir not in directories:
            directories.append(views_dir)
        if public_dir not in directories:
            directories.append(public_dir)

        self._architecture['directories'] = directories

    def _adjust_for_generic(self, frontend_files, backend_files, other_files):
        new_files = other_files

        for file in frontend_files:
            if isinstance(file, dict):
                path = file.get('path', '')

                if path.startswith('frontend/'):
                    file['path'] = path.replace('frontend/', '', 1)

                new_files.append(file)
            else:
                new_files.append(file)

        for file in backend_files:
            if isinstance(file, dict):
                path = file.get('path', '')

                if path.startswith('backend/'):
                    file['path'] = path.replace('backend/', '', 1)

                new_files.append(file)
            else:
                new_files.append(file)

        self._architecture['files'] = new_files

        directories = self._architecture.get('directories', [])

        if 'frontend' in directories:
            directories.remove('frontend')
        if 'backend' in directories:
            directories.remove('backend')

        self._architecture['directories'] = directories
