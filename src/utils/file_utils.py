"""
Utility functions for file operations, structure parsing, and code writing.
"""
import re
import streamlit as st
from pathlib import Path

def parse_structure_and_prompt(response_text):
    """
    Extract the reformulated prompt and cleaned structure from the first API call response.
    
    Args:
        response_text (str): Raw response text from the API
        
    Returns:
        tuple: (reformulated_prompt, structure_lines)
    """
    reformulated_prompt = None
    structure_lines = []
    cleaned_structure_lines = []

    try:
        # Search for main markers
        prompt_match = re.search(r"###\s*REFORMULATED PROMPT\s*###\s*(.*?)\s*###\s*STRUCTURE\s*###", response_text, re.DOTALL | re.IGNORECASE)
        structure_match = re.search(r"###\s*STRUCTURE\s*###\s*(.*)", response_text, re.DOTALL | re.IGNORECASE)

        if prompt_match:
            reformulated_prompt = prompt_match.group(1).strip()
        else:
            # Try to find prompt even without the structure marker after it
            prompt_match_alt = re.search(r"###\s*REFORMULATED PROMPT\s*###\s*(.*)", response_text, re.DOTALL | re.IGNORECASE)
            if prompt_match_alt:
                 reformulated_prompt = prompt_match_alt.group(1).strip()

        if structure_match:
            structure_block = structure_match.group(1).strip()
            # Clean structure block: remove ``` and # comments
            structure_block_cleaned = structure_block.strip().strip('`') # Remove ``` at beginning/end
            potential_lines = structure_block_cleaned.split('\n')

            for line in potential_lines:
                line = line.strip()
                # Ignore empty lines or lone code markers
                if not line or line == '```':
                    continue
                # Remove inline comments (everything after #)
                # Keep part before #, then re-strip in case there are spaces before #
                if '#' in line:
                    line = line.split('#', 1)[0].strip()
                # Add only if line is not empty after cleaning
                if line:
                    cleaned_structure_lines.append(line)
            structure_lines = cleaned_structure_lines # Use cleaned list
        else:
            # If structure_match fails, we can't extract structure
             st.warning("'### STRUCTURE ###' marker not found.")

        # --- Handle cases where markers are not found or empty ---
        if not reformulated_prompt and not structure_lines:
             st.error("Unable to extract both reformulated prompt AND structure. Check AI response format.")
             st.code(response_text)
             return None, []
        elif not reformulated_prompt:
             st.warning("Reformulated prompt not found, but structure found. Attempting to continue.")
             # Could try using original prompt as fallback, but risky
             # For now, return None for prompt, which will cause error later (which is ok)
             return None, structure_lines
        elif not structure_lines:
             st.warning("Structure not found, but reformulated prompt found. Unable to create files.")
             return reformulated_prompt, []

    except Exception as e:
        st.error(f"Error analyzing AI response (structure/prompt): {e}")
        st.code(response_text) # Display raw response
        return None, []

    # Display cleaned structure for debugging
    st.write("Detected and cleaned structure:")
    st.code("\n".join(structure_lines), language='text')

    return reformulated_prompt, structure_lines


def create_project_structure(base_path, structure_lines):
    """
    Create folders and empty files based on the cleaned structure.
    
    Args:
        base_path (str): Base directory path
        structure_lines (list): List of file/directory paths
        
    Returns:
        list: List of created paths or None on error
    """
    created_paths = []
    base_path = Path(base_path).resolve() # Get absolute and normalized path
    st.info(f"Attempting to create structure in: {base_path}")

    if not base_path.is_dir():
        st.error(f"Base path '{base_path}' is not a valid folder or does not exist.")
        return None

    if not structure_lines:
        st.warning("No structure lines provided to create.")
        return [] # Return empty list, not a fatal error

    try:
        for line in structure_lines:
            line = line.strip() # Re-clean just in case
            if not line: continue # Ignore empty lines

            # Security: Check for '..' in path components
            relative_path = Path(line)
            if ".." in relative_path.parts:
                 st.warning(f"⚠️ Path containing '..' ignored (security): '{line}'")
                 continue

            item_path = base_path / relative_path

            try:
                # Determine if it's a folder or file
                # Path() removes the trailing '/', so we rely on the original line
                is_dir = line.endswith('/')

                if is_dir:
                    # Create folder
                    item_path.mkdir(parents=True, exist_ok=True)
                    st.write(f" ✅ Folder created/verified: {item_path}")
                    created_paths.append(item_path)
                else:
                    # It's a file: Create parent folders if needed
                    item_path.parent.mkdir(parents=True, exist_ok=True)
                    # Create empty file (or empty it if it exists)
                    item_path.touch(exist_ok=True)
                    st.write(f" ✅ File created/verified: {item_path}")
                    created_paths.append(item_path)

            except OSError as e:
                 st.error(f"❌ OS error creating '{item_path}' from line '{line}': {e}")
                 # Continue with others if possible
            except Exception as e:
                 st.error(f"❌ Unexpected error for '{item_path}' from line '{line}': {e}")

        return created_paths
    except Exception as e:
        st.error(f"Major error processing project structure: {e}")
        return None


def clean_code_block(code_block):
    """
    Remove markdown code block markers from the beginning and end of code blocks.
    
    Args:
        code_block (str): The code block to clean
        
    Returns:
        str: Cleaned code block without markdown markers
    """
    # Pattern for beginning: ```language or ```
    start_pattern = r'^```(?:\w+)?\n'
    # Pattern for end: ```
    end_pattern = r'\n```$'
    # Remove both patterns
    code_block = re.sub(start_pattern, '', code_block)
    code_block = re.sub(end_pattern, '', code_block)
    return code_block


def parse_and_write_code(base_path, code_response_text):
    """
    Parse code response and write each block to the corresponding file.
    
    Args:
        base_path (str): Base directory path
        code_response_text (str): Raw code generation response
        
    Returns:
        tuple: (files_written, errors, generation_incomplete)
    """
    base_path = Path(base_path).resolve()
    files_written = []
    errors = []
    generation_incomplete = False

    # First check if the response ends with the incompleteness marker
    if code_response_text.strip().endswith("GENERATION_INCOMPLETE"):
        generation_incomplete = True
        st.warning("⚠️ AI indicated that code generation is incomplete (likely token limit reached).")
        # Remove marker to avoid interfering with parsing the last file
        code_response_text = code_response_text.strip()[:-len("GENERATION_INCOMPLETE")].strip()

    # Regex to find code blocks marked by --- FILE: path/to/file ---
    # Use re.split to separate by marker, capturing the path
    # The `?` after `.*` makes it non-greedy, important if markers are close
    parts = re.split(r'(---\s*FILE:\s*(.*?)\s*---)', code_response_text, flags=re.IGNORECASE)

    if len(parts) <= 1:
        st.warning("No '--- FILE: ... ---' markers found in code generation response.")
        st.info("Attempting to write entire response to 'generated_code.txt'")
        output_file = base_path / "generated_code.txt"
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(code_response_text)
            files_written.append(str(output_file))
            st.write(f" ✅ Raw code written to: {output_file}")
        except Exception as e:
             errors.append(f"❌ Unable to write to '{output_file}': {e}")
        # Can't tell if it's incomplete in this case without marker
        return files_written, errors, generation_incomplete

    # Iterate over captured blocks (ignore first part before first marker)
    # Parts structure: ['', marker1, path1, code1, marker2, path2, code2, ...]
    for i in range(1, len(parts), 3):
        try:
            # marker = parts[i] # Full marker (e.g., '--- FILE: src/main.py ---')
            file_path_str = parts[i+1].strip() # Extracted file path
            code_block = parts[i+2].strip()    # Code block (may be empty if abrupt end)

            if not file_path_str:
                st.warning(f"Marker found but empty or invalid file path, block ignored.")
                continue

            # Clean and validate path
            file_path_str = file_path_str.replace('\r', '').strip()
            if not file_path_str: continue # Ignore if empty after cleaning

            relative_path = Path(file_path_str)
            if ".." in relative_path.parts: # Security: Check for '..'
                 st.warning(f"⚠️ File path '{file_path_str}' contains '..', ignored for security.")
                 continue

            target_file_path = base_path / relative_path

            # Ensure parent folder exists (created in step 2, but for safety)
            target_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Clean code block before writing
            code_block = clean_code_block(code_block)

            # Write code to file
            with open(target_file_path, 'w', encoding='utf-8') as f:
                f.write(code_block)

            files_written.append(str(target_file_path))
            # st.write(f"   Code written to: {target_file_path}") # Can be verbose

        except IndexError:
             # If response ends just after a marker without code
             st.warning(f"Unexpected end of response after marker for '{parts[i+1].strip() if i+1 < len(parts) else 'last file'}'. File potentially empty or missing.")
             continue
        except OSError as e:
            error_msg = f"❌ Error writing to file '{file_path_str}': {e}"
            st.error(error_msg)
            errors.append(error_msg)
        except Exception as e:
            error_msg = f"❌ Unexpected error processing file '{file_path_str}': {e}"
            st.error(error_msg)
            errors.append(error_msg)

    return files_written, errors, generation_incomplete


def identify_empty_files(base_path, structure_lines):
    """
    Identify empty files in the project structure.
    
    Args:
        base_path (str): Base directory path
        structure_lines (list): List of file/directory paths
        
    Returns:
        list: List of empty file paths (relative to base_path)
    """
    empty_files = []
    base_path = Path(base_path).resolve()
    
    for line in structure_lines:
        line = line.strip()
        if not line or line.endswith('/'): 
            continue  # Skip empty lines and directories
            
        # Security check for '..'
        relative_path = Path(line)
        if ".." in relative_path.parts:
            continue
            
        file_path = base_path / relative_path
        
        # Check if file exists and is empty
        if file_path.exists() and file_path.is_file() and file_path.stat().st_size == 0:
            empty_files.append(str(relative_path))
            
    return empty_files


def generate_missing_code(api_key, model, empty_files, reformulated_prompt, structure_lines, generated_code, target_directory):
    """
    Generate code for empty files by providing the LLM with context about the project.
    
    Args:
        api_key (str): OpenRouter API key
        model (str): Model name to use
        empty_files (list): List of empty file paths
        reformulated_prompt (str): The reformulated project description
        structure_lines (list): The project structure
        generated_code (str): Previously generated code
        target_directory (str): Target directory path
        
    Returns:
        tuple: (files_written, errors)
    """
    from src.api.openrouter_api import call_openrouter_api
    
    files_written = []
    errors = []
    
    if not empty_files:
        return files_written, errors
    
    st.info(f"Attempting to generate code for {len(empty_files)} empty files...")
    
    # Prepare a condensed version of the previously generated code
    # Only include the FILE markers and a brief indicator of content
    condensed_code = ""
    parts = re.split(r'(---\s*FILE:\s*(.*?)\s*---)', generated_code, flags=re.IGNORECASE)
    for i in range(1, len(parts), 3):
        if i+1 < len(parts):
            file_path = parts[i+1].strip()
            content_preview = parts[i+2].strip()[:100] + "..." if parts[i+2].strip() else "[Empty]"
            condensed_code += f"--- FILE: {file_path} --- (Content length: {len(parts[i+2].strip())} chars)\n"
    
    # Build the prompt for generating missing code
    prompt = f"""
    You need to complete code for files that were left empty in a previous generation.
    
    **Project Description:**
    {reformulated_prompt}
    
    **Complete Project Structure:**
    ```
    {chr(10).join(structure_lines)}
    ```
    
    **Previously Generated Files (summary):**
    {condensed_code}
    
    **Files to Complete:**
    {chr(10).join([f"- {f}" for f in empty_files])}
    
    **Instructions:**
    1. Generate ONLY the code for the files listed under "Files to Complete".
    2. Use the EXACT format `--- FILE: path/to/filename ---` on a line by itself before each file's code.
    3. Ensure your code is consistent with the rest of the project structure and functionality.
    4. Use appropriate imports, error handling, and comments.
    5. DO NOT generate code for files not listed in "Files to Complete".
    
    Generate code for the missing files now:
    """
    
    messages = [{"role": "user", "content": prompt}]
    response = call_openrouter_api(api_key, model, messages, temperature=0.4, max_retries=2)
    
    if response and response.get("choices"):
        response_text = response["choices"][0]["message"]["content"]
        
        # Parse the response and write files
        base_path = Path(target_directory).resolve()
        
        parts = re.split(r'(---\s*FILE:\s*(.*?)\s*---)', response_text, flags=re.IGNORECASE)
        
        for i in range(1, len(parts), 3):
            try:
                if i+1 >= len(parts):
                    continue
                    
                file_path_str = parts[i+1].strip()
                code_block = parts[i+2].strip()
                
                if not file_path_str or not code_block:
                    continue
                
                # Clean paths
                file_path_str = file_path_str.replace('\r', '').strip()
                relative_path = Path(file_path_str)
                
                # Security check
                if ".." in relative_path.parts:
                    errors.append(f"⚠️ File path '{file_path_str}' contains '..', ignored for security.")
                    continue
                
                target_file_path = base_path / relative_path
                
                # Ensure parent folder exists
                target_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Clean code before writing
                code_block = clean_code_block(code_block)
                
                # Write code to file
                with open(target_file_path, 'w', encoding='utf-8') as f:
                    f.write(code_block)
                
                files_written.append(str(target_file_path))
                
            except Exception as e:
                error_msg = f"❌ Error processing file '{file_path_str if 'file_path_str' in locals() else 'unknown'}': {e}"
                errors.append(error_msg)
        
        return files_written, errors
    else:
        errors.append("Failed to generate code for empty files: No valid response from API")
        return files_written, errors
