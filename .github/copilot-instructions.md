This is NetAlertX. A network monitoring and alerting tool.
# Instructions for GitHub Copilot

Purpose: Provide AI assistant guidance so suggestions follow NetAlertX architecture, conventions, and safety practices. Keep answers concise but opinionated; reference existing helpers before inventing code. Prefer settings over hard‑coding behavior.

## 🧱 High-Level Architecture

| Layer | Role | Key Paths |
|-------|------|----------|
| Backend (Python loop + GraphQL) | Orchestrates scans, workflows, plugins, notifications, JSON export | `server/__main__.py`, `server/plugin.py`, `server/initialise.py` |
| Data / DB (SQLite) | Persistent state, device & plugin tables | `db/app.db`, `server/database.py` |
| Frontend (Nginx + PHP + JS) | Renders UI, polls JSON, triggers execution queue events | `front/`, `front/js/common.js`, `php/server/*.php` |
| Plugins (Python) | Data acquisition, enrichment, publishers, automation | `front/plugins/*` |
| Workflows | Post-event automation & reactive logic | `server/workflows/*` |
| Messaging / Notifications | Aggregation + publisher plugins | `server/messaging/*`, publisher plugin folders |
| API JSON Cache | Fast consumable state for UI | `api/*.json` (generated) |

Backend main loop (see `server/__main__.py`):
1. Import / re-import configs & plugin manifests (`importConfigs`).
2. Run any `once` plugins (only first loop) via `plugin_manager.run_plugin_scripts('once')`.
3. Service user execution queue events (`plugin_manager.check_and_run_user_event`).
4. Export API JSON (`api/update_api`).
5. Every minute boundary: run scheduled plugins, always-after-scan plugins, process scan results, name updates, new-device trigger plugins, notification generation + publishers, workflows, conditional API refreshes.
6. Sleep 5s; repeat forever.

Key phases exposed to plugins (argument to `run_plugin_scripts`):
`once`, `schedule`, `always_after_scan`, `before_name_updates`, `on_new_device`, `on_notification` (publisher stage), plus ad-hoc `run` via execution queue.

## ⚙️ Plugin System Overview

Manifest file: `front/plugins/<code_name>/config.json`
Important manifest fields:
- `code_name`: must match folder name.
- `unique_prefix`: setting + file name base (e.g. `ARPSCAN`).
- `data_source`: one of `script`, `app-db-query`, `sqlite-db-query`, `template`, `plugin_type`.
- `settings`: array of setting objects (drives UI & persistence) – parsed and inserted via `initialise.importConfigs`.
- `database_column_definitions`: mapping of plugin output columns → internal DB columns (for device import or object mapping).
- `show_ui`: controls visibility in plugins page.

Execution control settings (prefix = `unique_prefix`):
- `<PREF>_RUN`: `disabled`, `once`, `schedule`, `always_after_scan`, `before_name_updates`, `on_new_device`, `on_notification` (context-dependent) – must match code expectations.
- `<PREF>_RUN_SCHD`: cron-like descriptor for scheduled execution (parsed into `conf.mySchedules`).
- `<PREF>_CMD`: command string; for script plugins typically `python3 front/plugins/<code_name>/script.py`.
- `<PREF>_RUN_TIMEOUT`: safety timeout for script execution.
- `<PREF>_WATCH`: comma-separated list of watched value columns for change notifications.

Script plugin data path contract (see `docs/PLUGINS_DEV.md`):
- Script writes (usually via helper) a pipe-delimited `last_result.<PREF>.log` file in `/app/log/plugins/`.
- 9 mandatory columns + 4 optional helper columns (must pad unused optional ones if any are used).
- Backend ingests into plugin tables or device import depending on mapping.

Helper Library: `front/plugins/plugin_helper.py`
- Provides `Plugin_Object` and `Plugin_Objects` to sanitize & serialize output.
- Call `add_object(...)` repeatedly, then `write_result_file()` once.
- Normalizes MACs (`normalize_mac`) & sanitizes text.

Template: `front/plugins/__template/rename_me.py` shows structure, logging, settings access.

Result pipeline (script plugins):
Script → helper builds `last_result.<PREF>.log` → backend `execute_plugin()` parses → DB insert/update → JSON export → UI consumption → notifications (watched diffs) → publishers.

### Adding a New Script Plugin (Minimal Path)
1. Copy `front/plugins/__template` to `front/plugins/<code_name>`; rename file(s) appropriately.
2. Edit `config.json`: set `code_name`, `unique_prefix`, `settings`, `data_source`.
3. Implement logic in `script.py`: build `Plugin_Objects`, add objects, write result file.
4. Set `<PREF>_RUN=once` to test; backend loop executes it automatically.
5. Inspect `/app/log/plugins/script.<PREF>.log` & `last_result.<PREF>.log`.
6. Switch to `schedule` or other execution phase as required.
7. Map columns for device import if creating devices (`database_column_definitions`).

### Common Plugin Debug Steps
- Ensure unique prefix not colliding (search repository for existing prefix).
- Verify `<PREF>_CMD` path is valid inside container (`/app/...`).
- Check backend log for `[Plugins]` entries and schedule decisions.
- Confirm run type matches `<PREF>_RUN` exactly.
- Validate `last_result.<PREF>.log` formatting (pipe count, `null` placeholders, timestamp format `YYYY-MM-DD HH:MM:SS`).
- If schedule not firing: inspect `conf.mySchedules` via logs & update time zone / schedule expression.

## 🖥 Frontend Data Flow

Bootstrap sequence (`front/js/common.js`): `executeOnce()` → `waitForGraphQLServer()` → parallel caching (`cacheDevices`, `cacheSettings`, `cacheStrings`) → `onAllCallsComplete()` to finalize UI.

Access helpers (prefer these):
- `getSetting(key)` returns value from cached settings.
- `getDevDataByMac(mac, column)` for device lookups.
- `getString(key)` for localized text (never hardcode UI labels).
- `showMessage`, `showModalOk`, `showModalWarning` for user feedback.

Settings UI generation (`front/js/settings_utils.js`): resolves dynamic options (base64-encoded arrays), plugin grouping, form control type determination. When adding new setting types, follow existing pattern & update docs.

Execution queue (user-triggered events): via PHP helper writing to execution log; backend reads with `plugin_manager.check_and_run_user_event()` enabling ad-hoc plugin runs or API refresh.

## 🔐 Settings & Configuration

Define new core settings via `ccd()` in `server/initialise.py` (ensures defaults, migration, metadata). Avoid scattering literal values—add a setting or reuse existing one. When adding plugin-only settings, define inside plugin manifest.

Never hardcode network ports; rely on existing `PORT`, `GRAPHQL_PORT`, or env-injected settings. Reference via `get_setting_value()`.

## 🪵 Logging & Log Locations

| Component | Path |
|-----------|------|
| Backend app log | `log/app.log` or `/app/log/app.log` inside container |
| Backend stdout/stderr (debugpy start) | `/app/log/app_stdout.log`, `/app/log/app_stderr.log` |
| Plugin script logs | `/app/log/plugins/script.<PREF>.log` |
| Plugin last results | `/app/log/plugins/last_result.<PREF>.log` |
| Notification / event traces | part of main log + DB tables |

Increase verbosity: set `LOG_LEVEL` to `trace` (revert afterward). Some warnings are normal during early plugin iteration (missing result file, empty mappings) – treat repeated ones as smell.

## 🐞 Debugging in VS Code

Backend:
- Use task: "Restart GraphQL" (starts with `debugpy --listen 0.0.0.0:5678`).
- Attach with remote Python debug configuration (port 5678).
- Set breakpoints in `server/` modules; dynamic reload is limited—restart backend after structural changes.

Frontend (PHP):
- Use task: "Restart Nginx and PHP-FPM".
- Xdebug (port 9003) attaches to a "Listen for Xdebug" configuration.
- Ensure browser Xdebug helper extension sends the cookie; otherwise requests won't break.

Plugin manual execution (inside dev container):
```
python3 front/plugins/<code_name>/script.py
```
If environment-specific imports fail, confirm plugin extends `sys.path` with `/app/front/plugins` & `/app/server` as per template.

## 🔔 Event & Notification Lifecycle
1. Plugin (or scan) produces data object.
2. Backend detects changed watched values → inserts row in events/notifications tables.
3. Notification aggregation merges events (see `messaging/reporting.py`).
4. Publisher plugins (`plugin_type=publisher`) with `<PREF>_RUN=on_notification` send outbound messages.
5. UI polls JSON; new notifications displayed & history updated.

## 🧪 Safe Contribution Guidelines
- Reuse helpers: `timeNowTZ`, `get_setting_value`, `mylog` (log levels: none/minimal/verbose/debug/trace).
- Keep plugin scripts idempotent per run; no cumulative file writes besides result log.
- Sanitize all external text (helper already strips non-ASCII & newlines).
- Avoid direct raw SQL in new code paths—prefer abstractions; if needed, centralize queries.
- Validate MACs with `normalize_mac` before DB insertion.
- Wrap new long-running or blocking operations with timeout or schedule separation.

## 💡 When to Suggest What (Assistant Heuristics)
| User Intent | Assistant Direction |
|-------------|--------------------|
| Add plugin to import devices | Start from template; map `database_column_definitions`; watched fields for change alerts |
| Need periodic task | Use plugin with `schedule` + `<PREF>_RUN_SCHD`; not a while loop in core |
| New notification channel | Create publisher-style plugin (`plugin_type=publisher`, run on `on_notification`) |
| Add configurable behavior | Introduce setting (core `ccd()` or plugin manifest) |
| UI slow / stale | Check JSON cache update triggers & execution queue for `update_api` entries |
| Plugin not firing | Verify `<PREF>_RUN`, schedule overdue, log presence, path of `CMD` |
| Need custom table view | Use `app-db-query` plugin with a SQL query returning expected columns |

## 🪜 Internal Phases Cheat Sheet
| Phase | Typical Use |
|-------|-------------|
| once | One-time initialization & data bootstrap |
| schedule | Interval / cron-based acquisition |
| always_after_scan | Enrichment after each scan cycle |
| before_name_updates | Provide data used during name resolution |
| on_new_device | React to discovery of fresh devices |
| on_notification | Publisher / outbound gateways |

## 🛠 Adding Core Settings (Example Pattern)
In `server/initialise.py`, follow existing calls to `ccd()` (create config definition). Provide: group, key, type, default, description. Keep naming consistent & UPPER_SNAKE_CASE.

## 🧾 Quick Commands (For Maintainers Inside Container)
```
# Restart backend manually
killall python3 2>/dev/null || true; python3 -m debugpy --listen 0.0.0.0:5678 /app/server/__main__.py &

# Run a specific plugin immediately
python3 front/plugins/<code_name>/script.py

# Tail main + a plugin log
tail -f log/app.log /app/log/plugins/script.<PREF>.log
```

## ✅ Assistant Response Expectations
When user requests changes:
- Reference these guidelines.
- Point to specific files/paths (backticks) instead of broad advice.
- If adding code: ensure path correctness, reuse existing style, avoid silent hardcoding.
- Offer minimal test or validation method (e.g., how to see effect in logs/UI).

## ⏳ Future Enhancements (Do NOT Assume Implemented)
- Extended GraphQL coverage (partial currently) – avoid promising full schema.
- Plugin hot-reload without backend restart.
- Unified notification rule engine (currently plugin + workflow blend).

---
End of internal assistant guidance.