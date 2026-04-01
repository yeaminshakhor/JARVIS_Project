"""Security policy checks after parsing command actions."""

from __future__ import annotations

from typing import Dict, Set, Tuple

from ..enhanced_compat import SecurityLayer


class AutomationSecurityPolicy:
    def __init__(self, security_layer: SecurityLayer):
        self._security_layer = security_layer
        self._role_permissions: Dict[str, Set[str]] = {
            "user": {"basic"},
            "admin": {"basic", "admin"},
        }
        self._restricted_actions = {"shutdown", "restart"}

    def validate_raw(self, command_text: str) -> Tuple[bool, str]:
        return self._security_layer.validate_command(command_text)

    def validate_action(
        self,
        action: str,
        params: Dict[str, str],
        *,
        permission: str = "basic",
        role: str = "user",
    ) -> Tuple[bool, str]:
        _ = params

        normalized_role = (role or "user").strip().lower()
        allowed_permissions = self._role_permissions.get(normalized_role, self._role_permissions["user"])
        if permission not in allowed_permissions:
            return False, f"Permission denied for role '{normalized_role}'"

        if action in self._restricted_actions and normalized_role != "admin":
            return False, "Restricted command"

        return True, "Command validated"
