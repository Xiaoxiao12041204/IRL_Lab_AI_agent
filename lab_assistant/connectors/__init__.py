"""
IRL Lab AI Assistant - 外部系統與雲端服務串接讀寫器模組 (Connectors)
包含：
- nas_reader: NAS Synology 檔案系統與歷屆畢業論文串流讀取
- wiki_reader: MediaWiki 實驗室維基知識庫檢索
- official_site_reader: IRL 實驗室官方網站即時爬取與解析
- google_calendar_reader: Google Calendar 實驗室行事曆出勤與請假
- invoice_reader: 臺灣電子發票 QR Code 辨識與會計合規防呆檢核
- sheets_writer: Google Sheets 雲端公用經費雙向自動記帳
"""

from . import nas_reader
from . import wiki_reader
from . import official_site_reader
from . import google_calendar_reader
from . import invoice_reader
from . import sheets_writer

__all__ = [
    "nas_reader",
    "wiki_reader",
    "official_site_reader",
    "google_calendar_reader",
    "invoice_reader",
    "sheets_writer",
]
