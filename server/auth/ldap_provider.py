"""
LDAP authentication provider for NetAlertX.

Uses the *search-then-bind* pattern which is compatible with both OpenLDAP and
Microsoft Active Directory:

1. Connect to the LDAP server (optionally over TLS/StartTLS).
2. Bind with a read-only service account (``LDAP_bind_dn`` / ``LDAP_bind_password``).
3. Search for the user entry whose ``LDAP_user_filter`` matches *username*.
4. Re-bind as that user with the supplied *password*.
5. A successful re-bind means the credentials are valid.

Configuration settings (via NetAlertX plugin ``auth_ldap``)
-------------------------------------------------------------
- ``LDAP_server``              – hostname or IP of the LDAP/AD server
- ``LDAP_port``                – default 389 (636 for LDAPS)
- ``LDAP_use_ssl``             – True → LDAPS (port 636), False → plain / StartTLS
- ``LDAP_use_start_tls``       – True → issue StartTLS on a plain-text connection
- ``LDAP_bind_dn``             – service-account DN for the initial search bind
- ``LDAP_bind_password``       – service-account password
- ``LDAP_base_dn``             – base DN for the user search
- ``LDAP_user_filter``         – search filter template; ``{username}`` is replaced at
                                 runtime.  Examples:
                                 OpenLDAP : ``(uid={username})``
                                 Active Directory: ``(sAMAccountName={username})``
- ``LDAP_username_attribute``  – attribute that holds the login name (default ``uid``)
"""

from __future__ import annotations

import re
import ssl
from typing import Optional

from helper import get_setting_value
from logger import mylog
from auth.base import AuthProvider, AuthResult


# ---------------------------------------------------------------------------
# LDAP filter escaping (RFC 4515)
# ---------------------------------------------------------------------------

_LDAP_ESCAPE_RE = re.compile(r'[\\*()\x00]')
_LDAP_ESCAPE_MAP = {
    '\\': r'\5c',
    '*':  r'\2a',
    '(':  r'\28',
    ')':  r'\29',
    '\x00': r'\00',
}


def _escape_ldap_filter(value: str) -> str:
    """Escape special characters in an LDAP filter value (RFC 4515 §4)."""
    return _LDAP_ESCAPE_RE.sub(lambda m: _LDAP_ESCAPE_MAP[m.group(0)], value)


class LdapProvider(AuthProvider):
    """Authenticate against an LDAP / Active Directory server."""

    name = "ldap"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def authenticate(self, username: str, password: str) -> AuthResult:
        if not username or not password:
            return AuthResult.fail(self.name, "Username and password are required")

        try:
            import ldap3  # noqa: PLC0415 (deferred to avoid hard dep at import time)
        except ImportError:
            mylog("none", ["[auth.ldap] ldap3 package is not installed"])
            return AuthResult.fail(self.name, "LDAP library not available")

        cfg = self._read_config()
        if not cfg.get("server"):
            return AuthResult.fail(self.name, "LDAP server not configured")

        tls_obj = None
        if cfg["use_ssl"] or cfg["use_start_tls"]:
            validate = ssl.CERT_REQUIRED if cfg["tls_verify_cert"] else ssl.CERT_NONE
            ca_certs_file = cfg["ca_cert_path"] if cfg["ca_cert_path"] else None
            tls_obj = ldap3.Tls(validate=validate, ca_certs_file=ca_certs_file)

        server_obj = ldap3.Server(
            cfg["server"],
            port=cfg["port"],
            use_ssl=cfg["use_ssl"],
            tls=tls_obj,
            connect_timeout=cfg["timeout"],
            get_info=ldap3.NONE,
        )

        try:
            user_dn = self._resolve_user_dn(ldap3, server_obj, cfg, username)
            if user_dn is None:
                return AuthResult.fail(self.name)

            return self._bind_as_user(ldap3, server_obj, cfg, user_dn, username, password)

        except Exception as exc:
            mylog("none", [f"[auth.ldap] Unexpected error for user '{username}': {exc}"])
            return AuthResult.fail(self.name, "LDAP authentication error")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _read_config(self) -> dict:
        return {
            "server":       str(get_setting_value("LDAP_server") or "").strip(),
            "port":         int(get_setting_value("LDAP_port") or 389),
            "use_ssl":      bool(get_setting_value("LDAP_use_ssl")),
            "use_start_tls": bool(get_setting_value("LDAP_use_start_tls")),
            "bind_dn":      str(get_setting_value("LDAP_bind_dn") or "").strip(),
            "bind_password": str(get_setting_value("LDAP_bind_password") or "").strip(),
            "base_dn":      str(get_setting_value("LDAP_base_dn") or "").strip(),
            "user_filter":  str(get_setting_value("LDAP_user_filter") or "(uid={username})").strip(),
            "username_attr": str(get_setting_value("LDAP_username_attribute") or "uid").strip(),
            "timeout":      5,
        }

    def _create_secure_connection(self, ldap3, server_obj, cfg: dict, user: Optional[str], password: Optional[str], authentication):
        """
        Creates a secure LDAP connection, handling the StartTLS sequence
        correctly before binding.
        """
        conn = ldap3.Connection(
            server_obj,
            user=user,
            password=password,
            auto_bind=ldap3.AUTO_BIND_NONE,
            authentication=authentication,
        )

        if cfg["use_start_tls"] and not cfg["use_ssl"]:
            conn.start_tls()

        if not conn.bind():
            return conn, False

        return conn, True

    def _resolve_user_dn(self, ldap3, server_obj, cfg: dict, username: str) -> Optional[str]:
        """
        Bind with the service account and search for the user's DN.
        Returns the DN string on success, None if user is not found.
        Raises if the connection itself fails.
        """
        safe_username = _escape_ldap_filter(username)
        search_filter = cfg["user_filter"].replace("{username}", safe_username)

        authentication = ldap3.SIMPLE if cfg["bind_dn"] else ldap3.ANONYMOUS
        conn, bind_success = self._create_secure_connection(
            ldap3, server_obj, cfg,
            user=cfg["bind_dn"] or None,
            password=cfg["bind_password"] or None,
            authentication=authentication
        )

        try:
            if not bind_success:
                mylog("none", [f"[auth.ldap] Service-account bind failed: {conn.result}"])
                return None

            conn.search(
                search_base=cfg["base_dn"],
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=[cfg["username_attr"]],
                size_limit=2,
            )

            entries = conn.entries
            if len(entries) != 1:
                mylog("verbose", [
                    f"[auth.ldap] User '{username}' not found "
                    f"(got {len(entries)} entries for filter {search_filter})"
                ])
                return None

            return entries[0].entry_dn

        finally:
            conn.unbind()

    def _bind_as_user(
        self, ldap3, server_obj, cfg: dict,
        user_dn: str, username: str, password: str,
    ) -> AuthResult:
        """
        Attempt to bind as *user_dn* using the supplied *password*.
        A successful bind confirms valid credentials.
        """
        conn, bind_success = self._create_secure_connection(
            ldap3, server_obj, cfg,
            user=user_dn,
            password=password,
            authentication=ldap3.SIMPLE
        )

        try:
            if bind_success:
                return AuthResult.ok(username, self.name)

            mylog("verbose", [f"[auth.ldap] User bind failed for DN '{user_dn}': {conn.result}"])
            return AuthResult.fail(self.name)

        finally:
            conn.unbind()
