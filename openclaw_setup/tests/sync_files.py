import os
import subprocess
import base64

def sync_dir(src_dir, dest_base):
    for root, dirs, files in os.walk(src_dir):
        for f in files:
            full_p = os.path.join(root, f)
            rel_p = os.path.relpath(full_p, src_dir).replace("\\", "/")
            dest_p = f"{dest_base}/{rel_p}"
            with open(full_p, "rb") as fp:
                b64_str = base64.b64encode(fp.read()).decode("ascii")
            
            parent_dir = "/".join(dest_p.split("/")[:-1])
            subprocess.run(["wsl", "-d", "OpenClawGateway", "bash", "-c", f"mkdir -p '{parent_dir}'"], check=True)
            p = subprocess.Popen(["wsl", "-d", "OpenClawGateway", "bash", "-c", f"base64 -d > '{dest_p}'"], stdin=subprocess.PIPE)
            p.communicate(input=b64_str.encode("ascii"))
            if p.returncode != 0:
                print(f"Error syncing {rel_p}")
            else:
                print(f"Synced: {rel_p}")

def sync_files_list(files_map):
    for src, dest in files_map.items():
        with open(src, "rb") as fp:
            b64_str = base64.b64encode(fp.read()).decode("ascii")
        parent_dir = "/".join(dest.split("/")[:-1])
        subprocess.run(["wsl", "-d", "OpenClawGateway", "bash", "-c", f"mkdir -p '{parent_dir}'"], check=True)
        p = subprocess.Popen(["wsl", "-d", "OpenClawGateway", "bash", "-c", f"base64 -d > '{dest}'"], stdin=subprocess.PIPE)
        p.communicate(input=b64_str.encode("ascii"))
        print(f"Synced file: {src} -> {dest}")

sync_dir(r"c:\Users\shw12\Downloads\IRL_Lab_AI_ agent\IRL_Lab_AI_ agent\lab_assistant", "/home/openclaw/irl_lab/lab_assistant")
sync_dir(r"c:\Users\shw12\Downloads\IRL_Lab_AI_ agent\openclaw_setup", "/home/openclaw/irl_lab/openclaw_setup")

ws_map = {
    r"c:\Users\shw12\Downloads\IRL_Lab_AI_ agent\openclaw_setup\AGENTS.md": "/home/openclaw/.openclaw/workspace/AGENTS.md",
    r"c:\Users\shw12\Downloads\IRL_Lab_AI_ agent\openclaw_setup\IDENTITY.md": "/home/openclaw/.openclaw/workspace/IDENTITY.md",
    r"c:\Users\shw12\Downloads\IRL_Lab_AI_ agent\openclaw_setup\SOUL.md": "/home/openclaw/.openclaw/workspace/SOUL.md",
    r"c:\Users\shw12\Downloads\IRL_Lab_AI_ agent\openclaw_setup\USER.md": "/home/openclaw/.openclaw/workspace/USER.md"
}
sync_files_list(ws_map)

print("All synced successfully!")


