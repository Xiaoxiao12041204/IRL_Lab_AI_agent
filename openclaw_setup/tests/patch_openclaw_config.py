import json, sys

config_path = "/home/openclaw/.openclaw/openclaw.json"

with open(config_path, "r") as f:
    config = json.load(f)

# 加入自訂遠端算力模型設定
config["models"] = {
    "mode": "merge",
    "providers": {
        "irl-lab-dgx1": {
            "baseUrl": "http://140.138.175.53:8000/v1",
            "apiKey": "sk-lab-admin-dgx1-master",
            "api": "openai-completions",
            "models": [
                {
                    "id": "Qwen3.5-27B",
                    "name": "IRL Lab Qwen3.5-27B (DGX1)",
                    "contextWindow": 32768,
                    "input": ["text"]
                }
            ]
        }
    }
}

# 設定 main agent 預設使用此模型
config["agents"]["entries"]["main"] = {
    "model": {
        "primary": "irl-lab-dgx1/Qwen3.5-27B"
    }
}

# 設定全域預設模型
if "defaults" not in config["agents"]:
    config["agents"]["defaults"] = {}
config["agents"]["defaults"]["model"] = {
    "primary": "irl-lab-dgx1/Qwen3.5-27B"
}

with open(config_path, "w") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print("Config updated OK")
print(json.dumps(config.get("models", {}), indent=2, ensure_ascii=False))
