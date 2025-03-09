import os
import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class FileSystemManager:
    def __init__(self):
        pass
        
    def create_project_structure(self, output_path: str, architecture: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not os.path.exists(output_path):
            os.makedirs(output_path)
            
        files_to_generate = []
        directories = set()
        
        for file_spec in architecture.get("files", []):
            file_path = file_spec.get("path", "")
            if file_path:
                dir_path = os.path.dirname(file_path)
                if dir_path:
                    directories.add(os.path.join(output_path, dir_path))
                files_to_generate.append(file_spec)
        
        for directory in sorted(directories):
            os.makedirs(directory, exist_ok=True)
            
        for directory in directories:
            if any(os.path.basename(f) == "__init__.py" for f in os.listdir(directory)):
                continue
            
            if any(f.endswith(".py") for f in os.listdir(directory)):
                init_path = os.path.join(directory, "__init__.py")
                with open(init_path, 'w') as f:
                    f.write("")
                    
        return files_to_generate
    
    def write_code_to_file(self, output_path: str, file_path: str, code_content: str) -> str:
        absolute_path = os.path.join(output_path, file_path)
        
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
        
        # Clean markdown code blocks formatting
        cleaned_content = self._clean_markdown_code_blocks(code_content)
        
        with open(absolute_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
            
        return absolute_path

    def _clean_markdown_code_blocks(self, content: str) -> str:        
        pattern = r"```[a-zA-Z0-9_+#-]*\n([\s\S]*?)\n```"
        
        matches = re.findall(pattern, content)
        if matches:
            return matches[0]
        
        return content