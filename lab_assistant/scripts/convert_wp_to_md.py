import requests, urllib3
from bs4 import BeautifulSoup
import os, sys, re

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

urllib3.disable_warnings()
session = requests.Session()

# 登入 WordPress 文章密碼 yzu70640
session.post('https://yzuirl.synology.me/wordpress/wp-login.php?action=postpass', data={'post_password': 'yzu70640'}, verify=False)

# 嚴格對應「黑曼巴系統說明目錄」中的 10 大章節連結
chapters = [
    ('01_系統簡介', 'https://yzuirl.synology.me/wordpress/hello-world/'),
    ('02_運作過程', 'https://yzuirl.synology.me/wordpress/%E9%81%8B%E4%BD%9C%E9%81%8E%E7%A8%8B/'),
    ('03_安裝部署', 'https://yzuirl.synology.me/wordpress/%E5%AE%89%E8%A3%9D%E9%83%A8%E7%BD%B2/'),
    ('04_本機資料庫設定', 'https://yzuirl.synology.me/wordpress/%E6%9C%AC%E6%A9%9F%E8%B3%87%E6%96%99%E5%BA%AB%E8%A8%AD%E5%AE%9A/'),
    ('05_程式架構', 'https://yzuirl.synology.me/wordpress/%e7%a8%8b%e5%bc%8f%e6%9e%b6%e6%a7%8b/'),
    ('06_現有外接模組', 'https://yzuirl.synology.me/wordpress/%E7%8F%BE%E6%9C%89%E5%A4%96%E6%8E%A5%E6%A8%A1%E7%B5%84%E6%96%B0%E7%89%88/'),
    ('07_賓果文件含bricks', 'https://yzuirl.synology.me/wordpress/%E8%B3%93%E6%9E%9C%E6%96%87%E4%BB%B6%E5%90%ABbricks/'),
    ('08_測試試算表流程工具使用方法', 'https://yzuirl.synology.me/wordpress/%E6%B8%AC%E8%A9%A6%E8%A9%A6%E7%AE%97%E8%A1%A8%E6%B5%81%E7%A8%8B%E5%B7%A5%E5%85%B7%E4%BD%BF%E7%94%A8%E6%96%B9%E6%B3%95/'),
    ('09_障礙排除', 'https://yzuirl.synology.me/wordpress/%E9%9A%9C%E7%A4%99%E6%8E%92%E9%99%A4/'),
    ('10_實驗室公用帳號', 'https://yzuirl.synology.me/wordpress/%e5%85%ac%e7%94%a8%e5%b8%b3%e8%99%9f/')
]

out_dir = r'C:\Users\shw12\Downloads\IRL_Lab_AI_ agent\IRL_Lab_AI_ agent\lab_assistant\thesis_viewer\黑曼巴系統完整說明'
os.makedirs(out_dir, exist_ok=True)

# 清理舊檔案
for f in os.listdir(out_dir):
    try:
        os.remove(os.path.join(out_dir, f))
    except Exception:
        pass

def parse_html_to_markdown(elem):
    # 處理表格
    for table in elem.find_all('table'):
        rows = table.find_all('tr')
        if not rows:
            continue
        md_table = []
        first_row_cols = [th.get_text(strip=True).replace('|', '\\|') for th in rows[0].find_all(['th', 'td'])]
        if not first_row_cols:
            continue
        md_table.append('| ' + ' | '.join(first_row_cols) + ' |')
        md_table.append('| ' + ' | '.join(['---'] * len(first_row_cols)) + ' |')
        
        for r in rows[1:]:
            cols = [td.get_text(strip=True).replace('|', '\\|').replace('\n', ' ') for td in r.find_all(['td', 'th'])]
            if len(cols) == len(first_row_cols):
                md_table.append('| ' + ' | '.join(cols) + ' |')
            elif len(cols) > 0:
                while len(cols) < len(first_row_cols):
                    cols.append('')
                md_table.append('| ' + ' | '.join(cols[:len(first_row_cols)]) + ' |')
        table.replace_with('\n\n' + '\n'.join(md_table) + '\n\n')

    # 處理標題
    for h in elem.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        lvl = int(h.name[1])
        h.replace_with(f'\n\n{"#" * lvl} {h.get_text(strip=True)}\n\n')

    # 處理清單
    for li in elem.find_all('li'):
        li.replace_with(f'* {li.get_text(strip=True)}\n')

    # 處理代碼區塊
    for pre in elem.find_all('pre'):
        pre.replace_with(f'\n\n```python\n{pre.get_text(strip=True)}\n```\n\n')

    lines = [line.strip() for line in elem.get_text(separator='\n').split('\n')]
    clean_lines = []
    for l in lines:
        if l:
            clean_lines.append(l)
        elif clean_lines and clean_lines[-1] != '':
            clean_lines.append('')
    return '\n'.join(clean_lines)

for title, url in chapters:
    try:
        r = session.get(url, verify=False, timeout=10)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')
        entry = soup.find('div', class_='entry-content') or soup.find('article') or soup.body
        content = parse_html_to_markdown(entry) if entry else '無內容'
        
        # 針對原網頁留白的安裝部署補充說明
        if title == '03_安裝部署' and len(content.strip()) < 10:
            content = '> **備註**：原 WordPress 站台此頁面作者未填寫內文。相關伺服器配置與 SSL 憑證請參見 SSL 設定與後端部署說明。\n\n' + content

        md_path = os.path.join(out_dir, f'{title}.md')
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(f'# {title}\n> 原始連結：{url}\n\n' + content)
        print(f'成功產生: {title}.md')
    except Exception as e:
        print(f'失敗: {title} - {e}')
