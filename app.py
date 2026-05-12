from flask import Flask, render_template
from flask_cors import CORS
from routes.routes import api_bp
import logging
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load config
with open("ollama_config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Create Flask app
app = Flask(__name__, template_folder='templates')
CORS(app)

# Register blueprints
app.register_blueprint(api_bp, url_prefix="/api")

# Serve index.html
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/health-ui")
def health_ui():
    """Simple health check page"""
    return render_template("health.html")

if __name__ == "__main__":
    for agent_name, agent_config in config['agents'].items():
        print(f"  - {agent_config['name']}")
    
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True, use_reloader=False)