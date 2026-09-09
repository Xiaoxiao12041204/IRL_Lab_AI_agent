import json, sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

with open('lab_assistant/data/thesis_index.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

seen = {}
dups = []
for item in data:
    if item['author'] in seen:
        dups.append(item['author'])
    seen[item['author']] = True

print(f'總筆數: {len(data)} 筆, 重複: {dups if dups else "無"}')
print()
print(f"{'作者':6s} | {'年份':4s} | 論文題目")
print("-" * 80)
for item in sorted(data, key=lambda x: x.get('year_roc', 0)):
    title = item['title'][:40]
    print(f'{item["author"]:6s} | 民{item.get("year_roc", "?"):3d} | {title}')
