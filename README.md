# AI Chat Service

## Project Overview
The AI Chat Service is a robust platform designed to facilitate conversational interactions using advanced AI models. This service integrates seamlessly with Azure OpenAI to provide dynamic and responsive chat capabilities. It is built using Django, leveraging Django REST Framework for API management.

## Features
- **Conversational AI**: Utilizes Azure OpenAI to handle user interactions, providing intelligent responses based on user input.
- **RESTful APIs**: Built with Django REST Framework to provide scalable and maintainable endpoints.
- **Asynchronous Support**: Configured with ASGI for handling asynchronous requests, suitable for real-time applications.

## Installation

### Prerequisites
- Python 3.x
- Django (compatible version as per project requirement)
- Azure OpenAI subscription and access credentials

### Environment Setup
1. Clone the repository:
   ```bash
   git clone <repository-url>
Navigate to the project directory:
cd AI-Chat-Service

Create a virtual environment:
python -m venv venv

Activate the virtual environment:
On Windows:
venv\Scripts\activate

On macOS/Linux:
source venv/bin/activate

Install the dependencies:
pip install -r requirements.txt

Configuration
Create a .env file in the root directory and add your Azure OpenAI and database credentials as shown in settings.py:
AZURE_OPENAI_API_KEY=<your-api-key>
AZURE_OPENAI_ENDPOINT=<your-endpoint>

Usage
Run the Django development server:
python manage.py runserver

Access the API endpoints at http://localhost:8000/api/.

API Endpoints
Chat Endpoints: Manage conversations and chat history.
User Management: Create and authenticate users.
Performance Data: Track and analyze user interactions.