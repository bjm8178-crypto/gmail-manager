"""Benchmark pipeline with simulated latencies (fakes only, no real DB or network).

Simulated latencies:
- Gmail get: 150ms
- Gmail modify: 150ms
- AI single call: 600ms
- AI batch call: 900ms
- DB call: 5ms
- URL scan: 100ms

Measures:
- fetch_only_pipeline
- label_only_pipeline
- apply_all_pending (label sync)
"""

import argparse
import asyncio
import os
import sys
import time
from unittest.mock import MagicMock, patch

# Ensure backend directory is in path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Set required environment variables before imports
os.environ.setdefault("DATABASE_URL", "postgresql://fake:fake@localhost:5432/fake")
os.environ.setdefault("SESSION_SECRET_KEY", "bench" * 8)
os.environ.setdefault("JWT_SECRET_KEY", "bench" * 8)
os.environ.setdefault("SECRET_KEY", "bench" * 8)
os.environ.setdefault("DB_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
os.environ.setdefault("GOOGLE_CLIENT_ID", "fake")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "fake")

# Mock psycopg2 pool before any module imports database
import psycopg2.pool
class FakeConnectionPool:
    def __init__(self, *args, **kwargs):
        pass
    def getconn(self):
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = None
        conn.cursor.return_value = cursor
        return conn
    def putconn(self, *args, **kwargs):
        pass
    def closeall(self):
        pass

psycopg2.pool.ThreadedConnectionPool = FakeConnectionPool


class BenchMetrics:
    def __init__(self, scale=1.0):
        self.scale = scale
        self.gmail_calls = 0
        self.ai_calls = 0
        self.db_calls = 0
        self.lock = asyncio.Lock()

    def sync_gmail(self, count=1, latency=0.150):
        self.gmail_calls += count
        if self.scale > 0:
            time.sleep(latency * count * self.scale)

    async def async_gmail(self, count=1, latency=0.150):
        async with self.lock:
            self.gmail_calls += count
        if self.scale > 0:
            await asyncio.sleep(latency * count * self.scale)

    def sync_db(self, count=1, latency=0.005):
        self.db_calls += count
        if self.scale > 0:
            time.sleep(latency * count * self.scale)

    async def async_db(self, count=1, latency=0.005):
        async with self.lock:
            self.db_calls += count
        if self.scale > 0:
            await asyncio.sleep(latency * count * self.scale)

    async def async_ai_single(self):
        async with self.lock:
            self.ai_calls += 1
        if self.scale > 0:
            await asyncio.sleep(0.600 * self.scale)

    async def async_ai_batch(self, count=1):
        async with self.lock:
            self.ai_calls += 1
        if self.scale > 0:
            await asyncio.sleep(0.900 * self.scale)

    async def async_url_scan(self):
        if self.scale > 0:
            await asyncio.sleep(0.100 * self.scale)


def generate_fake_emails(count=100):
    labels = ["Inbox", "Work", "Personal", "Receipts"]
    emails = []
    for i in range(count):
        label = labels[i % len(labels)]
        emails.append({
            "id": f"email_{i:04d}",
            "subject": f"Bench email {i} regarding {label}",
            "sender": f"sender_{i % 10}@example.com",
            "snippet": f"Snippet for email {i}",
            "body": f"Full body text for email {i} with url https://example.com/item/{i}",
            "target_label": label,
            "target_label_id": (i % len(labels)) + 1,
            "last_applied_label_id": None,
        })
    return emails


async def bench_fetch_only(emails, metrics):
    from gmail import fetch_only_pipeline

    email_map = {e["id"]: e for e in emails}
    
    # Check if batch fetch flag is active
    fetch_batch_enabled = os.environ.get("FETCH_BATCH", "0") == "1"

    def fake_get_gmail_service(user_email):
        return MagicMock()

    def fake_fetch_emails(limit, page_token=None, user_email=None):
        metrics.sync_gmail(1, 0.150)
        # return metadata stubs without body
        stubs = [
            {"id": e["id"], "snippet": e["snippet"], "sender": e["sender"], "subject": e["subject"], "body": ""}
            for e in emails[:limit]
        ]
        return {"emails": stubs, "next_page_token": None}

    def fake_is_already_analyzed(email_id, user_id):
        metrics.sync_db(1, 0.005)
        return False

    def fake_get_analyzed_email_ids(user_id, email_ids):
        metrics.sync_db(1, 0.005)
        return set()

    def fake_get_email_body(service, email_id):
        metrics.sync_gmail(1, 0.150)
        return email_map[email_id]["body"]

    def fake_get_email_bodies_batch(creds, email_ids):
        # 1 batch call per chunk
        metrics.sync_gmail(1, 0.150)
        return {eid: email_map[eid]["body"] for eid in email_ids if eid in email_map}

    def fake_save_analyzed_email(**kwargs):
        metrics.sync_db(1, 0.005)

    def fake_save_fetched_emails_bulk(user_id, rows):
        metrics.sync_db(1, 0.005)

    t0 = time.perf_counter()
    with patch("gmail.get_gmail_service", side_effect=fake_get_gmail_service), \
         patch("gmail.fetch_emails", side_effect=fake_fetch_emails), \
         patch("gmail.is_already_analyzed", side_effect=fake_is_already_analyzed), \
         patch("database.is_already_analyzed", side_effect=fake_is_already_analyzed), \
         patch("database.get_analyzed_email_ids", side_effect=fake_get_analyzed_email_ids, create=True), \
         patch("gmail._get_email_body", side_effect=fake_get_email_body), \
         patch("gmail._get_email_bodies_batch", side_effect=fake_get_email_bodies_batch, create=True), \
         patch("gmail.save_analyzed_email", side_effect=fake_save_analyzed_email), \
         patch("database.save_analyzed_email", side_effect=fake_save_analyzed_email), \
         patch("database.save_fetched_emails_bulk", side_effect=fake_save_fetched_emails_bulk, create=True):

        results = []
        async for event in fetch_only_pipeline(limit=len(emails), user_id=1, user_email="bench@test.com"):
            results.append(event)

    wall = time.perf_counter() - t0
    return wall


async def bench_label_only(emails, metrics):
    from gmail import label_only_pipeline
    import ai_router

    email_map = {e["id"]: e for e in emails}
    labels_list = [
        {"label_id": 1, "label_name": "Inbox", "bg_color": "#4285f4", "text_color": "#ffffff"},
        {"label_id": 2, "label_name": "Work", "bg_color": "#34a853", "text_color": "#ffffff"},
        {"label_id": 3, "label_name": "Personal", "bg_color": "#fbbc05", "text_color": "#ffffff"},
        {"label_id": 4, "label_name": "Receipts", "bg_color": "#ea4335", "text_color": "#ffffff"},
    ]

    def fake_get_gmail_service(user_email):
        svc = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.side_effect = lambda: (
            metrics.sync_gmail(1, 0.150),
            {"labels": [{"name": l["label_name"], "id": f"Label_{l['label_id']}"} for l in labels_list]}
        )[1]
        svc.users().labels().list.return_value = mock_list
        return svc

    def fake_get_labels(user_id):
        metrics.sync_db(1, 0.005)
        return labels_list

    def fake_get_emails_by_status(user_id, status="fetched", limit=None):
        metrics.sync_db(1, 0.005)
        return [
            {
                "id": e["id"],
                "email_id": e["id"],
                "subject": e["subject"],
                "sender": e["sender"],
                "snippet": e["snippet"],
                "body": e["body"],
                "received_at": None,
            }
            for e in emails[:limit]
        ]

    def fake_get_label_id_by_name(user_id, name):
        metrics.sync_db(1, 0.005)
        for l in labels_list:
            if l["label_name"].casefold() == name.casefold():
                return l["label_id"]
        return 1

    def fake_update_analyzed_email(**kwargs):
        metrics.sync_db(1, 0.005)

    def fake_add_to_retry_queue(*args, **kwargs):
        metrics.sync_db(1, 0.005)

    def fake_remove_from_retry_queue(*args, **kwargs):
        metrics.sync_db(1, 0.005)

    async def fake_scan_urls_batch(urls, email_id, client):
        await metrics.async_url_scan()
        return {}

    async def fake_analyze_json(prompt):
        await metrics.async_ai_single()
        return {
            "data": {
                "label": "Work",
                "scam_score": 10,
                "scam_indicators": [],
                "reasoning": "Standard work communication",
            },
            "provider_used": "fake_ai",
        }

    async def fake_analyze_batch(items, available_labels):
        await metrics.async_ai_batch(len(items))
        return {
            "results": [
                {
                    "id": item["id"],
                    "label": "Work",
                    "scam_score": 10,
                    "scam_indicators": [],
                    "reasoning": "Batch work classification",
                }
                for item in items
            ],
            "provider_used": "fake_ai_batch",
        }

    t0 = time.perf_counter()
    with patch("gmail.get_gmail_service", side_effect=fake_get_gmail_service), \
         patch("gmail.get_labels", side_effect=fake_get_labels), \
         patch("database.get_labels", side_effect=fake_get_labels), \
         patch("database.get_emails_by_status", side_effect=fake_get_emails_by_status), \
         patch("database.get_label_id_by_name", side_effect=fake_get_label_id_by_name), \
         patch("gmail.get_label_id_by_name", side_effect=fake_get_label_id_by_name), \
         patch("database.update_analyzed_email", side_effect=fake_update_analyzed_email), \
         patch("database.add_to_retry_queue", side_effect=fake_add_to_retry_queue), \
         patch("gmail.add_to_retry_queue", side_effect=fake_add_to_retry_queue), \
         patch("database.remove_from_retry_queue", side_effect=fake_remove_from_retry_queue), \
         patch("gmail.remove_from_retry_queue", side_effect=fake_remove_from_retry_queue), \
         patch("security.scan_urls_batch", side_effect=fake_scan_urls_batch), \
         patch("security.extract_urls", return_value=["https://example.com/test"]), \
         patch.object(ai_router.AIRouter, "analyze_json", side_effect=fake_analyze_json), \
         patch.object(ai_router.AIRouter, "analyze_batch", side_effect=fake_analyze_batch, create=True):

        results = []
        async for event in label_only_pipeline(limit=len(emails), user_id=1, user_email="bench@test.com"):
            results.append(event)

    wall = time.perf_counter() - t0
    return wall


async def bench_sync(emails, metrics):
    from main import apply_all_pending
    from starlette.requests import Request

    labels_list = [
        {"label_id": 1, "label_name": "Inbox", "bg_color": "#4285f4", "text_color": "#ffffff"},
        {"label_id": 2, "label_name": "Work", "bg_color": "#34a853", "text_color": "#ffffff"},
        {"label_id": 3, "label_name": "Personal", "bg_color": "#fbbc05", "text_color": "#ffffff"},
        {"label_id": 4, "label_name": "Receipts", "bg_color": "#ea4335", "text_color": "#ffffff"},
    ]

    def fake_get_connection():
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = [{"email_id": e["id"]} for e in emails]
        cursor.fetchone.side_effect = lambda: {"label_id": 2, "last_applied_label_id": None}
        conn.cursor.return_value = cursor
        
        def fake_execute(*args, **kwargs):
            metrics.sync_db(1, 0.005)
        cursor.execute.side_effect = fake_execute
        return conn

    def fake_release_connection(conn):
        pass

    def fake_get_gmail_service(user_email):
        svc = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.side_effect = lambda: (
            metrics.sync_gmail(1, 0.150),
            {"labels": [{"name": f"GM/{l['label_name']}", "id": f"Label_{l['label_id']}"} for l in labels_list]}
        )[1]
        svc.users().labels().list.return_value = mock_list

        mock_modify = MagicMock()
        mock_modify.execute.side_effect = lambda: (
            metrics.sync_gmail(1, 0.150),
            {"id": "ok"}
        )[1]
        svc.users().messages().modify.return_value = mock_modify
        svc.users().messages().batchModify.return_value = mock_modify

        mock_get = MagicMock()
        mock_get.execute.side_effect = lambda: (
            metrics.sync_gmail(1, 0.150),
            {"labelIds": ["Label_2"]}
        )[1]
        svc.users().messages().get.return_value = mock_get

        def fake_batch_req(callback=None):
            req = MagicMock()
            def fake_batch_execute():
                metrics.sync_gmail(1, 0.150)
            req.execute.side_effect = fake_batch_execute
            return req
        svc.new_batch_http_request.side_effect = fake_batch_req
        return svc

    def fake_get_labels(user_id):
        metrics.sync_db(1, 0.005)
        return labels_list

    t0 = time.perf_counter()
    with patch("main._get_connection", side_effect=fake_get_connection), \
         patch("database._get_connection", side_effect=fake_get_connection), \
         patch("main._release_connection", side_effect=fake_release_connection), \
         patch("database._release_connection", side_effect=fake_release_connection), \
         patch("main._execute", side_effect=lambda c, q, p=None: metrics.sync_db(1, 0.005)), \
         patch("database._execute", side_effect=lambda c, q, p=None: metrics.sync_db(1, 0.005)), \
         patch("main._request_user_email", return_value="bench@test.com"), \
         patch("gmail.get_gmail_service", side_effect=fake_get_gmail_service), \
         patch("database.get_labels", side_effect=fake_get_labels), \
         patch("gmail.get_labels", side_effect=fake_get_labels):

        fake_req = MagicMock(spec=Request)
        fake_user = {"user_id": 1, "email": "bench@test.com"}
        res = await apply_all_pending(request=fake_req, user=fake_user, limit=len(emails))

    wall = time.perf_counter() - t0
    return wall


async def run_benchmark(num_emails=100, scale=1.0):
    print(f"\n================ BENCHMARK PIPELINE ({num_emails} emails, scale={scale}) ================")
    emails = generate_fake_emails(num_emails)

    stages = [
        ("fetch_only", bench_fetch_only),
        ("label_only", bench_label_only),
        ("label_sync", bench_sync),
    ]

    results = []
    total_wall = 0.0
    total_gmail = 0
    total_ai = 0
    total_db = 0

    for name, bench_fn in stages:
        m = BenchMetrics(scale=scale)
        wall = await bench_fn(emails, m)
        epm = (num_emails / wall * 60) if wall > 0 else 0.0
        results.append({
            "stage": name,
            "emails": num_emails,
            "wall_s": wall,
            "epm": epm,
            "gmail_calls": m.gmail_calls,
            "ai_calls": m.ai_calls,
            "db_calls": m.db_calls,
        })
        total_wall += wall
        total_gmail += m.gmail_calls
        total_ai += m.ai_calls
        total_db += m.db_calls

    total_epm = (num_emails / total_wall * 60) if total_wall > 0 else 0.0

    print("\n--------------------------------------------------------------------------------------------------")
    print(f"{'Stage':<15} | {'Emails':<8} | {'Wall-clock':<12} | {'Emails/min':<12} | {'Gmail Calls':<12} | {'AI Calls':<10} | {'DB Calls':<10}")
    print("--------------------------------------------------------------------------------------------------")
    for r in results:
        print(f"{r['stage']:<15} | {r['emails']:<8} | {r['wall_s']:>10.2f}s | {r['epm']:>12.1f} | {r['gmail_calls']:>12} | {r['ai_calls']:>10} | {r['db_calls']:>10}")
    print("--------------------------------------------------------------------------------------------------")
    print(f"{'TOTAL':<15} | {num_emails:<8} | {total_wall:>10.2f}s | {total_epm:>12.1f} | {total_gmail:>12} | {total_ai:>10} | {total_db:>10}")
    print("--------------------------------------------------------------------------------------------------\n")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline benchmark with simulated latencies")
    parser.add_argument("--emails", type=int, default=100, help="Number of fake emails (default: 100)")
    parser.add_argument("--scale", type=float, default=1.0, help="Latency scale factor (1.0 = real simulated latency)")
    args = parser.parse_args()

    asyncio.run(run_benchmark(num_emails=args.emails, scale=args.scale))
