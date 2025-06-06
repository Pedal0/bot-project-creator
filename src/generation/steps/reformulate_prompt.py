# Copyright (C) 2025 Perey Alex
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>

"""
Fonction d'étape : reformulation du prompt utilisateur pour la génération d'application.
"""
import re
import json
from pathlib import Path
from src.api.openrouter_api import call_openrouter_api
from src.utils.model_utils import is_free_model
from src.config.constants import RATE_LIMIT_DELAY_SECONDS
import time

def reformulate_prompt(api_key, selected_model, user_prompt, url_context, additional_context, progress_callback=None, current_app=None, process_state=None):
    """
    Reformule le prompt utilisateur pour guider la génération de code.
    Retourne le prompt reformulé ou None en cas d'échec.
    Met à jour process_state et current_app si fournis.
    """
    def update_progress(step, message, progress=None):
        if progress_callback:
            progress_callback(step, message, progress)

    # Vérifier la limite de taux pour les modèles gratuits
    if is_free_model(selected_model):
        current_time = time.time()
        last_api_call_time = process_state.get('last_api_call_time', 0) if process_state else 0
        time_since_last_call = current_time - last_api_call_time
        if time_since_last_call < RATE_LIMIT_DELAY_SECONDS:
            wait_time = RATE_LIMIT_DELAY_SECONDS - time_since_last_call
            update_progress(1, f"⏳ Modèle gratuit détecté. Attente de {wait_time:.1f} secondes (limite de taux)...", 20)
            time.sleep(wait_time)

    # Load and prepare best system prompts as a system message
    config_file = Path(__file__).parents[2] / 'config' / 'best_system_prompts.json'
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            best_prompts_list = json.load(f)
        system_prompt = 'You are an AI assistant for code generation. Follow these best practices strictly:\n' + ''.join(f'- {item}\n' for item in best_prompts_list)
    except Exception:
        system_prompt = 'You are an AI assistant for code generation. Follow best practices for clear, maintainable, and secure code.'

    prompt_reformulation = f"""
    Analyze the user's request below. Your task is to:
    1. Reformulate the request in a detailed and precise way to guide code generation.
    2. Structure your reformulation into the following sections:
       - Main features required
       - Technologies/frameworks to use (or avoid)
       - Specific constraints or preferences
       - Example use cases or user flows
    3. If the request is vague, make reasonable assumptions to fill in missing information.
    4. If the user provided URLs, carefully read their content and follow any instructions or use examples as inspiration.
    5. Your output MUST be EXACTLY in the following format:
    ### REFORMULATED PROMPT ###
    Features:
    - ...
    Technologies:
    - ...
    Constraints:
    - ...
    Example use cases:
    - ...

    User request:
    "{user_prompt}"
    {url_context if url_context else ""}
    {additional_context if additional_context else ""}
    """
    # Prepare messages with system prompt and user content
    messages_reformulation = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt_reformulation}
    ]
    response_reformulation = call_openrouter_api(api_key, selected_model, messages_reformulation, temperature=0.6, max_retries=2)
    if process_state is not None:
        process_state['last_api_call_time'] = time.time()
    update_progress(1, "Analyse de la réponse de reformulation...", 35)
    reformulated_prompt = None
    if response_reformulation and response_reformulation.get("choices"):
        response_text = response_reformulation["choices"][0]["message"]["content"]
        prompt_match = re.search(r"###\s*REFORMULATED PROMPT\s*###\s*(.*)", response_text, re.DOTALL | re.IGNORECASE)
        if prompt_match:
            reformulated_prompt = prompt_match.group(1).strip()
            if process_state is not None:
                process_state['reformulated_prompt'] = reformulated_prompt
            if current_app:
                current_app.config['reformulated_prompt'] = reformulated_prompt
            update_progress(1, "✅ Prompt reformulé avec succès.", 40)
        else:
            update_progress(1, "⚠️ Format de réponse inattendu pour la reformulation.", 40)
            reformulated_prompt = response_text.strip()
            if process_state is not None:
                process_state['reformulated_prompt'] = reformulated_prompt
            if current_app:
                current_app.config['reformulated_prompt'] = reformulated_prompt
    else:
        update_progress(1, "❌ Échec de la reformulation du prompt.", 40)
        return None
    return reformulated_prompt