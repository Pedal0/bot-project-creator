import json
import logging
from typing import Dict, Any, Optional

from src.config import API_DESIGNER_PROMPT, MAX_TOKENS_DEFAULT

logger = logging.getLogger(__name__)

def design_api(api_client, requirements_spec: Dict[str, Any], architecture: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Design API interfaces based on requirements and architecture
    
    Args:
        api_client: API client instance
        requirements_spec: Requirements specification dictionary
        architecture: Architecture specification dictionary
        
    Returns:
        API specification dictionary or None if design failed
    """
    context = {
        "requirements": requirements_spec,
        "architecture": architecture
    }
    
    response = api_client.call_agent(
        API_DESIGNER_PROMPT, 
        json.dumps(context), 
        max_tokens=MAX_TOKENS_DEFAULT
    )
    
    if not response:
        logger.error("No response received for API design")
        return None
        
    try:
        if "```json" in response or "```" in response:
            # Extract JSON from code blocks if present
            start = response.find("```json")
            if start != -1:
                start += 7  
            else:
                start = response.find("```")
                if start != -1:
                    start += 3  
            
            if start != -1:
                end = response.find("```", start)
                if end != -1:
                    response = response[start:end].strip()
                
        api_spec = json.loads(response)
        
        if not isinstance(api_spec, dict):
            logger.error(f"API design returned invalid format: {type(api_spec)}")
            return None
            
        logger.info("API design successful")
        return api_spec
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse API specification JSON: {e}")
        logger.error(f"Raw response (first 500 chars): {response[:500]}")
        return None
