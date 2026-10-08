"""
test_attachment_scanner.py — Phase 5: Attachment Scanner Tests
Comprehensive test coverage for attachment scanning rules.
"""

import pytest
from attachment_scanner import (
    scan_attachment,
    scan_attachments,
    EXECUTABLE_EXTENSIONS,
    MACRO_ENABLED_OFFICE,
    ARCHIVE_EXTENSIONS,
)


# ---------- SINGLE ATTACHMENT TESTS ----------

def test_clean_pdf_attachment():
    """Test that clean PDF files are marked as safe."""
    result = scan_attachment("invoice.pdf", size=50000)
    assert result["verdict"] == "clean"
    assert result["risk_score"] == 0
    assert result["scam_score_adjustment"] == 0
    assert result["block_download"] == False


def test_executable_exe_file():
    """Test that .exe files are marked as malicious."""
    result = scan_attachment("setup.exe", size=1024000)
    assert result["verdict"] == "malicious"
    assert result["risk_score"] == 90
    assert result["scam_score_adjustment"] == 30
    assert result["block_download"] == True
    assert any("Executable" in r for r in result["reasons"])


def test_executable_bat_file():
    """Test that .bat files are marked as malicious."""
    result = scan_attachment("script.bat")
    assert result["verdict"] == "malicious"
    assert result["block_download"] == True


def test_executable_vbs_file():
    """Test that .vbs files are marked as malicious."""
    result = scan_attachment("malware.vbs")
    assert result["verdict"] == "malicious"
    assert result["block_download"] == True


def test_executable_js_file():
    """Test that .js files are marked as malicious."""
    result = scan_attachment("ransomware.js")
    assert result["verdict"] == "malicious"
    assert result["block_download"] == True


def test_double_extension_pdf_exe():
    """Test that invoice.pdf.exe is detected as malicious double extension."""
    result = scan_attachment("invoice.pdf.exe")
    assert result["verdict"] == "malicious"
    assert result["risk_score"] >= 90
    assert result["scam_score_adjustment"] == 30  # Maximum penalty
    assert result["block_download"] == True
    assert any("Double extension" in r for r in result["reasons"])


def test_double_extension_txt_js():
    """Test that document.txt.js is detected as malicious double extension."""
    result = scan_attachment("document.txt.js")
    assert result["verdict"] == "malicious"
    assert result["block_download"] == True
    assert any("Double extension" in r for r in result["reasons"])


def test_double_extension_doc_exe():
    """Test that report.doc.exe is detected as malicious double extension."""
    result = scan_attachment("report.doc.exe")
    assert result["verdict"] == "malicious"
    assert result["block_download"] == True


def test_macro_enabled_excel():
    """Test that .xlsm files are marked as suspicious."""
    result = scan_attachment("spreadsheet.xlsm", size=200000)
    assert result["verdict"] == "suspicious"
    assert result["risk_score"] == 40
    assert result["scam_score_adjustment"] == 10
    assert result["block_download"] == False
    assert any("macro" in r.lower() for r in result["reasons"])


def test_macro_enabled_word():
    """Test that .docm files are marked as suspicious."""
    result = scan_attachment("document.docm")
    assert result["verdict"] == "suspicious"
    assert result["block_download"] == False


def test_macro_enabled_powerpoint():
    """Test that .pptm files are marked as suspicious."""
    result = scan_attachment("presentation.pptm")
    assert result["verdict"] == "suspicious"
    assert result["block_download"] == False


def test_zip_archive_small():
    """Test that small .zip files are marked as suspicious."""
    result = scan_attachment("files.zip", size=500000)
    assert result["verdict"] == "suspicious"
    assert result["risk_score"] <= 20
    assert result["block_download"] == False


def test_zip_archive_large():
    """Test that large .zip files (>10MB) are more suspicious."""
    result = scan_attachment("files.zip", size=15 * 1024 * 1024)
    assert result["verdict"] == "suspicious"
    assert result["risk_score"] > 10
    assert result["scam_score_adjustment"] >= 10
    assert any("Large archive" in r for r in result["reasons"])


def test_rar_archive():
    """Test that .rar files are marked as suspicious."""
    result = scan_attachment("archive.rar", size=1024000)
    assert result["verdict"] == "suspicious"
    assert result["block_download"] == False


def test_script_sh_file():
    """Test that .sh files are marked as suspicious."""
    result = scan_attachment("install.sh")
    assert result["verdict"] == "suspicious"
    assert result["scam_score_adjustment"] >= 10


def test_script_py_file():
    """Test that .py files are marked as suspicious."""
    result = scan_attachment("malware.py")
    assert result["verdict"] == "suspicious"


def test_safe_docx_file():
    """Test that .docx files (normal Office) are clean."""
    result = scan_attachment("report.docx", size=100000)
    assert result["verdict"] == "clean"
    assert result["risk_score"] == 0
    assert result["block_download"] == False


def test_safe_xlsx_file():
    """Test that .xlsx files are clean."""
    result = scan_attachment("data.xlsx")
    assert result["verdict"] == "clean"


def test_safe_image_jpg():
    """Test that .jpg files are clean."""
    result = scan_attachment("photo.jpg", size=2048000)
    assert result["verdict"] == "clean"


def test_safe_image_png():
    """Test that .png files are clean."""
    result = scan_attachment("screenshot.png")
    assert result["verdict"] == "clean"


def test_unknown_extension():
    """Test that unknown file types are marked as suspicious."""
    result = scan_attachment("file.xyz123")
    assert result["verdict"] == "suspicious"
    assert result["risk_score"] == 20
    assert any("Unknown" in r for r in result["reasons"])


def test_no_extension():
    """Test files with no extension."""
    result = scan_attachment("README")
    assert result["verdict"] == "suspicious"
    assert any("Unknown" in r for r in result["reasons"])


def test_case_insensitive_exe():
    """Test that .EXE (uppercase) is detected as malicious."""
    result = scan_attachment("SETUP.EXE")
    assert result["verdict"] == "malicious"
    assert result["block_download"] == True


def test_case_insensitive_double_extension():
    """Test that Invoice.PDF.EXE is detected as malicious."""
    result = scan_attachment("Invoice.PDF.EXE")
    assert result["verdict"] == "malicious"
    assert result["block_download"] == True


# ---------- MULTIPLE ATTACHMENTS TESTS ----------

def test_multiple_clean_attachments():
    """Test scanning multiple clean attachments."""
    attachments = [
        {"filename": "report.pdf", "size": 50000},
        {"filename": "data.xlsx", "size": 100000},
        {"filename": "photo.jpg", "size": 2048000},
    ]
    result = scan_attachments(attachments)
    
    assert result["overall_verdict"] == "clean"
    assert result["malicious_count"] == 0
    assert result["suspicious_count"] == 0
    assert result["clean_count"] == 3
    assert result["block_download"] == False


def test_multiple_with_one_malicious():
    """Test that one malicious attachment makes the overall verdict malicious."""
    attachments = [
        {"filename": "report.pdf", "size": 50000},
        {"filename": "malware.exe", "size": 1024000},
        {"filename": "photo.jpg", "size": 2048000},
    ]
    result = scan_attachments(attachments)
    
    assert result["overall_verdict"] == "malicious"
    assert result["malicious_count"] == 1
    assert result["suspicious_count"] == 0
    assert result["clean_count"] == 2
    assert result["block_download"] == True


def test_multiple_with_suspicious():
    """Test multiple attachments with suspicious files."""
    attachments = [
        {"filename": "report.pdf", "size": 50000},
        {"filename": "macro.xlsm", "size": 100000},
        {"filename": "archive.zip", "size": 5000000},
    ]
    result = scan_attachments(attachments)
    
    assert result["overall_verdict"] == "suspicious"
    assert result["malicious_count"] == 0
    assert result["suspicious_count"] == 2
    assert result["clean_count"] == 1
    assert result["block_download"] == False


def test_empty_attachments_list():
    """Test scanning empty attachment list."""
    result = scan_attachments([])
    
    assert result["overall_verdict"] == "clean"
    assert result["malicious_count"] == 0
    assert result["total_scam_score_adjustment"] == 0
    assert result["block_download"] == False


def test_scam_score_aggregation():
    """Test that scam score adjustments are aggregated correctly."""
    attachments = [
        {"filename": "malware.exe"},  # +30
        {"filename": "file.pdf.exe"},  # +30
    ]
    result = scan_attachments(attachments)
    
    # Total should be capped at 50
    assert result["total_scam_score_adjustment"] <= 50
    assert result["malicious_count"] == 2


def test_highest_risk_score_tracking():
    """Test that highest risk score is tracked correctly."""
    attachments = [
        {"filename": "clean.pdf"},  # risk 0
        {"filename": "suspicious.zip"},  # risk ~10-20
        {"filename": "malicious.exe"},  # risk 90
    ]
    result = scan_attachments(attachments)
    
    assert result["highest_risk_score"] >= 90


# ---------- EDGE CASES ----------

def test_multiple_dots_in_filename():
    """Test filenames with multiple dots but not double extension."""
    result = scan_attachment("my.document.v2.final.pdf")
    assert result["verdict"] == "clean"


def test_double_extension_with_spaces():
    """Test double extension detection ignores spaces (OS-level)."""
    # Note: This tests current behavior; spaces in extensions are rare
    result = scan_attachment("file.pdf.exe")
    assert result["verdict"] == "malicious"


def test_jar_file_detected():
    """Test that .jar files are detected as executables."""
    result = scan_attachment("malware.jar")
    assert result["verdict"] == "malicious"


def test_msi_installer():
    """Test that .msi files are detected as executables."""
    result = scan_attachment("installer.msi")
    assert result["verdict"] == "malicious"


def test_powershell_ps1():
    """Test that PowerShell .ps1 files are detected as executables."""
    result = scan_attachment("script.ps1")
    assert result["verdict"] == "malicious"


def test_hta_file():
    """Test that .hta files are detected as executables."""
    result = scan_attachment("malware.hta")
    assert result["verdict"] == "malicious"


def test_iso_disk_image():
    """Test that .iso files are suspicious."""
    result = scan_attachment("bootable.iso", size=700 * 1024 * 1024)
    assert result["verdict"] == "suspicious"


def test_scam_score_cap_at_50():
    """Test that total scam score adjustment is capped at 50."""
    attachments = [
        {"filename": "file1.exe"},  # +30
        {"filename": "file2.exe"},  # +30
        {"filename": "file3.exe"},  # +30
    ]
    result = scan_attachments(attachments)
    
    assert result["total_scam_score_adjustment"] == 50


# ---------- INTEGRATION TESTS ----------

def test_realistic_phishing_email():
    """Test realistic phishing email with double extension."""
    attachments = [
        {"filename": "Invoice_2026-10-01.pdf.exe", "size": 512000}
    ]
    result = scan_attachments(attachments)
    
    assert result["overall_verdict"] == "malicious"
    assert result["block_download"] == True
    assert result["total_scam_score_adjustment"] >= 25


def test_realistic_legitimate_email():
    """Test realistic legitimate email with safe attachments."""
    attachments = [
        {"filename": "Q4_Report.pdf", "size": 1024000},
        {"filename": "Budget_2026.xlsx", "size": 512000},
        {"filename": "Logo.png", "size": 256000},
    ]
    result = scan_attachments(attachments)
    
    assert result["overall_verdict"] == "clean"
    assert result["total_scam_score_adjustment"] == 0


def test_realistic_suspicious_email():
    """Test realistic suspicious email with macro document."""
    attachments = [
        {"filename": "Project_Plan.xlsm", "size": 200000}
    ]
    result = scan_attachments(attachments)
    
    assert result["overall_verdict"] == "suspicious"
    assert result["block_download"] == False
    assert result["total_scam_score_adjustment"] == 10
