import os
import sys
import time
import statistics

# Ensure utf-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LAB_ASSISTANT_DIR = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, LAB_ASSISTANT_DIR)

from query_service import (
    load_json,
    query_alumni,
    query_properties,
    query_budget,
    query_accounting_rules,
    query_thesis,
    query_person_360,
    evaluate_expense_compliance
)

def benchmark_function(func, args=(), kwargs=None, iterations=5):
    if kwargs is None:
        kwargs = {}
    
    # Warm up / run once
    t0 = time.perf_counter()
    res = func(*args, **kwargs)
    cold_time = (time.perf_counter() - t0) * 1000

    times = []
    for _ in range(iterations):
        t_start = time.perf_counter()
        func(*args, **kwargs)
        times.append((time.perf_counter() - t_start) * 1000)

    avg_time = statistics.mean(times)
    min_time = min(times)
    max_time = max(times)
    
    return {
        "cold_ms": round(cold_time, 2),
        "avg_ms": round(avg_time, 2),
        "min_ms": round(min_time, 2),
        "max_ms": round(max_time, 2),
        "iterations": iterations
    }

def run_all_benchmarks():
    test_cases = [
        ("校友名冊查詢 (query_alumni - 無關鍵字)", query_alumni, ()),
        ("校友名冊查詢 (query_alumni - 關鍵字'蕭宇傑')", query_alumni, ("蕭宇傑",)),
        ("財產清冊查詢 (query_properties - 無關鍵字)", query_properties, ()),
        ("財產清冊查詢 (query_properties - 關鍵字'GPU伺服器')", query_properties, ("GPU",)),
        ("經費帳本查詢 (query_budget - 最近10筆/無關鍵字)", query_budget, ()),
        ("經費帳本查詢 (query_budget - 關鍵字'零食')", query_budget, ("零食",)),
        ("會計報銷法規 (query_accounting_rules - 關鍵字'便當上限')", query_accounting_rules, ("便當",)),
        ("碩士論文檢索 (query_thesis - 多分詞與模糊比對)", query_thesis, ("無人機",)),
        ("360度人物全景速查 (query_person_360 - 跨4庫聯查)", query_person_360, ("蕭宇傑",)),
        ("報帳合規防呆試算 (evaluate_expense_compliance)", evaluate_expense_compliance, ("OpenAI 研討會註冊", 35000, "境外電商", True))
    ]

    print("=" * 70)
    print(" IRL Lab AI Assistant - 本地知識庫查詢效能基準測試 (Benchmark)")
    print("=" * 70)
    
    results = []
    for name, func, args in test_cases:
        stats = benchmark_function(func, args=args, iterations=10)
        results.append((name, stats))
        print(f"[測試項目] {name}")
        print(f"  ➔ 初次冷啟動延遲 : {stats['cold_ms']} ms")
        print(f"  ➔ 暖機平均延遲   : {stats['avg_ms']} ms (Min: {stats['min_ms']} ms, Max: {stats['max_ms']} ms, n=10)")
        print("-" * 70)

    print("\n測試完成！所有測試皆以本地快取資料庫進行。")

if __name__ == "__main__":
    run_all_benchmarks()
