import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.automation.executor import CommandExecutor
from core.automation.registry import CommandRegistry


class TestRegistryExecutor(unittest.TestCase):
    def test_execute_registered_command(self):
        registry = CommandRegistry()
        registry.register("ping", lambda: "pong", group="system", permission="basic")

        executor = CommandExecutor(registry)
        self.assertEqual(executor.execute("ping"), "pong")

    def test_execute_unknown_command(self):
        registry = CommandRegistry()
        executor = CommandExecutor(registry)
        self.assertIn("Unknown command", executor.execute("nope"))


if __name__ == "__main__":
    unittest.main()
