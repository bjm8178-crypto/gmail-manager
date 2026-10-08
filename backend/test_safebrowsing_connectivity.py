"""
test_safebrowsing_connectivity.py — Standalone Google Safe Browsing API connectivity test
Run this directly in Railway's shell or as a one-off script to test if the API is reachable.

Usage (Railway shell):
  python test_safebrowsing_connectivity.py

Expected: If working, should return 200 with threat match for the malware test URL.
If failing: Will show the exact exception (ConnectionError, TimeoutError, etc.)
"""

from logger_setup import get_logger
logger = get_logger(__name__)

import os
import json
import time
import urllib.request
import urllib.error
import socket

SAFE_BROWSING_KEY = os.getenv("GOOGLE_SAFE_BROWSING_KEY")

def test_safe_browsing():
    """Test Google Safe Browsing API connectivity with a known malware test URL."""
    
    logger.info("=" * 60)
    logger.info("GOOGLE SAFE BROWSING API CONNECTIVITY TEST")
    logger.info("=" * 60)
    
    # Step 1: Check if API key is configured
    if not SAFE_BROWSING_KEY or SAFE_BROWSING_KEY == "your_key_here":
        logger.error("[ERROR] GOOGLE_SAFE_BROWSING_KEY is not configured in environment variables.")
        logger.info("        Set it in Railway's Variables tab before testing.")
        return
    
    logger.info(f"[OK] API key found (length: {len(SAFE_BROWSING_KEY)} chars)")
    logger.info("")
    
    # Step 2: Test with Google's official malware test URL
    test_url = "http://malware.testing.google.test/testing/malware/"
    endpoint = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
    
    body = {
        "client": {
            "clientId": "gmail-manager-test",
            "clientVersion": "1.0",
        },
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": test_url}],
        },
    }
    
    logger.info(f"[TEST] Testing URL: {test_url}")
    logger.info(f"[TEST] Endpoint: https://safebrowsing.googleapis.com/v4/threatMatches:find")
    logger.info(f"[TEST] Timeout: 10 seconds")
    logger.info("")
    
    # Step 3: Make the API call with timing
    try:
        t_start = time.perf_counter()
        
        # Prepare request
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'x-goog-api-key': SAFE_BROWSING_KEY},
            method='POST'
        )
        
        # Set timeout to 10 seconds
        with urllib.request.urlopen(req, timeout=10.0) as response:
            status_code = response.status
            response_data = response.read().decode('utf-8')
        
        t_elapsed = time.perf_counter() - t_start
        
        logger.info(f"[OK] Connection successful!")
        logger.info(f"[OK] Response time: {t_elapsed:.2f} seconds")
        logger.info(f"[OK] Status code: {status_code}")
        logger.info("")
        
        if status_code == 200:
            data = json.loads(response_data)
            if data.get("matches"):
                logger.info(f"[OK] Threat detected (expected for test URL): {data['matches'][0].get('threatType')}")
                logger.info("[RESULT] Google Safe Browsing API is WORKING correctly.")
            else:
                logger.info("[WARNING] No threat detected for malware test URL (unexpected).")
                logger.info("          This might indicate the API key is invalid or test URL changed.")
        else:
            logger.error(f"[ERROR] Unexpected status code: {status_code}")
            logger.info(f"        Response: {response_data[:200]}")
    
    except socket.timeout:
        logger.error(f"[ERROR] Timeout: Connection to Safe Browsing API timed out after 10s")
        logger.info("")
        logger.info("[DIAGNOSIS] Railway egress cannot reach safebrowsing.googleapis.com")
        logger.info("            Possible causes:")
        logger.info("            - Railway firewall/networking blocking Google APIs")
        logger.info("            - Google Safe Browsing API endpoint down/unreachable")
        logger.info("            - DNS resolution failing for googleapis.com")
    
    except urllib.error.URLError as e:
        if isinstance(e.reason, socket.timeout):
            logger.error(f"[ERROR] Timeout: Connection to Safe Browsing API timed out")
        else:
            logger.error(f"[ERROR] URLError: Failed to establish connection")
            logger.info(f"        Reason: {e.reason}")
        logger.info("")
        logger.info("[DIAGNOSIS] Network connectivity issue")
        logger.info("            Possible causes:")
        logger.info("            - Railway cannot route to external Google APIs")
        logger.info("            - DNS failure")
        logger.info("            - Firewall blocking outbound HTTPS to googleapis.com")
    
    except urllib.error.HTTPError as e:
        logger.error(f"[ERROR] HTTP Error {e.code}: {e.reason}")
        logger.info(f"        Response: {e.read().decode('utf-8')[:200]}")
        logger.info("")
        if e.code == 400:
            logger.info("[DIAGNOSIS] Bad request - API key may be invalid")
        elif e.code == 403:
            logger.info("[DIAGNOSIS] Forbidden - API key invalid or lacks Safe Browsing permissions")
    
    except Exception as e:
        logger.error(f"[ERROR] Unexpected error: {type(e).__name__}: {e}")
        logger.info("")
        logger.info("[DIAGNOSIS] Unknown issue - see exception details above")
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("TEST COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    test_safe_browsing()
