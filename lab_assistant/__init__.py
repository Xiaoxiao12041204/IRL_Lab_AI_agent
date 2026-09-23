"""
IRL Lab AI Assistant - 實驗室智慧詢問模組套件
提供實驗室歷屆論文檢索、成員出勤與請假、財產盤點、公用經費自動記帳與會計報帳合規審核。
"""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
_CONNECTORS = os.path.join(_ROOT, "connectors")
_CORE = os.path.join(_ROOT, "core")

for _p in (_ROOT, _CONNECTORS, _CORE):
    if os.path.exists(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from .core import query_service
from .connectors import (
    nas_reader,
    wiki_reader,
    official_site_reader,
    google_calendar_reader,
    invoice_reader,
    sheets_writer,
)

__all__ = [
    "query_service",
    "nas_reader",
    "wiki_reader",
    "official_site_reader",
    "google_calendar_reader",
    "invoice_reader",
    "sheets_writer",
]
