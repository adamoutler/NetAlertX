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
            return LdapProvider()
        return LocalProvider()

    def authenticate(self, username: str, password: str) -> AuthResult:
        """Authenticate *username* / *password* with the active provider."""
        ldap_enabled = get_setting_value("LDAP_enabled")
        
        if ldap_enabled:
            # Check requirements
            setpwd_enabled = get_setting_value("SETPWD_enable_password")
            disable_local = get_setting_value("LDAP_disable_local_admin")
            
            if not setpwd_enabled and not disable_local:
                mylog("warning", ["[auth.manager] LDAP is enabled but SETPWD_enable_password is disabled. Local admin account is still active unless explicitly disabled in LDAP settings (not recommended)."])

            mylog("verbose", ["[auth.manager] Trying LDAP provider"])
            ldap_result = LdapProvider().authenticate(username, password)
            if ldap_result.success:
                return ldap_result

            # Fallback to local admin unless explicitly disabled
            if not disable_local:
                mylog("warning", ["[auth.manager] LDAP failed, falling back to local provider"])
                local_result = LocalProvider().authenticate(username, password)
                if not local_result.success:
                    mylog("verbose", [f"[auth.manager] Authentication failed for user '{username}' via both ldap and local"])
                return local_result
            else:
                mylog("verbose", [f"[auth.manager] Authentication failed for user '{username}' via ldap (local fallback disabled)"])
                return ldap_result

        mylog("verbose", ["[auth.manager] Using local provider"])
        local_result = LocalProvider().authenticate(username, password)
        if not local_result.success:
            mylog("verbose", [f"[auth.manager] Authentication failed for user '{username}' via local"])
        return local_result
