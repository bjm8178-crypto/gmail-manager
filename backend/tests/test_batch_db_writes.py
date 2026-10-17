"""Tests for Step 5: Batched DB result writes and no-downgrade SQL guards."""
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from database import update_analyzed_emails_bulk
from gmail import DBBatchWriter


def test_update_analyzed_emails_bulk_empty():
    assert update_analyzed_emails_bulk(user_id=1, rows=[]) == 0


def test_update_analyzed_emails_bulk_sql_and_retry_removal():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 2
    mock_conn.cursor.return_value = mock_cursor

    rows = [
        {"email_id": "em_1", "status": "labeled", "label_id": 10, "scam_score": 15},
        {"email_id": "em_2", "status": "labeled", "label_id": 20, "scam_score": 25},
    ]

    with patch("database._get_connection", return_value=mock_conn), \
         patch("database._release_connection") as mock_release, \
         patch("psycopg2.extras.execute_values") as mock_exec_values, \
         patch("database._execute") as mock_execute:

        count = update_analyzed_emails_bulk(user_id=1, rows=rows)

        assert count == 2
        assert mock_exec_values.call_count == 1
        # Check retry_queue deletion called for labeled rows
        assert mock_execute.call_count == 1
        assert "DELETE FROM retry_queue" in mock_execute.call_args[0][1]
        assert mock_conn.commit.call_count == 1
        assert mock_release.call_count == 1


@pytest.mark.asyncio
async def test_db_batch_writer_submits_and_resolves():
    writer = DBBatchWriter(user_id=1, max_batch_size=2, flush_interval=0.1)
    writer.start()

    with patch("database.update_analyzed_emails_bulk", return_value=2) as mock_bulk:
        fut1 = asyncio.create_task(writer.submit({"email_id": "em_1", "status": "labeled"}))
        fut2 = asyncio.create_task(writer.submit({"email_id": "em_2", "status": "labeled"}))

        # Reaching batch_size=2 triggers immediate flush
        res1, res2 = await asyncio.gather(fut1, fut2)
        assert res1 is True
        assert res2 is True
        assert mock_bulk.call_count == 1

    await writer.close()


@pytest.mark.asyncio
async def test_db_batch_writer_fallback_on_bulk_error():
    writer = DBBatchWriter(user_id=1, max_batch_size=5, flush_interval=0.1)
    writer.start()

    # If bulk fails, should fall back to per-row update_analyzed_email
    with patch("database.update_analyzed_emails_bulk", side_effect=Exception("DB connection dropped")), \
         patch("database.update_analyzed_email", return_value=None) as mock_single:

        fut1 = asyncio.create_task(writer.submit({"email_id": "em_fallback", "status": "labeled"}))
        res1 = await fut1
        assert res1 is True
        assert mock_single.call_count == 1
        assert mock_single.call_args[0][0] == "em_fallback"

    await writer.close()
