from logger_setup import get_logger
logger = get_logger(__name__)

#!/usr/bin/env python3
"""
Gmail Intelligence Manager - SQLite to Postgres Data Migration Script
Generated: 2026-07-21
Purpose: One-time migration of data from local SQLite to Railway Postgres

Usage:
    python migrate_to_postgres.py

Prerequisites:
    - Railway Postgres database must be provisioned
    - DATABASE_URL environment variable must be set
    - gmail_manager.db must exist in the same directory
    - psycopg2-binary must be installed

This script:
    1. Connects to both SQLite and Postgres databases
    2. Copies all data from SQLite to Postgres
    3. Preserves primary keys, foreign keys, and relationships
    4. Validates data integrity after migration
    5. Provides rollback instructions if migration fails
"""

import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from pathlib import Path
from datetime import datetime

# Configuration
SQLITE_DB_PATH = Path(__file__).parent / "gmail_manager.db"
DATABASE_URL = os.getenv("DATABASE_URL")

# Table migration order (respects foreign key dependencies)
TABLES = [
    "users",
    "custom_labels",
    "scan_cursor",
    "analyzed_emails",
    "url_cache",
    "retry_queue"
]

def connect_sqlite():
    """Connect to SQLite database"""
    if not SQLITE_DB_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found at {SQLITE_DB_PATH}")
    
    conn = sqlite3.connect(str(SQLITE_DB_PATH))
    conn.row_factory = sqlite3.Row
    logger.info(f"✅ Connected to SQLite: {SQLITE_DB_PATH}")
    return conn

def connect_postgres():
    """Connect to Postgres database"""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable not set")
    
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    logger.info(f"✅ Connected to Postgres: {DATABASE_URL[:30]}...")
    return conn

def get_row_count(conn, table_name, is_postgres=False):
    """Get row count for a table"""
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    
    if is_postgres:
        count = cursor.fetchone()['count']
    else:
        count = cursor.fetchone()[0]
    
    cursor.close()
    return count

def migrate_table(sqlite_conn, postgres_conn, table_name):
    """Migrate data from one table"""
    logger.info(f"\n📦 Migrating table: {table_name}")
    
    # Get data from SQLite
    sqlite_cursor = sqlite_conn.cursor()
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()
    
    if not rows:
        logger.info(f"   ⚠️  No data to migrate (table is empty)")
        return 0
    
    # Get column names
    columns = [description[0] for description in sqlite_cursor.description]
    logger.info(f"   Columns: {', '.join(columns)}")
    logger.info(f"   Rows in SQLite: {len(rows)}")
    
    # Prepare INSERT statement for Postgres
    placeholders = ', '.join(['%s'] * len(columns))
    column_names = ', '.join(columns)
    insert_sql = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"
    
    # Insert data into Postgres
    postgres_cursor = postgres_conn.cursor()
    migrated = 0
    failed = 0
    
    for row in rows:
        try:
            # Convert sqlite3.Row to tuple
            values = tuple(row[col] for col in columns)
            postgres_cursor.execute(insert_sql, values)
            migrated += 1
        except Exception as e:
            failed += 1
            logger.info(f"   ❌ Failed to insert row: {e}")
            logger.info(f"      Data: {dict(row)}")
    
    postgres_conn.commit()
    postgres_cursor.close()
    sqlite_cursor.close()
    
    logger.info(f"   ✅ Migrated: {migrated} rows")
    if failed > 0:
        logger.info(f"   ⚠️  Failed: {failed} rows")
    
    return migrated

def reset_sequences(postgres_conn):
    """Reset Postgres sequences to match migrated data"""
    logger.info(f"\n🔄 Resetting auto-increment sequences...")
    
    cursor = postgres_conn.cursor()
    
    # Tables with SERIAL primary keys
    tables_with_serial = [
        ("users", "user_id"),
        ("custom_labels", "label_id"),
        ("scan_cursor", "cursor_id"),
        ("url_cache", "url_id"),
        ("retry_queue", "retry_id")
    ]
    
    for table, id_column in tables_with_serial:
        try:
            # Get max ID from table
            cursor.execute(f"SELECT MAX({id_column}) FROM {table}")
            result = cursor.fetchone()
            max_id = result['max'] if result['max'] is not None else 0
            
            # Reset sequence
            sequence_name = f"{table}_{id_column}_seq"
            cursor.execute(f"SELECT setval('{sequence_name}', {max_id}, true)")
            
            logger.info(f"   ✅ {table}.{id_column} sequence reset to {max_id}")
        except Exception as e:
            logger.info(f"   ⚠️  Failed to reset {table}.{id_column}: {e}")
    
    postgres_conn.commit()
    cursor.close()

def validate_migration(sqlite_conn, postgres_conn):
    """Validate that migration was successful"""
    logger.info(f"\n🔍 Validating migration...")
    
    all_valid = True
    
    for table in TABLES:
        sqlite_count = get_row_count(sqlite_conn, table, is_postgres=False)
        postgres_count = get_row_count(postgres_conn, table, is_postgres=True)
        
        if sqlite_count == postgres_count:
            logger.info(f"   ✅ {table}: {postgres_count} rows (matches SQLite)")
        else:
            logger.info(f"   ❌ {table}: SQLite={sqlite_count}, Postgres={postgres_count} (MISMATCH)")
            all_valid = False
    
    return all_valid

def main():
    """Main migration process"""
    logger.info("=" * 60)
    logger.info("Gmail Intelligence Manager - Data Migration")
    logger.info("SQLite → Postgres (Railway)")
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    try:
        # Connect to both databases
        sqlite_conn = connect_sqlite()
        postgres_conn = connect_postgres()
        
        # Show current state
        logger.info(f"\n📊 Pre-migration state:")
        total_rows = 0
        for table in TABLES:
            count = get_row_count(sqlite_conn, table, is_postgres=False)
            total_rows += count
            logger.info(f"   {table}: {count} rows")
        logger.info(f"   TOTAL: {total_rows} rows")
        
        # Confirm migration
        logger.info(f"\n⚠️  WARNING: This will insert {total_rows} rows into Postgres")
        logger.info(f"   Target database: {DATABASE_URL[:50]}...")
        response = input(f"\nProceed with migration? (yes/no): ")
        
        if response.lower() != 'yes':
            logger.info("\n❌ Migration cancelled by user")
            return
        
        # Migrate each table
        logger.info(f"\n🚀 Starting migration...")
        total_migrated = 0
        
        for table in TABLES:
            migrated = migrate_table(sqlite_conn, postgres_conn, table)
            total_migrated += migrated
        
        # Reset sequences
        reset_sequences(postgres_conn)
        
        # Validate migration
        if validate_migration(sqlite_conn, postgres_conn):
            logger.info(f"\n✅ Migration completed successfully!")
            logger.info(f"   Total rows migrated: {total_migrated}")
            logger.info(f"\n💡 Next steps:")
            logger.info(f"   1. Set DATABASE_URL in Railway environment variables")
            logger.info(f"   2. Deploy updated backend code to Railway")
            logger.info(f"   3. Test OAuth login and email analysis")
            logger.info(f"   4. Keep gmail_manager.db as backup (don't delete)")
        else:
            logger.info(f"\n⚠️  Migration completed with validation errors")
            logger.info(f"   Review the mismatches above and investigate")
        
        # Close connections
        sqlite_conn.close()
        postgres_conn.close()
        
        logger.info(f"\n✅ Database connections closed")
        logger.info(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.info(f"\n❌ Migration failed: {e}")
        logger.info(f"\n💡 Rollback instructions:")
        logger.info(f"   1. Connect to Railway Postgres via psql or pg_admin")
        logger.info(f"   2. Run: DROP TABLE IF EXISTS retry_queue, url_cache, analyzed_emails, scan_cursor, custom_labels, users CASCADE;")
        logger.info(f"   3. Re-run postgres_schema.sql to recreate tables")
        logger.info(f"   4. Re-run this migration script")
        return 1

if __name__ == "__main__":
    exit(main() or 0)
