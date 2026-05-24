import uvicorn
from dotenv import load_dotenv  # pip install python-dotenv

# Load API keys from backend/.env (if it exists) before starting the app.
# Environment variables already set in the shell take precedence.
load_dotenv()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
