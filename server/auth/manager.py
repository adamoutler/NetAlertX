"""
AuthManager — selects and dispatches to the correct authentication provider.

Decision logic
--------------
1. If ``LDAP_enabled`` setting is ``True`` → use :class:`LdapProvider`.
2. Otherwise → use :class:`LocalProvider`.

The manager does NOT cache the provider across requests so that toggling
``LDAP_enabled`` at runtime takes effect without a server restart.
"""

from __future__ import annotations

from helper import get_setting_value
from logger import mylog
from auth.base import AuthProvider, AuthResult
from auth.local_provider import LocalProvider
from auth.ldap_provider import LdapProvider


class AuthManager:
    """Thin dispatcher that picks the active :class:`AuthProvider`."""

    def get_provider(self) -> AuthProvider:
        """Return the :class:`AuthProvider` appropriate for the current config."""
        ldap_enabled = get_setting_value("LDAP_enabled")
        if ldap_enabled:
            mylog("verbose", ["[auth.manager] Using LDAP provider"])
            return LdapProvider()

        mylog("verbose", ["[auth.manager] Using local provider"])
        return LocalProvider()

    def authenticate(self, username: str, password: str) -> AuthResult:
        """Authenticate *username* / *password* with the active provider."""
        provider = self.get_provider()
        result = provider.authenticate(username, password)
        if not result.success:
            mylog(
                "verbose",
                [f"[auth.manager] Authentication failed for user '{username}' via {provider.name}"],
            )
        return result
