import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.automation.security import AutomationSecurityPolicy
from core.utils import SecurityLayer


class TestSecurityPolicy(unittest.TestCase):
    def setUp(self):
        self.policy = AutomationSecurityPolicy(SecurityLayer())

    def test_user_denied_admin_permission(self):
        ok, msg = self.policy.validate_action("shutdown", {}, permission="admin", role="user")
        self.assertFalse(ok)
        self.assertIn("Permission denied", msg)

    def test_admin_allowed_admin_permission(self):
        ok, msg = self.policy.validate_action("shutdown", {}, permission="admin", role="admin")
        self.assertTrue(ok)
        self.assertIn("validated", msg.lower())

    def test_restricted_action_denied_for_user_even_if_basic(self):
        ok, msg = self.policy.validate_action("restart", {}, permission="basic", role="user")
        self.assertFalse(ok)
        self.assertIn("Restricted", msg)


if __name__ == "__main__":
    unittest.main()
