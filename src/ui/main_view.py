import streamlit as st
from src.ui.reformulation import show_reformulation_section
from src.ui.generation import show_generation_section, process_generation
from src.ui.components import show_sidebar, show_header
from src.utils.config import get_api_key
import os


def get_language_from_extension(file_path):
    """Determine the appropriate language for syntax highlighting based on file extension"""
    ext = os.path.splitext(file_path)[1].lower()
    language_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.html': 'html',
        '.css': 'css',
        '.json': 'json',
        '.md': 'markdown',
        '.sql': 'sql',
        '.sh': 'bash',
        '.bat': 'bash',
        '.yml': 'yaml',
        '.yaml': 'yaml',
        '.tsx': 'typescript',
        '.ts': 'typescript',
        '.jsx': 'javascript'
    }
    return language_map.get(ext, 'text')


def is_binary_file(file_path):
    """Check if a file is likely to be binary rather than text"""
    binary_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.ico', '.pdf', '.zip', '.tar',
                         '.gz', '.exe', '.dll', '.so', '.pyc', '.ttf', '.woff']
    ext = os.path.splitext(file_path)[1].lower()
    return ext in binary_extensions


def display_main_ui():
    """Affiche l'interface utilisateur principale de l'application"""
    # Afficher l'en-tête et la barre latérale
    show_header()
    api_key = show_sidebar()

    # Initialiser les variables d'état de session
    init_session_state()

    # Afficher la section de saisie de description
    user_prompt = st.text_area(
        "Describe the application you want to build",
        height=150,
        placeholder="Example: Create a web application that allows users to manage their personal finances. It should track income, expenses, investments, and provide visualizations of spending patterns."
    )

    # Bouton de reformulation
    if st.button("Reformulate Description"):
        handle_reformulation_request(api_key, user_prompt)

    # Afficher la section de reformulation si nécessaire
    if st.session_state.show_reformulation:
        show_reformulation_section()

    # Afficher la section de génération
    if user_prompt:
        show_generation_section(st.session_state.show_reformulation)

    # Afficher la section d'information
    st.divider()
    st.markdown("### How it works")
    st.markdown("""
    1. **Requirements Reformulation**: The system can reformulate your description to make it more comprehensive.
    2. **Requirements Analysis**: The system analyzes your description to understand what you want to build.
    3. **Architecture Design**: It designs the overall structure of your application.
    4. **Database Schema**: It creates appropriate database schemas if needed.
    5. **API Design**: It designs API interfaces for the application components.
    6. **Code Generation**: It generates the actual code for the application.
    7. **Code Review**: It reviews the generated code and makes improvements if necessary.
    8. **Project Packaging**: It creates project files like requirements.txt and README.md.
    """)


def init_session_state():
    """Initialise les variables d'état de la session"""
    if 'reformulated_prompt' not in st.session_state:
        st.session_state.reformulated_prompt = ""
    if 'show_reformulation' not in st.session_state:
        st.session_state.show_reformulation = False
    if 'original_prompt' not in st.session_state:
        st.session_state.original_prompt = ""
    if 'app_name' not in st.session_state:
        st.session_state.app_name = ""
    if 'original_reformulation' not in st.session_state:
        st.session_state.original_reformulation = ""
    if 'output_directory' not in st.session_state:
        st.session_state.output_directory = get_default_output_path()


def handle_reformulation_request(api_key, user_prompt):
    """Gère la demande de reformulation"""
    from src.main_app import AppGenerator
    import os

    # Vérification des prérequis
    if not api_key:
        st.error("Please enter your OpenAI API key in the sidebar.")
        return

    if not user_prompt:
        st.error("Please describe the application you want to build.")
        return

    # Appel à l'API pour reformulation et génération de nom
    with st.spinner("Reformulating description and generating app name..."):
        app_generator = AppGenerator(api_key)

        # Demander un nom d'application
        app_name = app_generator.api_client.generate_app_name(user_prompt)

        # Obtenir la reformulation avec placeholder
        reformulated = app_generator.api_client.reformulate_prompt(user_prompt)

        if reformulated:
            # Mise à jour de l'état avec la reformulation et le nom
            st.session_state.app_name = app_name

            # Conserver la reformulation avec le placeholder intact
            st.session_state.reformulated_prompt = reformulated
            st.session_state.original_prompt = user_prompt
            st.session_state.show_reformulation = True

            # Stocker la version originale avec placeholders
            st.session_state.original_reformulation = reformulated

            # Mise à jour du répertoire de sortie (utiliser le nom généré pour le répertoire)
            base_dir = os.path.dirname(st.session_state.output_directory)
            st.session_state.output_directory = os.path.join(
                base_dir, app_name.replace(" ", "_").lower())
        else:
            st.error("Failed to reformulate description. Please try again.")


def get_default_output_path():
    """Renvoie le chemin de sortie par défaut"""
    import os
    return os.path.join(os.path.expanduser('~'), "generated_app")
