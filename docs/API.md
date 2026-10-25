# API Documentation

This API provides programmatic access to **devices, events, sessions, metrics, network tools, and sync** in NetAlertX. It is implemented as a **REST and GraphQL server**. All requests require authentication via **API Token** (`API_TOKEN` setting) unless explicitly noted. For example, to authorize a GraphQL request, you need to use a `Authorization: Bearer API_TOKEN` header as per example below:

```graphql
curl 'http://host:GRAPHQL_PORT/graphql' \
  -X POST \
  -H 'Authorization: Bearer API_TOKEN' \
  -H 'Content-Type: application/json' \
  --data '{
    "query": "query GetDevices($options: PageQueryOptionsInput) { devices(options: $options) { devices { rowid devMac devName devOwner devType devVendor devLastConnection devStatus } count } }",
    "variables": {
      "options": {
        "page": 1,
        "limit": 10,
        "sort": [{ "field": "devName", "order": "asc" }],
        "search": "",
        "status": "connected"
      }
    }
  }'
```

The API server runs on `0.0.0.0:<graphql_port>` with **CORS enabled** for all main endpoints.

CORS configuration: You can limit allowed CORS origins with the `CORS_ORIGINS` environment variable. Set it to a comma-separated list of origins (for example: `CORS_ORIGINS="https://example.com,http://localhost:3000"`). The server parses this list at startup and only allows origins that begin with `http://` or `https://`. If `CORS_ORIGINS` is unset or parses to an empty list, the API falls back to a safe development default list (localhosts) and will include `*` as a last-resort permissive origin.

---

## Authentication

All endpoints require an API token provided in the HTTP headers:

```http
Authorization: Bearer <API_TOKEN>
```

If the token is missing or invalid, the server will return:

```json
{
  "success": false,
  "message": "ERROR: Not authorized",
  "error": "Forbidden"
}
```

HTTP Status: **403 Forbidden**

---

## Base URL

```
http://<server>:<GRAPHQL_PORT>/
```

---

## Endpoints

> [!NOTE]
> You can explore the API endpoints by using the interactive API docs at `http://<server>:<GRAPHQL_PORT>/docs`.
> ![API docs](./img/API/API_docs.png)

> [!TIP]
> When retrieving devices or settings try using the GraphQL API endpoint first as it is read-optimized.

### Standard REST Endpoints

* [Device API Endpoints](API_DEVICE.md) – Manage individual devices
* [Devices Collection](API_DEVICES.md) – Bulk operations on multiple devices
* [Events](API_EVENTS.md) – Device event logging and management
* [Sessions](API_SESSIONS.md) – Connection sessions and history
* [Settings](API_SETTINGS.md) – Settings
* Messaging:
    * [In app messaging](API_MESSAGING_IN_APP.md) - In-app messaging
* [Metrics](API_METRICS.md) – Prometheus metrics and per-device status
* [Network Tools](API_NETTOOLS.md) – Utilities like Wake-on-LAN, traceroute, nslookup, nmap, and internet info
* [Online History](API_ONLINEHISTORY.md) – Online/offline device records
* [GraphQL](API_GRAPHQL.md) – Advanced queries and filtering for Devices, Settings and Language Strings
* [Sync](API_SYNC.md) – Synchronization between multiple NetAlertX instances
* [Logs](API_LOGS.md) – Purging of logs and adding to the event execution queue for user triggered events
* [DB query](API_DBQUERY.md) (⚠ Internal) - Low level database access - use other endpoints if possible
* `/server` (⚠ Internal) - Backend server endpoint for internal communication only - **do not use directly**

### MCP Server Bridge

NetAlertX includes an **MCP (Model Context Protocol) Server Bridge** that provides AI assistants access to NetAlertX functionality through standardized tools, resources, and prompts over **Streamable HTTP**:

* `/mcp` (`POST`, `GET`, `DELETE`) - Primary **Streamable HTTP** endpoint for MCP client connections, JSON-RPC 2.0 requests/batches, session management (`Mcp-Session-Id`), and optional server-sent event streams
* `/openapi.json` (`GET`) - OpenAPI 3.1 specification used to dynamically generate MCP tool schemas (standard REST endpoints such as `/device/*`, `/devices/*`, `/nettools/*`, and `/events/*` are invoked via JSON-RPC `tools/call` on `/mcp`)
* `/mcp/sse` (`GET`) and `/mcp/messages` (`POST`) - **Deprecated** legacy HTTP+SSE endpoints retained for backward compatibility with older SSE-only MCP clients

MCP endpoints require the same Bearer token authentication (`Authorization: Bearer <API_TOKEN>`) as REST endpoints.

**📖 See [MCP Server Bridge API](API_MCP.md) for complete documentation, tool specifications, and integration examples.**

See [Testing](API_TESTS.md) for example requests and usage.

---

## Notes

* All endpoints enforce **Bearer token authentication**.
* Errors return JSON with `success: False` and an error message.
* GraphQL is available for advanced queries, while REST endpoints cover structured use cases.
* Endpoints run on `0.0.0.0:<GRAPHQL_PORT>` with **CORS enabled**.
* Use consistent API tokens and node/plugin names when interacting with `/sync` to ensure data integrity.
