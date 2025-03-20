import streamlit as st
import sys
import os
import logging
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.ui.page import setup_page, show_how_it_works
from src.ui.common import initialize_session_state, create_tabs, set_active_tab
from src.ui.initial_setup import show_initial_setup_tab
from src.ui.review_tab import show_review_tab
from src.ui.generation_tab import show_generation_tab  # Ajouter l'import pour l'onglet de génération

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def main():
    """Main Streamlit application function"""
    load_dotenv()
    
    # Set up the main page
    setup_page()
    
    # Initialize session state for multi-step process
    initialize_session_state()
    
    # Get API keys from environment
    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
    
    # Show API key requirements in the UI
    if not openai_api_key and not openrouter_api_key:
        st.error("No API keys found. Please add at least one of these to your .env file:")
        st.code("OPENAI_API_KEY=your_openai_key_here\nOPENROUTER_API_KEY=your_openrouter_key_here")
    
    # Créer les onglets
    tab1, tab2, tab3 = st.tabs(["Definition", "Review", "Generation"])  # Renommer le dernier onglet en "Generation"

    with tab1:
        show_initial_setup_tab(openai_api_key)
        
    with tab2:
        show_review_tab(openai_api_key)
        
    with tab3:
        show_generation_tab(openai_api_key)  # Utilisez la fonction pour l'onglet de génération

    # Set the active tab based on the current step
    set_active_tab()
    
    # Show the "How it works" section
    show_how_it_works()

if __name__ == "__main__":
    main()