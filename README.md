# AI Application Generator

This project uses AI to generate complete, functional applications based on user descriptions. It leverages the OpenAI API to design, generate, and validate application code. The Streamlit interface provides an intuitive way to create applications without writing code.

## Features

- **Complete Application Generation**: Creates fully functional applications from text descriptions
- **Multiple Technology Support**: Generates apps in various programming languages and frameworks
- **Static Website Mode**: Option to create simple HTML/CSS/JS websites
- **Validation System**: Tests and validates generated applications to ensure they run correctly
- **Auto-fixing Capabilities**: Automatically fixes common issues in the generated code
- **File Download**: Download the complete project as a ZIP file

## Prerequisites

- Python 3.8 or higher
- Pipenv

## Installation

1. Clone the repository or copy the project files to your machine.
2. Open a terminal in the project's root folder.
3. Install the dependencies via Pipenv:

   ```
   pipenv install
   ```

4. If, after installation and activating the environment with `pipenv shell`, the dependencies don't seem to be properly installed, you can install them manually:

   ```
   pipenv install streamlit openai python-dotenv
   ```

5. Create a `.env` file at the project's root and add your OpenAI API key:

   ```
   OPENAI_API_KEY=<your_api_key>
   ```
## Usage

1. Activate the Pipenv environment:

   ```
   pipenv shell
   ```

2. Launch the Streamlit application:

   ```
   streamlit run app.py
   ```

3. In the web interface that opens:
   - Describe the application you want to build in the text area
   - Set the output directory where you want the application to be generated
   - Configure advanced options if needed:
     - Static website generation (HTML/CSS/JS only)
     - Test generation
     - Docker configuration
     - CI/CD configuration
     - Use sample JSON data instead of a database

4. Click **"Generate Application"** to start the process. The application will:
   - Analyze your requirements
   - Design the architecture
   - Generate all necessary code files
   - Validate the application structure
   - Attempt to fix any issues
   
5. When generation is complete, you can download the entire application as a ZIP file.

## Generation Process

The system follows these steps to create your application:
1. Requirements Analysis: Parses your description into structured requirements
2. Architecture Design: Creates a technical architecture based on the requirements
3. Database Schema Design: Designs database models if needed
4. API Design: Creates API endpoints when required
5. Code Generation: Writes all necessary code files
6. Validation: Tests the generated application for errors
7. Auto-fixing: Automatically corrects common issues

## API Configuration

Ensure you have your OpenAI API key set in the `.env` file.

## License

This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 International License - see the [LICENSE](LICENSE.md) file for details.

## Notes

- Ensure that the provided output directory is valid and accessible.
- The application generates complete, functional code but may require minor adjustments for complex use cases.
- The quality of the generated application depends on the clarity and detail in your description.
- More complex applications may require additional dependencies to be installed manually.
- Static website generation produces pure HTML/CSS/JS files that can be hosted on any web server.
