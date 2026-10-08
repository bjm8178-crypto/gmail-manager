"""Regression tests verifying ownership protection in database.py.

P0-2: Ensure all email operations require user_id for ownership verification.
"""
import inspect
import unittest
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]


class OwnershipProtectionTests(unittest.TestCase):
    """Verify that critical functions require user_id for ownership checks."""
    
    def test_update_email_label_id_requires_user_id(self):
        """
        ✅ FIXED: update_email_label_id now requires user_id parameter.
        
        Location: database.py line 720
        Fixed signature: update_email_label_id(email_id: str, label_id: int, *, user_id: int)
        SQL: UPDATE analyzed_emails SET ... WHERE email_id = %s AND user_id = %s
        
        Prevents: Cross-user label manipulation
        """
        import sys
        sys.path.insert(0, str(BACKEND))
        import database
        
        sig = inspect.signature(database.update_email_label_id)
        params = list(sig.parameters.keys())
        
        self.assertIn('user_id', params,
            "update_email_label_id must require user_id for ownership check")
        self.assertEqual(params, ['email_id', 'label_id', 'user_id'],
            "Signature must include user_id ownership parameter")
    
    def test_add_to_retry_queue_requires_user_id(self):
        """
        ✅ FIXED: add_to_retry_queue now requires user_id parameter.
        
        Location: database.py line 900
        Fixed signature: add_to_retry_queue(email_id: str, user_id: int, error_reason: str)
        SQL: Joins analyzed_emails to verify user ownership
        
        Prevents: Cross-account retry queue pollution
        """
        import sys
        sys.path.insert(0, str(BACKEND))
        import database
        
        sig = inspect.signature(database.add_to_retry_queue)
        params = list(sig.parameters.keys())
        
        self.assertIn('user_id', params,
            "add_to_retry_queue must require user_id for ownership check")
        self.assertEqual(params, ['email_id', 'user_id', 'error_reason'],
            "Signature must include user_id ownership parameter")
    
    def test_mark_retry_attempt_requires_user_id(self):
        """
        ✅ FIXED: mark_retry_attempt now requires user_id parameter.
        
        Location: database.py line 973
        Fixed signature: mark_retry_attempt(email_id: str, user_id: int)
        SQL: WHERE email_id = %s AND email_id IN (SELECT email_id FROM analyzed_emails WHERE user_id = %s)
        
        Prevents: Cross-user retry count manipulation
        """
        import sys
        sys.path.insert(0, str(BACKEND))
        import database
        
        sig = inspect.signature(database.mark_retry_attempt)
        params = list(sig.parameters.keys())
        
        self.assertIn('user_id', params,
            "mark_retry_attempt must require user_id for ownership check")
        self.assertEqual(params, ['email_id', 'user_id'],
            "Signature must include user_id ownership parameter")


if __name__ == '__main__':
    unittest.main()
