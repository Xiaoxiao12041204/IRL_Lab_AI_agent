import urllib.request, json

url = "http://140.138.175.53:8000/v1/models"
req = urllib.request.Request(url, headers={"Authorization": "Bearer sk-lab-admin-dgx1-master"})
try:
    r = urllib.request.urlopen(req, timeout=10)
    data = json.loads(r.read().decode())
    print("連線成功！可用模型：")
    for m in data.get("data", []):
        print(f"  - {m.get('id')}")
except Exception as e:
    print(f"連線失敗：{e}")
