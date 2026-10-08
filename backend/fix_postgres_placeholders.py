from logger_setup import get_logger
logger = get_logger(__name__)

#!/usr/bin/env python3
"""
Script to replace SQLite ? placeholders with Postgres %s placeholders in database.py
Also fixes INSERT OR REPLACE to use Postgres ON CONFLICT syntax
"""

import re

def fix_placeholders(content):
    """Replace ? with %s in SQL queries"""
    # Replace ? with %s (simple global replacement)
    # This works because ? is only used as SQL placeholder in this file
    content = content.replace('?', '%s')
    return content

def fix_insert_or_replace(content):
    """Replace INSERT OR REPLACE with Postgres ON CONFLICT syntax"""
    
    # Find the INSERT OR REPLACE statement for analyzed_emails
    old_pattern = r'''INSERT OR REPLACE INTO analyzed_emails
            \(email_id, user_id, label_id, scam_score, scam_indicators, is_quarantined, snippet, sender, subject, status, body\)
            VALUES \(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s\)'''
    
    new_statement = '''INSERT INTO analyzed_emails
            (email_id, user_id, label_id, scam_score, scam_indicators, is_quarantined, snippet, sender, subject, status, body)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (email_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                label_id = EXCLUDED.label_id,
                scam_score = EXCLUDED.scam_score,
                scam_indicators = EXCLUDED.scam_indicators,
                is_quarantined = EXCLUDED.is_quarantined,
                snippet = EXCLUDED.snippet,
                sender = EXCLUDED.sender,
                subject = EXCLUDED.subject,
                status = EXCLUDED.status,
                body = EXCLUDED.body'''
    
    # Use a more flexible pattern to match the statement
    content = re.sub(
        r'INSERT OR REPLACE INTO analyzed_emails\s*\([^)]+\)\s*VALUES\s*\([^)]+\)',
        new_statement,
        content,
        flags=re.MULTILINE | re.DOTALL
    )
    
    return content

def main():
    logger.info("=" * 60)
    logger.info("Fixing database.py for Postgres Compatibility")
    logger.info("=" * 60)
    
    # Read the file
    logger.info("\n[1/4] Reading database.py...")
    with open('database.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_length = len(content)
    question_marks = content.count('?')
    logger.info(f"      File size: {original_length} bytes")
    logger.info(f"      Found {question_marks} question marks to replace")
    
    # Fix placeholders
    logger.info("\n[2/4] Replacing ? with %s...")
    content = fix_placeholders(content)
    new_question_marks = content.count('?')
    percent_s_count = content.count('%s')
    logger.info(f"      Remaining ?: {new_question_marks}")
    logger.info(f"      Now have: {percent_s_count} instances of %s")
    
    # Fix INSERT OR REPLACE
    logger.info("\n[3/4] Converting INSERT OR REPLACE to ON CONFLICT...")
    if 'INSERT OR REPLACE' in content:
        content = fix_insert_or_replace(content)
        if 'ON CONFLICT (email_id) DO UPDATE' in content:
            logger.info("      ✅ Successfully converted to ON CONFLICT syntax")
        else:
            logger.info("      ⚠️  Pattern match may have failed, manual review needed")
    else:
        logger.info("      ℹ️  No INSERT OR REPLACE found (may already be fixed)")
    
    # Write back
    logger.info("\n[4/4] Writing updated database.py...")
    with open('database.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    logger.info(f"      ✅ File updated successfully")
    logger.info(f"\n{'=' * 60}")
    logger.info("✅ Migration complete!")
    logger.info("\nNext steps:")
    logger.info("  1. Review database.py for any issues")
    logger.info("  2. Test with: python -c 'import database; database.init_db()'")
    logger.info("  3. If errors occur, restore from: database.py.backup_postgres_migration")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
