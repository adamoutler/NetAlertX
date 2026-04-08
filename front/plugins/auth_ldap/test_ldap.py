import sys
import os

# Add server path to sys.path
INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.append(f"{INSTALL_PATH}/server")

from auth.ldap_provider import LdapProvider

def main():
    print("[LDAP Test] Starting LDAP connection test...")
    provider = LdapProvider()
    cfg = provider._read_config()
    
    if not cfg.get("server"):
        print("[LDAP Test] ERROR: LDAP server not configured")
        sys.exit(1)
        
    try:
        import ldap3
        server_obj = ldap3.Server(
            cfg["server"],
            port=cfg["port"],
            use_ssl=cfg["use_ssl"],
            connect_timeout=cfg["timeout"],
            get_info=ldap3.NONE,
        )
        
        print(f"[LDAP Test] Attempting to connect to {cfg['server']}:{cfg['port']}...")
        
        conn = ldap3.Connection(
            server_obj,
            user=cfg["bind_dn"] or None,
            password=cfg["bind_password"] or None,
            auto_bind=ldap3.AUTO_BIND_NONE,
            authentication=ldap3.SIMPLE if cfg["bind_dn"] else ldap3.ANONYMOUS,
        )
        
        if cfg["use_start_tls"] and not cfg["use_ssl"]:
            conn.start_tls()
        
        if not conn.bind():
            print(f"[LDAP Test] ❌ ERROR: Service-account bind failed: {conn.result}")
            sys.exit(1)
            
        print("[LDAP Test] ✅ SUCCESS: Connected to LDAP server and successfully bound with service account.")
        
        # Test finding a user if possible, or just unbind.
        print(f"[LDAP Test] Base DN: {cfg['base_dn']}")
        print(f"[LDAP Test] User Filter: {cfg['user_filter']}")
        
        conn.unbind()
        
    except Exception as e:
        print(f"[LDAP Test] ❌ ERROR: Unexpected error testing LDAP: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
