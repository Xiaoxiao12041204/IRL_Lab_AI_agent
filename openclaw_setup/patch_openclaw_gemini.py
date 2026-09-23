import json
import sys

def configure_gemini(api_key: str):
    config_path = "/home/openclaw/.openclaw/openclaw.json"
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    if "models" not in config:
        config["models"] = {"mode": "merge", "providers": {}}
    if "providers" not in config["models"]:
        config["models"]["providers"] = {}
        
    # 加入 Google Gemini Flash Lite 系列
    config["models"]["providers"]["google-gemini"] = {
        "baseUrl": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "apiKey": api_key,
        "api": "openai-completions",
        "models": [
          {
            "id": "gemini-flash-lite-latest",
            "name": "Google Gemini Flash Lite Latest",
            "contextWindow": 1048576,
            "input": ["text"]
          },
          {
            "id": "gemini-3.5-flash-lite",
            "name": "Google Gemini 3.5 Flash Lite",
            "contextWindow": 1048576,
            "input": ["text"]
          },
          {
            "id": "gemini-3.1-flash-lite",
            "name": "Google Gemini 3.1 Flash Lite",
            "contextWindow": 1048576,
            "input": ["text"]
          }
        ]
    }
    
    # 全面設定主要模型與備用模型為 Flash Lite
    primary_model = "google-gemini/gemini-flash-lite-latest"
    fallbacks = ["google-gemini/gemini-3.5-flash-lite", "google-gemini/gemini-3.1-flash-lite", "irl-lab-dgx1/Qwen3.5-27B"]
    
    if "agents" not in config:
        config["agents"] = {"defaults": {}, "entries": {}}
    if "entries" not in config["agents"]:
        config["agents"]["entries"] = {}
    if "main" not in config["agents"]["entries"]:
        config["agents"]["entries"]["main"] = {}
        
    config["agents"]["entries"]["main"]["model"] = {
        "primary": primary_model,
        "fallbacks": fallbacks
    }
    
    # 全域預設也設定為 Flash Lite
    if "defaults" not in config["agents"]:
        config["agents"]["defaults"] = {}
    config["agents"]["defaults"]["model"] = {
        "primary": primary_model,
        "fallbacks": fallbacks
    }
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        
    print("All models successfully switched to Gemini Flash Lite!")
        
    print("Gemini API Key configured successfully as primary fallback!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python patch_openclaw_gemini.py <YOUR_GEMINI_API_KEY>")
        sys.exit(1)
    configure_gemini(sys.argv[1].strip())
