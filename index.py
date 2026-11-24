from app.main import create_app
from app.intelligence.gemini import configured_provider

app = create_app(intelligence_provider=configured_provider())
