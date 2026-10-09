"""
train_model_v2.py — Full Multi-Source Scam Classifier Training with Checkpointing
Gmail Manager Capstone Project

Retrains the model on ALL 10 datasets with incremental checkpointing to prevent
progress loss and includes held-out source validation for true generalization testing.
"""

import sys
import time
import warnings
import re
import json
from pathlib import Path
from datetime import datetime
from collections import Counter

import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, 
    confusion_matrix, classification_report
)

warnings.filterwarnings('ignore')

print("=" * 80)
print("SCAM CLASSIFIER V3: Full Multi-Source Training with All 10 Datasets")
print("=" * 80)
print()

# ============================================================================
# CONFIGURATION
# ============================================================================

DATASETS_DIR = Path(r"C:\Users\Administrator\Desktop\DATASETS")
CHECKPOINTS_DIR = Path(__file__).parent / "checkpoints"
CHECKPOINTS_DIR.mkdir(exist_ok=True)

# All dataset files (CSV and TXT)
DATASET_FILES = [
    'CEAS_08.csv',
    'email_phishing_data.csv',
    'Enron.csv',
    'Ling.csv',
    'meajor_cleaned_preprocessed.csv',
    'Nazario.csv',
    'Nigerian_Fraud.csv',
    'phishing_email.csv',
    'phishing_legit_dataset_KD_10000.csv',
    'SpamAssasin.csv',
    'fradulent_emails.txt',  # Now supported with custom parser
]

# ============================================================================
# STEP 1: PROCESS AND CHECKPOINT EACH FILE INDIVIDUALLY
# ============================================================================

print("\n" + "=" * 80)
print("STEP 1: Processing Individual Datasets with Checkpointing")
print("=" * 80 + "\n")

def clean_text(text):
    """Remove HTML tags and excessive whitespace."""
    if pd.isna(text):
        return ""
    text = str(text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def normalize_label(val):
    """Normalize diverse label values to 'phishing' or 'legitimate'."""
    val_str = str(val).lower().strip()
    
    # Phishing indicators
    if any(kw in val_str for kw in ['phish', 'spam', 'scam', 'fraud', 'malicious', '1', 'yes', 'true']):
        return 'phishing'
    # Legitimate indicators
    elif any(kw in val_str for kw in ['ham', 'legit', 'safe', 'normal', '0', 'no', 'false']):
        return 'legitimate'
    # Handle numeric labels (0.0 = legitimate, 1.0 = phishing)
    elif val_str in ['0.0', '0']:
        return 'legitimate'
    elif val_str in ['1.0', '1']:
        return 'phishing'
    else:
        return None


def process_txt_dataset(filename):
    """
    Process .txt files in mbox format (e.g., fradulent_emails.txt).
    Parses raw MIME email format and extracts sender, subject, body.
    
    Returns: DataFrame or None if failed.
    """
    checkpoint_file = CHECKPOINTS_DIR / f"normalized_{filename.replace('.txt', '.parquet')}"
    
    # Check if checkpoint already exists
    if checkpoint_file.exists():
        print(f"[OK] Loading existing checkpoint: {filename}")
        try:
            df = pd.read_parquet(checkpoint_file)
            if 'source' not in df.columns:
                df['source'] = filename.replace('.txt', '')
            print(f"  Rows: {len(df):,} | Phishing: {(df['label']=='phishing').sum():,} | Legitimate: {(df['label']=='legitimate').sum():,}")
            return df
        except Exception as e:
            print(f"  [WARN]  Checkpoint corrupted, reprocessing: {e}")
    
    print(f"📄 Processing: {filename}")
    print("-" * 80)
    
    filepath = DATASETS_DIR / filename
    if not filepath.exists():
        print(f"  [WARN]  File not found, skipping")
        return None
    
    start_time = time.time()
    
    try:
        # Read entire file
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        print(f"  Loaded file ({len(content):,} chars)")
        
        # Split into individual emails (mbox format: emails start with "From ")
        # Use regex to split while keeping the delimiter
        email_blocks = re.split(r'\n(?=From )', content)
        email_blocks = [block.strip() for block in email_blocks if block.strip()]
        
        print(f"  Found {len(email_blocks)} email blocks")
        
        emails = []
        failed = 0
        
        for block in email_blocks:
            try:
                # Extract headers and body
                lines = block.split('\n')
                
                sender = None
                subject = None
                body_start_idx = 0
                
                # Parse headers
                for i, line in enumerate(lines):
                    # Empty line marks end of headers
                    if line.strip() == '':
                        body_start_idx = i + 1
                        break
                    
                    # Extract From header
                    if line.startswith('From:') or line.startswith('FROM:'):
                        sender = line.split(':', 1)[1].strip()
                    # Extract Subject header
                    elif line.startswith('Subject:') or line.startswith('SUBJECT:'):
                        subject = line.split(':', 1)[1].strip()
                
                # Extract body (everything after headers)
                body_lines = lines[body_start_idx:]
                body = '\n'.join(body_lines).strip()
                
                # Only include if we have body text
                if len(body) > 10:
                    emails.append({
                        'sender': sender if sender else 'unknown',
                        'subject': subject if subject else '',
                        'body': body
                    })
                else:
                    failed += 1
                    
            except Exception as e:
                failed += 1
                continue
        
        print(f"  Successfully parsed {len(emails)} emails ({failed} failed)")
        
        if len(emails) == 0:
            print(f"  [ERROR] No valid emails parsed, skipping")
            return None
        
        # Create DataFrame
        df = pd.DataFrame(emails)
        
        # Build normalized DataFrame
        source_name = filename.replace('.txt', '')
        normalized = pd.DataFrame()
        normalized['source'] = [source_name] * len(df)
        
        # Combine subject + body
        normalized['body'] = (
            df['subject'].fillna('').astype(str) + ' ' + 
            df['body'].fillna('').astype(str)
        )
        
        # Clean text
        normalized['body'] = normalized['body'].apply(clean_text)
        
        # Add sender
        normalized['sender'] = df['sender'].fillna('unknown').astype(str)
        
        # Label ALL as phishing (this is the fraudulent email corpus)
        normalized['label'] = 'phishing'
        
        # Drop rows with empty body
        normalized = normalized[normalized['body'].str.len() > 10]
        
        if len(normalized) == 0:
            print(f"  [ERROR] No valid rows after cleaning, skipping")
            return None
        
        # Report stats
        elapsed = time.time() - start_time
        phishing_count = (normalized['label'] == 'phishing').sum()
        legit_count = (normalized['label'] == 'legitimate').sum()
        
        print(f"  [OK] Processed in {elapsed:.1f}s")
        print(f"  Valid rows: {len(normalized):,}")
        print(f"  Phishing: {phishing_count:,} (100.0%)")
        print(f"  Legitimate: {legit_count:,} (0.0%)")
        
        # Save checkpoint
        normalized.to_parquet(checkpoint_file, index=False)
        print(f"  [OK] Checkpoint saved: {checkpoint_file.name}")
        
        return normalized
        
    except Exception as e:
        print(f"  [ERROR] Error processing file: {e}")
        import traceback
        traceback.print_exc()
        return None


def normalize_label(val):
    """Normalize diverse label values to 'phishing' or 'legitimate'."""
    val_str = str(val).lower().strip()
    
    # Phishing indicators
    if any(kw in val_str for kw in ['phish', 'spam', 'scam', 'fraud', 'malicious', '1', 'yes', 'true']):
        return 'phishing'
    # Legitimate indicators
    elif any(kw in val_str for kw in ['ham', 'legit', 'safe', 'normal', '0', 'no', 'false']):
        return 'legitimate'
    else:
        return None


def process_dataset(filename):
    """
    Process a single dataset file and save normalized checkpoint.
    Returns: DataFrame or None if failed.
    """
    checkpoint_file = CHECKPOINTS_DIR / f"normalized_{filename.replace('.csv', '.parquet')}"
    
    # Check if checkpoint already exists
    if checkpoint_file.exists():
        print(f"[OK] Loading existing checkpoint: {filename}")
        try:
            df = pd.read_parquet(checkpoint_file)
            # Ensure source column exists
            if 'source' not in df.columns:
                df['source'] = filename.replace('.csv', '')
            print(f"  Rows: {len(df):,} | Phishing: {(df['label']=='phishing').sum():,} | Legitimate: {(df['label']=='legitimate').sum():,}")
            return df
        except Exception as e:
            print(f"  [WARN]  Checkpoint corrupted, reprocessing: {e}")
    
    print(f"📄 Processing: {filename}")
    print("-" * 80)
    
    filepath = DATASETS_DIR / filename
    if not filepath.exists():
        print(f"  [WARN]  File not found, skipping")
        return None
    
    start_time = time.time()
    
    try:
        # Load CSV with different encodings
        try:
            df = pd.read_csv(filepath, encoding='utf-8', low_memory=False)
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding='latin-1', low_memory=False)
        
        print(f"  Loaded {len(df):,} rows")
        print(f"  Columns: {list(df.columns)[:10]}")
        
        # === Auto-detect body/text column ===
        body_col = None
        
        # PRIORITY 1: Exact column name match for 'body' (fixes meajor_cleaned_preprocessed.csv)
        if 'body' in df.columns:
            body_col = 'body'
        # PRIORITY 2: Fuzzy keyword matching
        elif body_col is None:
            for col in df.columns:
                col_lower = col.lower()
                if any(keyword in col_lower for keyword in ['text', 'message', 'email', 'content']):
                    body_col = col
                    break
        
        # PRIORITY 3: Try first text column as fallback
        if body_col is None:
            text_cols = df.select_dtypes(include=['object']).columns
            if len(text_cols) > 0:
                body_col = text_cols[0]
        
        if body_col is None:
            print(f"  [ERROR] No text/body column found, skipping")
            return None
        
        print(f"  Body column: '{body_col}'")
        
        # === Auto-detect subject column (optional) ===
        subject_col = None
        # PRIORITY 1: Exact match for 'subject'
        if 'subject' in df.columns:
            subject_col = 'subject'
        # PRIORITY 2: Fuzzy match
        elif subject_col is None:
            for col in df.columns:
                if 'subject' in col.lower():
                    subject_col = col
                    break
        
        if subject_col:
            print(f"  Subject column: '{subject_col}'")
        
        # === Auto-detect sender column (optional) ===
        sender_col = None
        # PRIORITY 1: Exact match for 'sender'
        if 'sender' in df.columns:
            sender_col = 'sender'
        # PRIORITY 2: Fuzzy match
        elif sender_col is None:
            for col in df.columns:
                col_lower = col.lower()
                if any(keyword in col_lower for keyword in ['from', 'email_from']):
                    sender_col = col
                    break
        
        if sender_col:
            print(f"  Sender column: '{sender_col}'")
        
        # === Auto-detect label column ===
        label_col = None
        # PRIORITY 1: Exact match for 'label'
        if 'label' in df.columns:
            label_col = 'label'
        # PRIORITY 2: Fuzzy match
        elif label_col is None:
            for col in df.columns:
                col_lower = col.lower()
                if any(keyword in col_lower for keyword in ['class', 'type', 'category', 'target', 'spam']):
                    # Skip columns that are clearly NOT labels
                    if 'content' in col_lower or 'attachment' in col_lower or 'url' in col_lower:
                        continue
                    label_col = col
                    break
        
        if label_col is None:
            print(f"  [ERROR] No label column found, skipping")
            return None
        
        print(f"  Label column: '{label_col}'")
        
        # === Build normalized DataFrame ===
        source_name = filename.replace('.csv', '')
        normalized = pd.DataFrame()
        normalized['source'] = [source_name] * len(df)
        
        # Combine subject + body if both exist
        if subject_col and subject_col in df.columns:
            normalized['body'] = (
                df[subject_col].fillna('').astype(str) + ' ' + 
                df[body_col].fillna('').astype(str)
            )
        else:
            normalized['body'] = df[body_col].fillna('').astype(str)
        
        # Clean text
        normalized['body'] = normalized['body'].apply(clean_text)
        
        # Add sender if available
        if sender_col and sender_col in df.columns:
            normalized['sender'] = df[sender_col].fillna('unknown').astype(str)
        else:
            normalized['sender'] = 'unknown'
        
        # Normalize labels
        normalized['label'] = df[label_col].apply(normalize_label)
        
        # Drop rows with no label or empty body
        normalized = normalized[normalized['label'].notna()]
        normalized = normalized[normalized['body'].str.len() > 10]
        
        if len(normalized) == 0:
            print(f"  [ERROR] No valid rows after cleaning, skipping")
            return None
        
        # Report stats
        elapsed = time.time() - start_time
        phishing_count = (normalized['label'] == 'phishing').sum()
        legit_count = (normalized['label'] == 'legitimate').sum()
        
        print(f"  [OK] Processed in {elapsed:.1f}s")
        print(f"  Valid rows: {len(normalized):,}")
        print(f"  Phishing: {phishing_count:,} ({phishing_count/len(normalized)*100:.1f}%)")
        print(f"  Legitimate: {legit_count:,} ({legit_count/len(normalized)*100:.1f}%)")
        
        # Save checkpoint
        normalized.to_parquet(checkpoint_file, index=False)
        print(f"  [OK] Checkpoint saved: {checkpoint_file.name}")
        
        return normalized
        
    except Exception as e:
        print(f"  [ERROR] Error processing file: {e}")
        import traceback
        traceback.print_exc()
        return None


# Process all datasets
all_dataframes = []
dataset_stats = {}

for filename in DATASET_FILES:
    # Route to appropriate processor based on file extension
    if filename.endswith('.txt'):
        df = process_txt_dataset(filename)
    else:
        df = process_dataset(filename)
    
    if df is not None:
        all_dataframes.append(df)
        dataset_stats[filename] = {
            'rows': len(df),
            'phishing': int((df['label'] == 'phishing').sum()),
            'legitimate': int((df['label'] == 'legitimate').sum())
        }
    print()

if len(all_dataframes) == 0:
    print("\n[ERROR] ERROR: No datasets successfully processed. Exiting.")
    sys.exit(1)

print(f"\n[OK] Successfully processed {len(all_dataframes)} datasets")

# ============================================================================
# STEP 2: MERGE ALL CHECKPOINTS
# ============================================================================

print("\n" + "=" * 80)
print("STEP 2: Merging All Checkpoints")
print("=" * 80 + "\n")

print("Concatenating all datasets...")
merged = pd.concat(all_dataframes, ignore_index=True)
print(f"  Total rows before deduplication: {len(merged):,}")

# Drop exact duplicate bodies (many datasets overlap)
print("\nRemoving duplicate email bodies across sources...")
before_dedup = len(merged)
merged = merged.drop_duplicates(subset=['body'], keep='first')
after_dedup = len(merged)
duplicates_removed = before_dedup - after_dedup

print(f"  Duplicates removed: {duplicates_removed:,} ({duplicates_removed/before_dedup*100:.1f}%)")
print(f"  Final dataset size: {after_dedup:,}")

# Class balance
phishing_total = (merged['label'] == 'phishing').sum()
legit_total = (merged['label'] == 'legitimate').sum()
phishing_pct = phishing_total / len(merged) * 100
legit_pct = legit_total / len(merged) * 100

print(f"\nFinal class balance:")
print(f"  Phishing: {phishing_total:,} ({phishing_pct:.1f}%)")
print(f"  Legitimate: {legit_total:,} ({legit_pct:.1f}%)")

# ============================================================================
# STEP 3: BALANCE CLASSES IF NEEDED
# ============================================================================

print("\n" + "=" * 80)
print("STEP 3: Class Balance Strategy")
print("=" * 80 + "\n")

# Check if ratio is beyond 60/40
ratio = min(phishing_pct, legit_pct) / max(phishing_pct, legit_pct)

if ratio < 0.67:  # Less than 60/40
    print(f"Class imbalance detected (ratio: {ratio:.2f})")
    print("Using class_weight='balanced' in model training to handle imbalance")
    use_class_weight = True
else:
    print(f"Classes are reasonably balanced (ratio: {ratio:.2f})")
    print("No resampling needed")
    use_class_weight = False

# ============================================================================
# STEP 4: FEATURE ENGINEERING
# ============================================================================

print("\n" + "=" * 80)
print("STEP 4: Feature Engineering")
print("=" * 80 + "\n")

print("Extracting engineered features from email text...")

# Feature columns (defined here since Step 4 needs this list before Step 6 does)
feature_cols = [
    'num_urls', 'has_ip_url', 'num_exclamations', 'contains_urgent_words',
    'body_length', 'uppercase_ratio', 'writing_style_score'
]

def extract_features(row):
    """Extract all engineered features from email."""
    body = str(row['body'])
    sender = str(row['sender'])
    
    features = {}
    
    # Count URLs
    features['num_urls'] = len(re.findall(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
        body
    ))
    
    # Check if any URL uses raw IP address
    ip_pattern = r'http[s]?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
    features['has_ip_url'] = 1 if re.search(ip_pattern, body) else 0
    
    # Count exclamation marks
    features['num_exclamations'] = body.count('!')
    
    # Check for urgent/scam keywords
    urgent_words = [
        'urgent', 'verify', 'account', 'suspended', 'click here', 'act now',
        'limited time', 'expire', 'confirm', 'update', 'security', 'alert',
        'winner', 'congratulations', 'prize', 'claim', 'free', 'offer',
        'password', 'credit card', 'ssn', 'social security'
    ]
    body_lower = body.lower()
    features['contains_urgent_words'] = 1 if any(word in body_lower for word in urgent_words) else 0
    
    # Body length
    features['body_length'] = len(body)
    
    # Uppercase ratio
    if len(body) > 0:
        uppercase_count = sum(1 for c in body if c.isupper())
        features['uppercase_ratio'] = uppercase_count / len(body)
    else:
        features['uppercase_ratio'] = 0.0
    
    # NEW FEATURE: Writing style score
    # Combines sentence length variance and formality markers
    sentences = re.split(r'[.!?]+', body)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 0]
    
    if len(sentences) > 1:
        sentence_lengths = [len(s.split()) for s in sentences]
        # Higher variance suggests more natural, varied writing (less templated)
        style_variance = np.std(sentence_lengths) if len(sentence_lengths) > 1 else 0.0
    else:
        style_variance = 0.0
    
    # Formality markers (formal greetings, closings)
    formality_markers = ['dear', 'sincerely', 'regards', 'respectfully', 'yours truly']
    formality_count = sum(1 for marker in formality_markers if marker in body_lower)
    
    # Combine: high variance + formality = Nigerian 419 style prose
    # Low variance + urgency = templated corporate phishing
    # Ensure no NaN values
    features['writing_style_score'] = float(style_variance) + (formality_count * 2.0)
    
    return features


def extract_features_vectorized(body_series):
    """
    Vectorized feature extraction for entire DataFrame column.
    Processes all rows at once using pandas/numpy operations.
    
    Args:
        body_series: pandas Series containing email body text
    
    Returns:
        DataFrame with all feature columns
    """
    print(f"  Extracting features from {len(body_series):,} emails (vectorized)...")
    
    # URL pattern
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    ip_pattern = r'http[s]?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
    
    features = pd.DataFrame(index=body_series.index)
    
    # 1. Count URLs (vectorized)
    features['num_urls'] = body_series.str.findall(url_pattern).str.len().fillna(0).astype(int)
    
    # 2. Has IP URL (vectorized)
    features['has_ip_url'] = body_series.str.contains(ip_pattern, regex=True, na=False).astype(int)
    
    # 3. Count exclamation marks (vectorized)
    features['num_exclamations'] = body_series.str.count('!', flags=0).fillna(0).astype(int)
    
    # 4. Contains urgent words (vectorized with combined regex)
    urgent_words = [
        'urgent', 'verify', 'account', 'suspended', 'click here', 'act now',
        'limited time', 'expire', 'confirm', 'update', 'security', 'alert',
        'winner', 'congratulations', 'prize', 'claim', 'free', 'offer',
        'password', 'credit card', 'ssn', 'social security'
    ]
    # Escape special regex chars and create combined pattern
    urgent_pattern = '|'.join(re.escape(word) for word in urgent_words)
    features['contains_urgent_words'] = body_series.str.lower().str.contains(
        urgent_pattern, regex=True, na=False
    ).astype(int)
    
    # 5. Body length (vectorized)
    features['body_length'] = body_series.str.len().fillna(0).astype(int)
    
    # 6. Uppercase ratio (vectorized)
    # Count uppercase letters using regex
    uppercase_counts = body_series.str.count(r'[A-Z]').fillna(0)
    features['uppercase_ratio'] = (uppercase_counts / features['body_length']).fillna(0.0)
    
    # 7. Writing style score (optimized with apply - complex to fully vectorize)
    # This is the only feature using apply() due to sentence-level variance calculation
    def compute_style_score(text):
        """Compute writing style score for a single text."""
        if pd.isna(text) or len(text) == 0:
            return 0.0
        
        text_lower = text.lower()
        
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 0]
        
        # Calculate variance
        if len(sentences) > 1:
            sentence_lengths = [len(s.split()) for s in sentences]
            style_variance = np.std(sentence_lengths) if len(sentence_lengths) > 1 else 0.0
        else:
            style_variance = 0.0
        
        # Count formality markers
        formality_markers = ['dear', 'sincerely', 'regards', 'respectfully', 'yours truly']
        formality_count = sum(1 for marker in formality_markers if marker in text_lower)
        
        return float(style_variance) + (formality_count * 2.0)
    
    features['writing_style_score'] = body_series.apply(compute_style_score)
    
    return features


def extract_features_old(row):
    """
    OLD row-by-row feature extraction (kept for benchmarking).
    This is the slow iterrows() version.
    """
    body = str(row['body'])
    
    features = {}
    
    # Count URLs
    features['num_urls'] = len(re.findall(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
        body
    ))
    
    # Check if any URL uses raw IP address
    ip_pattern = r'http[s]?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
    features['has_ip_url'] = 1 if re.search(ip_pattern, body) else 0
    
    # Count exclamation marks
    features['num_exclamations'] = body.count('!')
    
    # Check for urgent/scam keywords
    urgent_words = [
        'urgent', 'verify', 'account', 'suspended', 'click here', 'act now',
        'limited time', 'expire', 'confirm', 'update', 'security', 'alert',
        'winner', 'congratulations', 'prize', 'claim', 'free', 'offer',
        'password', 'credit card', 'ssn', 'social security'
    ]
    body_lower = body.lower()
    features['contains_urgent_words'] = 1 if any(word in body_lower for word in urgent_words) else 0
    
    # Body length
    features['body_length'] = len(body)
    
    # Uppercase ratio
    if len(body) > 0:
        uppercase_count = sum(1 for c in body if c.isupper())
        features['uppercase_ratio'] = uppercase_count / len(body)
    else:
        features['uppercase_ratio'] = 0.0
    
    # NEW FEATURE: Writing style score
    sentences = re.split(r'[.!?]+', body)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 0]
    
    if len(sentences) > 1:
        sentence_lengths = [len(s.split()) for s in sentences]
        style_variance = np.std(sentence_lengths) if len(sentence_lengths) > 1 else 0.0
    else:
        style_variance = 0.0
    
    formality_markers = ['dear', 'sincerely', 'regards', 'respectfully', 'yours truly']
    formality_count = sum(1 for marker in formality_markers if marker in body_lower)
    
    features['writing_style_score'] = float(style_variance) + (formality_count * 2.0)
    
    return features


# Apply feature extraction (VECTORIZED)
print("Processing features (vectorized - much faster)...")
start_time = time.time()

# Use vectorized feature extraction
features_df = extract_features_vectorized(merged['body'])

# Add features to merged dataset
for col in features_df.columns:
    merged[col] = features_df[col]

# CRITICAL: Check for and remove any NaN values
print("\nChecking for NaN values in features...")
nan_counts = merged[feature_cols].isna().sum()
if nan_counts.sum() > 0:
    print(f"  [WARN]  Found NaN values:")
    for col in nan_counts[nan_counts > 0].index:
        print(f"    {col}: {nan_counts[col]} NaNs")
    print(f"  Filling NaN values with 0.0...")
    merged[feature_cols] = merged[feature_cols].fillna(0.0)
    print(f"  [OK] NaN values filled")
else:
    print(f"  [OK] No NaN values found")

elapsed = time.time() - start_time
print(f"[OK] Feature extraction complete in {elapsed:.1f}s")
print(f"  Features extracted: {list(features_df.columns)}")

# ============================================================================
# STEP 5: TRAIN/TEST SPLIT WITH HELD-OUT SOURCE
# ============================================================================

print("\n" + "=" * 80)
print("STEP 5: Train/Test Split with Held-Out Source Validation")
print("=" * 80 + "\n")

# Find the smallest source to hold out
source_sizes = merged['source'].value_counts()
print("Dataset sizes by source:")
for source, count in source_sizes.items():
    print(f"  {source}: {count:,} rows")

# Hold out the smallest source for true OOD testing
held_out_source = source_sizes.idxmin()
print(f"\nHolding out '{held_out_source}' as out-of-distribution test set")

# Split into training pool and held-out source
held_out_df = merged[merged['source'] == held_out_source].copy()
training_pool = merged[merged['source'] != held_out_source].copy()

print(f"\nTraining pool: {len(training_pool):,} rows")
print(f"Held-out source: {len(held_out_df):,} rows")

# 80/20 stratified split on training pool
X_train, X_test, y_train, y_test = train_test_split(
    training_pool,
    training_pool['label'],
    test_size=0.2,
    random_state=42,
    stratify=training_pool['label']
)

# Held-out source split
X_held_out = held_out_df
y_held_out = held_out_df['label']

print(f"\nFinal splits:")
print(f"  Training: {len(X_train):,} rows")
print(f"  Test (random): {len(X_test):,} rows")
print(f"  Held-out source: {len(X_held_out):,} rows ({held_out_source})")

# ============================================================================
# STEP 6: TRAIN MODELS
# ============================================================================

print("\n" + "=" * 80)
print("STEP 6: Training Models")
print("=" * 80 + "\n")

# (feature_cols was already defined in Step 4, reused here)

def train_and_evaluate(model, model_name, X_train, y_train, X_test, y_test, X_held_out, y_held_out):
    """Train a model and evaluate on both test sets."""
    print(f"\n{'='*80}")
    print(f"Training: {model_name}")
    print(f"{'='*80}\n")
    
    # Build pipeline
    preprocessor = ColumnTransformer(
        transformers=[
            ('text', TfidfVectorizer(max_features=5000, ngram_range=(1, 2)), 'body'),
            ('numeric', StandardScaler(), feature_cols)
        ]
    )
    
    pipeline = Pipeline([
        ('preprocessor', preprocessor),
        ('classifier', model)
    ])
    
    # Train
    print("Training...")
    start_time = time.time()
    pipeline.fit(X_train, y_train)
    train_time = time.time() - start_time
    print(f"[OK] Training complete in {train_time:.1f}s")
    
    # Evaluate on normal test set
    print(f"\n--- Performance on Random Test Split ---")
    y_pred_test = pipeline.predict(X_test)
    
    acc_test = accuracy_score(y_test, y_pred_test)
    prec_test = precision_score(y_test, y_pred_test, pos_label='phishing')
    rec_test = recall_score(y_test, y_pred_test, pos_label='phishing')
    f1_test = f1_score(y_test, y_pred_test, pos_label='phishing')
    cm_test = confusion_matrix(y_test, y_pred_test, labels=['legitimate', 'phishing'])
    
    print(f"Accuracy:  {acc_test:.4f} ({acc_test*100:.2f}%)")
    print(f"Precision: {prec_test:.4f} ({prec_test*100:.2f}%)")
    print(f"Recall:    {rec_test:.4f} ({rec_test*100:.2f}%)")
    print(f"F1-Score:  {f1_test:.4f} ({f1_test*100:.2f}%)")
    print(f"\nConfusion Matrix:")
    print(f"                Predicted")
    print(f"            Legitimate  Phishing")
    print(f"Legitimate    {cm_test[0,0]:4d}      {cm_test[0,1]:4d}")
    print(f"Phishing      {cm_test[1,0]:4d}      {cm_test[1,1]:4d}")
    
    # Evaluate on held-out source
    print(f"\n--- Performance on Held-Out Source ({held_out_source}) ---")
    y_pred_held = pipeline.predict(X_held_out)
    
    acc_held = accuracy_score(y_held_out, y_pred_held)
    prec_held = precision_score(y_held_out, y_pred_held, pos_label='phishing', zero_division=0)
    rec_held = recall_score(y_held_out, y_pred_held, pos_label='phishing', zero_division=0)
    f1_held = f1_score(y_held_out, y_pred_held, pos_label='phishing', zero_division=0)
    cm_held = confusion_matrix(y_held_out, y_pred_held, labels=['legitimate', 'phishing'])
    
    print(f"Accuracy:  {acc_held:.4f} ({acc_held*100:.2f}%)")
    print(f"Precision: {prec_held:.4f} ({prec_held*100:.2f}%)")
    print(f"Recall:    {rec_held:.4f} ({rec_held*100:.2f}%)")
    print(f"F1-Score:  {f1_held:.4f} ({f1_held*100:.2f}%)")
    print(f"\nConfusion Matrix:")
    print(f"                Predicted")
    print(f"            Legitimate  Phishing")
    print(f"Legitimate    {cm_held[0,0]:4d}      {cm_held[0,1]:4d}")
    print(f"Phishing      {cm_held[1,0]:4d}      {cm_held[1,1]:4d}")
    
    return {
        'pipeline': pipeline,
        'test_accuracy': acc_test,
        'test_precision': prec_test,
        'test_recall': rec_test,
        'test_f1': f1_test,
        'test_confusion_matrix': cm_test.tolist(),
        'held_out_accuracy': acc_held,
        'held_out_precision': prec_held,
        'held_out_recall': rec_held,
        'held_out_f1': f1_held,
        'held_out_confusion_matrix': cm_held.tolist(),
        'train_time': train_time
    }

# Model 1: Logistic Regression
lr_params = {'max_iter': 1000, 'random_state': 42}
if use_class_weight:
    lr_params['class_weight'] = 'balanced'

lr_results = train_and_evaluate(
    LogisticRegression(**lr_params),
    "Logistic Regression",
    X_train, y_train, X_test, y_test, X_held_out, y_held_out
)

# Model 2: Random Forest
rf_params = {'n_estimators': 100, 'max_depth': 20, 'random_state': 42, 'n_jobs': -1}
if use_class_weight:
    rf_params['class_weight'] = 'balanced'

rf_results = train_and_evaluate(
    RandomForestClassifier(**rf_params),
    "Random Forest",
    X_train, y_train, X_test, y_test, X_held_out, y_held_out
)

# ============================================================================
# STEP 7: EXPORT BEST MODEL
# ============================================================================

print("\n" + "=" * 80)
print("STEP 7: Exporting Best Model")
print("=" * 80 + "\n")

# Choose best model based on held-out F1 (true generalization metric)
if lr_results['held_out_f1'] >= rf_results['held_out_f1']:
    best_model = lr_results['pipeline']
    best_name = "Logistic Regression"
    best_metrics = lr_results
else:
    best_model = rf_results['pipeline']
    best_name = "Random Forest"
    best_metrics = rf_results

print(f"Best model: {best_name}")
print(f"  Held-out F1: {best_metrics['held_out_f1']:.4f}")

# Save model
model_path = Path(__file__).parent / 'scam_classifier_v3.pkl'
joblib.dump(best_model, model_path)
print(f"\n[OK] Model saved: {model_path}")

# Save metadata
metadata = {
    'model_version': 'v3',
    'model_type': best_name,
    'training_date': datetime.now().isoformat(),
    'datasets': dataset_stats,
    'total_training_samples': len(training_pool),
    'total_samples_after_dedup': len(merged),
    'duplicates_removed': duplicates_removed,
    'class_balance': {
        'phishing': int(phishing_total),
        'legitimate': int(legit_total),
        'phishing_percentage': round(phishing_pct, 2),
        'used_class_weight': use_class_weight
    },
    'held_out_source': held_out_source,
    'held_out_samples': len(held_out_df),
    'features': feature_cols + ['body (TF-IDF)'],
    'performance': {
        'random_test_split': {
            'samples': len(X_test),
            'accuracy': round(best_metrics['test_accuracy'], 4),
            'precision': round(best_metrics['test_precision'], 4),
            'recall': round(best_metrics['test_recall'], 4),
            'f1_score': round(best_metrics['test_f1'], 4),
            'confusion_matrix': best_metrics['test_confusion_matrix']
        },
        'held_out_source': {
            'source': held_out_source,
            'samples': len(X_held_out),
            'accuracy': round(best_metrics['held_out_accuracy'], 4),
            'precision': round(best_metrics['held_out_precision'], 4),
            'recall': round(best_metrics['held_out_recall'], 4),
            'f1_score': round(best_metrics['held_out_f1'], 4),
            'confusion_matrix': best_metrics['held_out_confusion_matrix']
        }
    },
    'training_time_seconds': round(best_metrics['train_time'], 2),
    'improvements_over_v2': {
        'note': 'V3 adds meajor_cleaned_preprocessed.csv (108K rows) + fradulent_emails.txt (4K rows)',
        'v2_samples': 96427,
        'v3_samples': len(training_pool),
        'v2_held_out_f1': 0.9158,
        'v3_held_out_f1': round(best_metrics['held_out_f1'], 4)
    }
}

metadata_path = Path(__file__).parent / 'model_metadata_v3.json'
with open(metadata_path, 'w') as f:
    json.dump(metadata, f, indent=2)

print(f"[OK] Metadata saved: {metadata_path}")

# ============================================================================
# STEP 8: FINAL HONEST VERDICT
# ============================================================================

print("\n\n" + "=" * 80)
print("STEP 8: FINAL VERDICT — V1 → V2 → V3 Comparison")
print("=" * 80 + "\n")

v1_cross_source_f1 = 0.2499  # From initial validation
v2_held_out_f1 = 0.9158  # From V2 training
v3_held_out_f1 = best_metrics['held_out_f1']

print("COMPARISON: V1 → V2 → V3")
print("-" * 80)
print(f"V1 (CEAS_08 only, 5K):          Cross-source F1 = {v1_cross_source_f1:.2%}")
print(f"V2 (8 datasets, 96K):           Held-out F1 =     {v2_held_out_f1:.2%}")
print(f"V3 (10 datasets, {len(training_pool)//1000}K):          Held-out F1 =     {v3_held_out_f1:.2%}")
print()
print(f"V1 → V2 improvement: {v2_held_out_f1 - v1_cross_source_f1:+.2%}")
print(f"V2 → V3 improvement: {v3_held_out_f1 - v2_held_out_f1:+.2%}")
print()

# Detailed comparison table
print("DETAILED V3 PERFORMANCE:")
print("-" * 80)
print(f"{'Metric':<25} {'Random Test':<15} {'Held-Out Source':<15}")
print("-" * 80)
print(f"{'Accuracy':<25} {best_metrics['test_accuracy']:<15.2%} {best_metrics['held_out_accuracy']:<15.2%}")
print(f"{'Precision':<25} {best_metrics['test_precision']:<15.2%} {best_metrics['held_out_precision']:<15.2%}")
print(f"{'Recall':<25} {best_metrics['test_recall']:<15.2%} {best_metrics['held_out_recall']:<15.2%}")
print(f"{'F1-Score':<25} {best_metrics['test_f1']:<15.2%} {best_metrics['held_out_f1']:<15.2%}")
print("-" * 80)

# Honest verdict
print("\n\nHONEST VERDICT:")
print("=" * 80)

improvement_v2_v3 = v3_held_out_f1 - v2_held_out_f1

if improvement_v2_v3 >= 0.03:
    print("\n[OK][OK] SIGNIFICANT IMPROVEMENT: V3 meaningfully better than V2")
    print(f"\nAdding meajor_cleaned_preprocessed ({dataset_stats.get('meajor_cleaned_preprocessed.csv', {}).get('rows', 0):,} rows)")
    print(f"and fradulent_emails ({dataset_stats.get('fradulent_emails.txt', {}).get('rows', 0):,} rows) improved held-out F1")
    print(f"from {v2_held_out_f1:.2%} to {v3_held_out_f1:.2%} ({improvement_v2_v3:+.2%}).")
    print(f"\nThe additional diversity from 2x more training data helped the model")
    print(f"generalize better to unseen email styles.")
    print(f"\n[OK] V3 is the new production model - replace V2 in FastAPI backend")
    
elif improvement_v2_v3 >= 0.01:
    print("\n[OK] MODEST IMPROVEMENT: V3 slightly better than V2")
    print(f"\nAdding ~112K more emails improved held-out F1 from {v2_held_out_f1:.2%}")
    print(f"to {v3_held_out_f1:.2%} ({improvement_v2_v3:+.2%}).")
    print(f"\nThe improvement is real but small - V2 had already captured most")
    print(f"of the learnable patterns. The extra data adds marginal value.")
    print(f"\n[OK] Can deploy V3, but V2 (91.58%) was already excellent")
    
elif improvement_v2_v3 >= -0.01:
    print("\n[!] NO SIGNIFICANT CHANGE: V3 ≈ V2")
    print(f"\nAdding ~112K more emails changed held-out F1 by only {improvement_v2_v3:+.2%}")
    print(f"({v2_held_out_f1:.2%} → {v3_held_out_f1:.2%}).")
    print(f"\nThis suggests V2 had already learned the generalizable patterns,")
    print(f"and more data didn't add new signal. Diminishing returns kicked in.")
    print(f"\n[!] Either model is production-ready - V2 is simpler (fewer sources)")
    
else:
    print("\n[WARN]  SLIGHT REGRESSION: V3 performed worse than V2")
    print(f"\nHeld-out F1 dropped from {v2_held_out_f1:.2%} to {v3_held_out_f1:.2%}")
    print(f"({improvement_v2_v3:.2%}).")
    print(f"\nPossible causes:")
    print(f"  • New data introduced noise or contradictory patterns")
    print(f"  • Held-out source happened to be more similar to V2's training set")
    print(f"  • Random variation (test on different held-out source)")
    print(f"\n[!] Stick with V2 (91.58%) unless further testing shows V3 is better")

print("\n\n" + "=" * 80)
print("[OK] TRAINING COMPLETE")
print("=" * 80)
print(f"\nFiles created:")
print(f"  • scam_classifier_v2.pkl")
print(f"  • model_metadata_v2.json")
print(f"  • {len(all_dataframes)} checkpoint files in checkpoints/")
print(f"\nTotal samples trained on: {len(training_pool):,}")
print(f"Training time: {best_metrics['train_time']:.1f}s")
print(f"Final V2 held-out F1: {v2_held_out_f1:.2%}")