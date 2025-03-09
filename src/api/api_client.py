import json
import openai
import time
import logging
from typing import Dict, List, Any, Optional

from src.config import (
    REQUIREMENTS_ANALYZER_PROMPT,
    ARCHITECTURE_DESIGNER_PROMPT,
    DATABASE_DESIGNER_PROMPT,
    API_DESIGNER_PROMPT,
    CODE_GENERATOR_PROMPT,
    TEST_GENERATOR_PROMPT,
    CODE_REVIEWER_PROMPT,
    FILE_SIGNATURE_EXTRACTOR_PROMPT,
    CROSS_FILE_REVIEWER_PROMPT,
    PROMPT_REFORMULATOR_PROMPT,
    API_MODEL,
    API_TEMPERATURE,
    MAX_TOKENS_DEFAULT,
    MAX_TOKENS_LARGE,
    PROJECT_FILES_GENERATOR_PROMPT

)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AIAppGeneratorAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        openai.api_key = api_key
        self.model = API_MODEL
        self.temperature = API_TEMPERATURE
        self.max_retries = 3
        self.retry_delay = 2

    def call_agent(self, prompt: str, user_input: str, max_tokens: int = MAX_TOKENS_DEFAULT) -> Optional[str]:
        attempts = 0

        while attempts < self.max_retries:
            try:
                logger.info(
                    f"Making API call (attempt {attempts + 1}/{self.max_retries})")
                response = openai.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": user_input}
                    ],
                    temperature=self.temperature,
                    max_tokens=max_tokens
                )
                content = response.choices[0].message.content
                logger.info(
                    f"API call successful, received {len(content)} characters")
                return content
            except Exception as e:
                attempts += 1
                logger.error(f"API call error: {e}")
                if attempts < self.max_retries:
                    wait_time = self.retry_delay * (2 ** (attempts - 1))
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error("Max retries reached, giving up")
                    return None

    def _safe_parse_json(self, json_str: str) -> Optional[Dict[str, Any]]:
        if not json_str:
            logger.error("Empty response received")
            return None

        try:
            if "```json" in json_str or "```" in json_str:
                start = json_str.find("```json")
                if start != -1:
                    start += 7
                else:
                    start = json_str.find("```")
                    if start != -1:
                        start += 3

                if start != -1:
                    end = json_str.find("```", start)
                    if end != -1:
                        json_str = json_str[start:end].strip()

            parsed_result = json.loads(json_str)

            # Ensure we actually got back a dict
            if not isinstance(parsed_result, dict):
                logger.error(
                    f"JSON parsed but result is not a dictionary: {type(parsed_result)}")
                logger.error(
                    f"First 500 chars of result: {str(parsed_result)[:500]}")
                return {}

            return parsed_result
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.error(f"Raw response (first 500 chars): {json_str[:500]}")
            return None

    def analyze_requirements(self, user_prompt: str) -> Optional[Dict[str, Any]]:
        response = self.call_agent(
            REQUIREMENTS_ANALYZER_PROMPT, user_prompt, max_tokens=MAX_TOKENS_DEFAULT)
        return self._safe_parse_json(response)

    def design_architecture(self, requirements_spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        req_json = json.dumps(requirements_spec, indent=2)
        response = self.call_agent(
            ARCHITECTURE_DESIGNER_PROMPT, req_json, max_tokens=MAX_TOKENS_LARGE)

        architecture = self._safe_parse_json(response)

        if architecture:
            logger.info("Architecture design successful")
        else:
            logger.error("Architecture design failed")

        return architecture

    def design_database(self, requirements_spec: Dict[str, Any], architecture: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        context = {
            "requirements": requirements_spec,
            "architecture": architecture
        }

        response = self.call_agent(DATABASE_DESIGNER_PROMPT, json.dumps(
            context), max_tokens=MAX_TOKENS_DEFAULT)
        return self._safe_parse_json(response)

    def design_api(self, requirements_spec: Dict[str, Any], architecture: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        context = {
            "requirements": requirements_spec,
            "architecture": architecture
        }

        response = self.call_agent(API_DESIGNER_PROMPT, json.dumps(
            context), max_tokens=MAX_TOKENS_DEFAULT)
        return self._safe_parse_json(response)

    def generate_code(self, file_spec: Dict[str, Any], project_context: Dict[str, Any]) -> Optional[str]:
        context = {
            "file_specification": file_spec,
            "project_context": project_context
        }

        return self.call_agent(CODE_GENERATOR_PROMPT, json.dumps(context), max_tokens=MAX_TOKENS_LARGE)

    def test_generator(self, file_path: str, code_content: str, project_context: Dict[str, Any]) -> Optional[str]:
        context = {
            "file_path": file_path,
            "code_content": code_content,
            "project_context": project_context
        }

        return self.call_agent(TEST_GENERATOR_PROMPT, json.dumps(context), max_tokens=MAX_TOKENS_DEFAULT)

    def code_reviewer(self, file_path: str, code_content: str, file_spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        context = {
            "file_path": file_path,
            "code_content": code_content,
            "file_specification": file_spec
        }

        response = self.call_agent(CODE_REVIEWER_PROMPT, json.dumps(
            context), max_tokens=MAX_TOKENS_DEFAULT)
        return self._safe_parse_json(response)

    def extract_file_signature(self, file_path: str, content: str) -> Dict[str, Any]:
        context = {
            "file_path": file_path,
            "code_content": content
        }

        response = self.call_agent(FILE_SIGNATURE_EXTRACTOR_PROMPT, json.dumps(
            context), max_tokens=MAX_TOKENS_DEFAULT)
        signature = self._safe_parse_json(response)

        if not signature:
            return {
                "file_path": file_path,
                "functions": [],
                "classes": [],
                "imports": []
            }

        return signature

    def cross_file_code_reviewer(self, all_files: Dict[str, str], project_context: Dict[str, Any]) -> Dict[str, str]:
        results = {}

        project_signatures = {}
        for path, content in all_files.items():
            project_signatures[path] = self.extract_file_signature(
                path, content)

        for file_path, content in all_files.items():
            context = {
                "file_to_review": file_path,
                "file_content": content,
                "project_signatures": project_signatures,
                "project_context": project_context
            }

            response = self.call_agent(CROSS_FILE_REVIEWER_PROMPT, json.dumps(
                context), max_tokens=MAX_TOKENS_LARGE)

            if response and response.strip() == "PARFAIT":
                results[file_path] = "PARFAIT"
            else:
                code_content = self._extract_code_content(response, file_path)
                results[file_path] = code_content if code_content else response

        return results

    def _extract_code_content(self, response: str, file_path: str) -> Optional[str]:
        if "```" in response:
            start_markers = ["```python", "```javascript",
                             "```java", "```typescript", "```"]
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

        return None

    def reformulate_prompt(self, user_prompt: str) -> Optional[str]:
        """Reformulate and enhance the user's application description."""
        response = self.call_agent(
            PROMPT_REFORMULATOR_PROMPT, user_prompt, max_tokens=MAX_TOKENS_DEFAULT)
        if response:
            return response.strip()
        return user_prompt  # Return original if reformulation fails

    def generate_app_name(self, user_prompt: str) -> Optional[str]:
        """Generate a name for the application based on the user's description."""
        from src.config import APP_NAME_GENERATOR_PROMPT

        response = self.call_agent(
            APP_NAME_GENERATOR_PROMPT, user_prompt, max_tokens=50)

        if response:
            # Nettoyer la réponse pour s'assurer qu'elle ne contient que le nom
            name = response.strip().split('\n')[0].strip()
            # Limiter à 30 caractères max et supprimer les guillemets éventuels
            name = name.replace('"', '').replace("'", "")[:30]
            return name

        return "MyApp"

    def generate_project_file(self, file_type: str, project_context: Dict[str, Any], file_structure: List[str]) -> str:
        context = {
            "file_type": file_type,
            "project_context": project_context,
            "file_structure": file_structure
        }

        response = self.call_agent(
            PROJECT_FILES_GENERATOR_PROMPT,
            json.dumps(context),
            max_tokens=MAX_TOKENS_DEFAULT
        )

        return response
