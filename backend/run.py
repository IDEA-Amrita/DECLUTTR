import uvicorn
from dotenv import load_dotenv  # pip install python-dotenv

# Load API keys from backend/.env first, then override with backend/.env.local.
# Environment variables already set in the shell take precedence.
load_dotenv(".env")
load_dotenv(".env.local", override=True)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
