"""
attachment_scanner.py — Phase 5: Attachment Scanner v1
Detects suspicious email attachments using rule-based detection.

Version 1: Local rules only (extensions, double extensions, macro files)
Version 2 (future): VirusTotal API integration for hash-based scanning

Detection Rules:
1. Executable files: .exe, .bat, .cmd, .scr, .pif, .vbs, .js, .jar
2. Double extensions: invoice.pdf.exe, document.txt.js
3. Macro-enabled Office: .xlsm, .docm, .pptm
4. Archives (metadata only): .zip, .rar (flagged as suspicious, not malicious)

Risk Levels:
- malicious: Executable files, double extensions (blocks download)
- suspicious: Macro-enabled Office, archives (shows warning)
- clean: Normal file types

Scam Score Adjustments:
- +30 for malicious attachments
- +15 for double extensions
- +10 for macro-enabled Office files
- +5 for large archives (>10MB)
"""

from logger_setup import get_logger
logger = get_logger(__name__)

from typing import List, Dict, Optional
import os
import re


# ---------- DETECTION RULES ----------

# Executable file extensions (high risk - always malicious)
EXECUTABLE_EXTENSIONS = {
    '.exe', '.bat', '.cmd', '.scr', '.pif', '.com',
    '.vbs', '.vbe', '.js', '.jse', '.wsf', '.wsh',
    '.jar', '.app', '.deb', '.rpm', '.dmg', '.pkg',
    '.msi', '.dll', '.so', '.dylib',
    '.ps1', '.psm1',  # PowerShell
    '.hta',  # HTML Application
}

# Macro-enabled Office document extensions (suspicious)
MACRO_ENABLED_OFFICE = {
    '.xlsm', '.xlsb',  # Excel with macros
    '.docm',  # Word with macros
    '.pptm',  # PowerPoint with macros
    '.potm', '.ppsm',  # PowerPoint templates/shows with macros
    '.dotm',  # Word templates with macros
    '.xltm',  # Excel templates with macros
}

# Archive extensions (suspicious if large or from unknown sender)
ARCHIVE_EXTENSIONS = {
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',
    '.tar.gz', '.tgz', '.tar.bz2',
    '.iso', '.img',  # Disk images
}

# Script/source code extensions (suspicious)
SCRIPT_EXTENSIONS = {
    '.sh', '.bash', '.py', '.rb', '.pl', '.php',
    '.cgi', '.asp', '.aspx', '.jsp',
}

# Safe common file types (explicitly allowed)
SAFE_EXTENSIONS = {
    '.pdf', '.txt', '.rtf', '.md',
    '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.odt', '.ods', '.odp',  # OpenDocument
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp',
    '.mp3', '.mp4', '.wav', '.avi', '.mov', '.mkv',
    '.csv', '.json', '.xml', '.yaml', '.yml',
    '.ics',  # Calendar files
}

# File size thresholds (bytes)
LARGE_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
HUGE_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


# ---------- DETECTION FUNCTIONS ----------

def scan_attachment(filename: str, size: int = 0) -> Dict[str, any]:
    """
    Scan a single attachment for suspicious characteristics.
    
    Args:
        filename: Attachment filename (e.g., "invoice.pdf", "document.txt.exe")
        size: File size in bytes (optional)
    
    Returns:
        {
            "verdict": "malicious" | "suspicious" | "clean",
            "risk_score": 0-100 (0=safe, 100=definitely malicious),
            "reasons": ["reason1", "reason2", ...],
            "scam_score_adjustment": 0-30 (points to add to email scam_score),
            "block_download": True | False,
        }
    """
    filename_lower = filename.lower()
    reasons = []
    risk_score = 0
    scam_score_adjustment = 0
    
    # Rule 1: Check for double extensions (HIGHEST PRIORITY)
    double_ext_result = _check_double_extension(filename_lower)
    if double_ext_result["detected"]:
        reasons.append(double_ext_result["reason"])
        risk_score += 40
        scam_score_adjustment += 15
        # Double extension is ALWAYS malicious
        return {
            "verdict": "malicious",
            "risk_score": 95,
            "reasons": reasons + ["Double extension detected - likely masquerading malware"],
            "scam_score_adjustment": 30,  # Maximum penalty
            "block_download": True,
        }
    
    # Rule 2: Check for executable extensions
    if _has_extension(filename_lower, EXECUTABLE_EXTENSIONS):
        ext = _get_extension(filename_lower)
        reasons.append(f"Executable file extension: {ext}")
        risk_score += 50
        scam_score_adjustment += 30
        return {
            "verdict": "malicious",
            "risk_score": 90,
            "reasons": reasons + ["Executable files are blocked for security"],
            "scam_score_adjustment": scam_score_adjustment,
            "block_download": True,
        }
    
    # Rule 3: Check for macro-enabled Office documents
    if _has_extension(filename_lower, MACRO_ENABLED_OFFICE):
        ext = _get_extension(filename_lower)
        reasons.append(f"Macro-enabled Office document: {ext}")
        risk_score += 25
        scam_score_adjustment += 10
        return {
            "verdict": "suspicious",
            "risk_score": 40,
            "reasons": reasons + ["Document contains macros - verify sender before opening"],
            "scam_score_adjustment": scam_score_adjustment,
            "block_download": False,
        }
    
    # Rule 4: Check for script files
    if _has_extension(filename_lower, SCRIPT_EXTENSIONS):
        ext = _get_extension(filename_lower)
        reasons.append(f"Script file: {ext}")
        risk_score += 30
        scam_score_adjustment += 15
        return {
            "verdict": "suspicious",
            "risk_score": 50,
            "reasons": reasons + ["Script files can be dangerous - verify sender"],
            "scam_score_adjustment": scam_score_adjustment,
            "block_download": False,
        }
    
    # Rule 5: Check for archives
    if _has_extension(filename_lower, ARCHIVE_EXTENSIONS):
        ext = _get_extension(filename_lower)
        reasons.append(f"Archive file: {ext}")
        risk_score += 10
        scam_score_adjustment += 5
        
        # Large archives are more suspicious
        if size > LARGE_FILE_SIZE:
            size_mb = size / (1024 * 1024)
            reasons.append(f"Large archive: {size_mb:.1f} MB")
            risk_score += 10
            scam_score_adjustment += 5
        
        return {
            "verdict": "suspicious",
            "risk_score": risk_score,
            "reasons": reasons + ["Archive files may contain hidden malware - scan before extracting"],
            "scam_score_adjustment": scam_score_adjustment,
            "block_download": False,
        }
    
    # Rule 6: Check for safe extensions
    if _has_extension(filename_lower, SAFE_EXTENSIONS):
        return {
            "verdict": "clean",
            "risk_score": 0,
            "reasons": ["Common safe file type"],
            "scam_score_adjustment": 0,
            "block_download": False,
        }
    
    # Unknown extension - treat as suspicious
    ext = _get_extension(filename_lower)
    reasons.append(f"Unknown file type: {ext or '(no extension)'}")
    return {
        "verdict": "suspicious",
        "risk_score": 20,
        "reasons": reasons + ["Unknown file type - verify before opening"],
        "scam_score_adjustment": 5,
        "block_download": False,
    }


def scan_attachments(attachments: List[Dict[str, any]]) -> Dict[str, any]:
    """
    Scan multiple attachments and aggregate results.
    
    Args:
        attachments: List of attachment dicts with "filename" and optional "size"
                     [{"filename": "file.pdf", "size": 12345}, ...]
    
    Returns:
        {
            "overall_verdict": "malicious" | "suspicious" | "clean",
            "highest_risk_score": 0-100,
            "total_scam_score_adjustment": 0-50,
            "malicious_count": 0,
            "suspicious_count": 0,
            "clean_count": 0,
            "results": [
                {"filename": "file.pdf", "verdict": "clean", ...},
                ...
            ],
            "block_download": True | False,
        }
    """
    if not attachments:
        return {
            "overall_verdict": "clean",
            "highest_risk_score": 0,
            "total_scam_score_adjustment": 0,
            "malicious_count": 0,
            "suspicious_count": 0,
            "clean_count": 0,
            "results": [],
            "block_download": False,
        }
    
    results = []
    malicious_count = 0
    suspicious_count = 0
    clean_count = 0
    highest_risk_score = 0
    total_scam_score_adjustment = 0
    
    for attachment in attachments:
        filename = attachment.get("filename", "")
        size = attachment.get("size", 0)
        
        result = scan_attachment(filename, size)
        result["filename"] = filename
        results.append(result)
        
        # Update counters
        if result["verdict"] == "malicious":
            malicious_count += 1
        elif result["verdict"] == "suspicious":
            suspicious_count += 1
        else:
            clean_count += 1
        
        # Track highest risk
        highest_risk_score = max(highest_risk_score, result["risk_score"])
        total_scam_score_adjustment += result["scam_score_adjustment"]
    
    # Determine overall verdict (worst case)
    if malicious_count > 0:
        overall_verdict = "malicious"
        block_download = True
    elif suspicious_count > 0:
        overall_verdict = "suspicious"
        block_download = False
    else:
        overall_verdict = "clean"
        block_download = False
    
    # Cap total scam score adjustment at 50
    total_scam_score_adjustment = min(total_scam_score_adjustment, 50)
    
    return {
        "overall_verdict": overall_verdict,
        "highest_risk_score": highest_risk_score,
        "total_scam_score_adjustment": total_scam_score_adjustment,
        "malicious_count": malicious_count,
        "suspicious_count": suspicious_count,
        "clean_count": clean_count,
        "results": results,
        "block_download": block_download,
    }


# ---------- HELPER FUNCTIONS ----------

def _get_extension(filename: str) -> str:
    """Extract file extension from filename (including dot)."""
    if '.' not in filename:
        return ''
    return '.' + filename.split('.')[-1]


def _has_extension(filename: str, extensions: set) -> bool:
    """Check if filename has one of the given extensions."""
    ext = _get_extension(filename)
    return ext in extensions


def _check_double_extension(filename: str) -> Dict[str, any]:
    """
    Detect double extensions like "invoice.pdf.exe" or "document.txt.js".
    
    Returns:
        {"detected": True/False, "reason": "explanation"}
    """
    parts = filename.split('.')
    if len(parts) < 3:
        return {"detected": False, "reason": ""}
    
    # Get last two extensions
    penultimate_ext = '.' + parts[-2]
    final_ext = '.' + parts[-1]
    
    # Check if final extension is executable AND penultimate is a safe extension
    if final_ext in EXECUTABLE_EXTENSIONS and penultimate_ext in SAFE_EXTENSIONS:
        return {
            "detected": True,
            "reason": f"Double extension detected: {penultimate_ext}{final_ext} (masquerading as {penultimate_ext})"
        }
    
    # Check for common double-extension patterns
    if final_ext in EXECUTABLE_EXTENSIONS:
        # Any non-executable followed by executable is suspicious
        if penultimate_ext not in EXECUTABLE_EXTENSIONS:
            return {
                "detected": True,
                "reason": f"Double extension detected: {penultimate_ext}{final_ext}"
            }
    
    return {"detected": False, "reason": ""}


# ---------- EXPORTS ----------

__all__ = [
    'scan_attachment',
    'scan_attachments',
    'EXECUTABLE_EXTENSIONS',
    'MACRO_ENABLED_OFFICE',
    'ARCHIVE_EXTENSIONS',
]
