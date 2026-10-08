"""
predict.py — ML Inference Module for Scam/Phishing Email Detection
Gmail Manager Capstone Project

Provides a fast, standalone prediction function that loads the trained model
and classifies emails as phishing or legitimate.
"""

import re
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict

# Global model cache
_model = None
_model_path = Path(__file__).parent / 'scam_classifier_v2.pkl'

def load_model():
    """Load the trained model (cached after first load)."""
    global _model
    if _model is None:
        if not _model_path.exists():
            raise FileNotFoundError(
                f"Model file not found: {_model_path}\n"
                "Please run train_model.py first to generate scam_classifier.pkl"
            )
        _model = joblib.load(_model_path)
    return _model


def extract_features(subject: str, body: str, sender: str = None) -> Dict:
    """
    Extract engineered features from email components.
    
    Args:
        subject: Email subject line
        body: Email body text
        sender: Sender email address (optional)
    
    Returns:
        Dictionary of feature values
    """
    # Combine subject and body for full text analysis
    full_text = f"{subject} {body}"
    
    features = {}
    
    # Count URLs
    features['num_urls'] = len(re.findall(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
        full_text
    ))
    
    # Check if any URL uses raw IP address
    ip_pattern = r'http[s]?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
    features['has_ip_url'] = 1 if re.search(ip_pattern, full_text) else 0
    
    # Count exclamation marks
    features['num_exclamations'] = full_text.count('!')
    
    # Check for urgent/scam keywords
    urgent_words = [
        'urgent', 'verify', 'account', 'suspended', 'click here', 'act now',
        'limited time', 'expire', 'confirm', 'update', 'security', 'alert',
        'winner', 'congratulations', 'prize', 'claim', 'free', 'offer',
        'password', 'credit card', 'ssn', 'social security'
    ]
    text_lower = full_text.lower()
    features['contains_urgent_words'] = 1 if any(word in text_lower for word in urgent_words) else 0
    
    # Extract sender domain
    if sender and '@' in str(sender):
        try:
            domain = str(sender).split('@')[1].split('>')[0].strip().lower()
            features['sender_domain'] = domain
        except:
            features['sender_domain'] = 'unknown'
    else:
        features['sender_domain'] = 'unknown'
    
    # Body length
    features['body_length'] = len(full_text)
    
    # Uppercase ratio
    if len(full_text) > 0:
        uppercase_count = sum(1 for c in full_text if c.isupper())
        features['uppercase_ratio'] = uppercase_count / len(full_text)
    else:
        features['uppercase_ratio'] = 0.0
    
    # NEW FEATURE (V2): Writing style score
    # Combines sentence length variance and formality markers
    # Helps distinguish Nigerian 419 prose from corporate phishing templates
    sentences = re.split(r'[.!?]+', full_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 0]
    
    if len(sentences) > 1:
        sentence_lengths = [len(s.split()) for s in sentences]
        # Higher variance suggests more natural, varied writing (less templated)
        style_variance = np.std(sentence_lengths) if len(sentence_lengths) > 1 else 0.0
    else:
        style_variance = 0.0
    
    # Formality markers (formal greetings, closings)
    formality_markers = ['dear', 'sincerely', 'regards', 'respectfully', 'yours truly']
    formality_count = sum(1 for marker in formality_markers if marker in text_lower)
    
    # Combine: high variance + formality = Nigerian 419 style prose
    # Low variance + urgency = templated corporate phishing
    features['writing_style_score'] = float(style_variance) + (formality_count * 2.0)
    
    return features


def predict_email(subject: str, body: str, sender: str = None) -> Dict:
    """
    Predict if an email is phishing or legitimate.
    
    Args:
        subject: Email subject line
        body: Email body text  
        sender: Sender email address (optional)
    
    Returns:
        Dictionary with:
            - label: "phishing" or "legitimate"
            - confidence: float between 0 and 1 (model's confidence)
            - risk_score: int between 0 and 100 (scaled for UI display)
            - features: dict of extracted features (for debugging/analysis)
    
    Example:
        >>> result = predict_email(
        ...     subject="Verify your account now!",
        ...     body="Click here to verify: http://192.168.1.1/verify",
        ...     sender="noreply@suspicious-domain.com"
        ... )
        >>> print(result)
        {
            'label': 'phishing',
            'confidence': 0.92,
            'risk_score': 92,
            'features': {...}
        }
    """
    try:
        # Load model
        model = load_model()
        
        # Combine subject and body for prediction
        full_text = f"{subject} {body}"
        
        # Extract features
        features = extract_features(subject, body, sender)
        
        # Create DataFrame with correct column order
        # (must match V2 training data structure with 7 features)
        X = pd.DataFrame([{
            'body': full_text,
            'num_urls': features['num_urls'],
            'has_ip_url': features['has_ip_url'],
            'num_exclamations': features['num_exclamations'],
            'contains_urgent_words': features['contains_urgent_words'],
            'body_length': features['body_length'],
            'uppercase_ratio': features['uppercase_ratio'],
            'writing_style_score': features['writing_style_score']
        }])
        
        # Make prediction
        prediction = model.predict(X)[0]
        
        # Get probability scores
        probabilities = model.predict_proba(X)[0]
        
        # Determine label based on prediction
        # Check if prediction is string or integer (different sklearn versions)
        if isinstance(prediction, str):
            label = prediction
            pred_idx = 1 if prediction == 'phishing' else 0
        else:
            # prediction: 0 = legitimate, 1 = phishing (integer)
            pred_idx = int(prediction)
            label = "phishing" if pred_idx == 1 else "legitimate"
        
        # Confidence is the probability of the predicted class
        confidence = float(probabilities[pred_idx])
        
        # Risk score: 0-100 scale (phishing probability * 100)
        phishing_probability = float(probabilities[1])
        risk_score = int(phishing_probability * 100)
        
        return {
            'label': label,
            'confidence': confidence,
            'risk_score': risk_score,
            'features': features,
            'probabilities': {
                'legitimate': float(probabilities[0]),
                'phishing': float(probabilities[1])
            }
        }
    
    except Exception as e:
        # Return error with safe defaults
        return {
            'label': 'unknown',
            'confidence': 0.0,
            'risk_score': 50,  # Neutral score on error
            'error': str(e),
            'features': {}
        }


def predict_batch(emails: list) -> list:
    """
    Predict multiple emails in batch for better performance.
    
    Args:
        emails: List of dicts with 'subject', 'body', 'sender' keys
    
    Returns:
        List of prediction dictionaries
    """
    model = load_model()
    results = []
    
    # Prepare batch data
    X_list = []
    features_list = []
    
    for email in emails:
        subject = email.get('subject', '')
        body = email.get('body', '')
        sender = email.get('sender', None)
        
        full_text = f"{subject} {body}"
        features = extract_features(subject, body, sender)
        features_list.append(features)
        
        X_list.append({
            'body': full_text,
            'num_urls': features['num_urls'],
            'has_ip_url': features['has_ip_url'],
            'num_exclamations': features['num_exclamations'],
            'contains_urgent_words': features['contains_urgent_words'],
            'body_length': features['body_length'],
            'uppercase_ratio': features['uppercase_ratio'],
            'writing_style_score': features['writing_style_score']
        })
    
    X_batch = pd.DataFrame(X_list)
    
    # Batch prediction
    predictions = model.predict(X_batch)
    probabilities = model.predict_proba(X_batch)
    
    # Format results
    for i, (pred, probs) in enumerate(zip(predictions, probabilities)):
        label = "phishing" if pred == 1 else "legitimate"
        confidence = float(probs[pred])
        risk_score = int(probs[1] * 100)
        
        results.append({
            'label': label,
            'confidence': confidence,
            'risk_score': risk_score,
            'features': features_list[i],
            'probabilities': {
                'legitimate': float(probs[0]),
                'phishing': float(probs[1])
            }
        })
    
    return results


# Example usage and testing
if __name__ == "__main__":
    print("ML Email Classifier - Inference Module Test")
    print("=" * 80)
    
    # Test examples
    test_emails = [
        {
            'subject': 'Your Amazon order has shipped',
            'body': 'Hello, your order #123456 has been shipped and will arrive in 2 days.',
            'sender': 'auto-confirm@amazon.com',
            'expected': 'legitimate'
        },
        {
            'subject': 'URGENT: Verify your account NOW!!!',
            'body': 'Your account has been suspended. Click here to verify: http://192.168.1.1/verify?id=12345. Act now or your account will be deleted!',
            'sender': 'noreply@suspicious-site.tk',
            'expected': 'phishing'
        },
        {
            'subject': 'Meeting tomorrow at 2pm',
            'body': 'Hi team, reminder that we have a meeting tomorrow at 2pm in conference room B.',
            'sender': 'manager@company.com',
            'expected': 'legitimate'
        },
        {
            'subject': 'You won $1,000,000!',
            'body': 'CONGRATULATIONS!!! You are the lucky winner of our lottery! Click here to claim your prize immediately: http://suspicious-lottery.com/claim. Limited time offer!',
            'sender': 'winner@lottery-scam.info',
            'expected': 'phishing'
        }
    ]
    
    print("\nTesting predictions:\n")
    
    for i, email in enumerate(test_emails, 1):
        print(f"Test {i}: {email['subject'][:50]}...")
        result = predict_email(email['subject'], email['body'], email['sender'])
        
        print(f"  Expected: {email['expected']}")
        print(f"  Predicted: {result['label']} (confidence: {result['confidence']:.2%})")
        print(f"  Risk Score: {result['risk_score']}/100")
        print(f"  Key features:")
        print(f"    - URLs: {result['features']['num_urls']}")
        print(f"    - IP URLs: {result['features']['has_ip_url']}")
        print(f"    - Urgent words: {result['features']['contains_urgent_words']}")
        print(f"    - Exclamations: {result['features']['num_exclamations']}")
        
        match = "✓" if result['label'] == email['expected'] else "✗"
        print(f"  Result: {match}\n")
    
    print("\n" + "=" * 80)
    print("✓ Inference module test complete")
