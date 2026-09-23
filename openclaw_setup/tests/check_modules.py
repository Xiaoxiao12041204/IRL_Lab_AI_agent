import importlib.util, sys
print("Python:", sys.version)
modules = ["requests", "dotenv", "json", "urllib", "pathlib", "synology_api", "PyPDF2", "docx", "pptx"]
for m in modules:
    spec = importlib.util.find_spec(m)
    print(f"  {'OK' if spec else 'MISSING'}: {m}")
