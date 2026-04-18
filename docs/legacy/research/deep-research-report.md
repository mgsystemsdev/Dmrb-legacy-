# Production-Grade Streamlit With Supabase PostgreSQL: Architecture, Performance, Reliability, and Data Access Patterns

## Execution model realities that dominate performance

Streamlit apps execute as a Python script on a server, while the UI runs in the user’s browser. A user’s browser maintains a persistent WebSocket connection to the server; each browser tab/window creates its own session, and the server maintains per-session context while pushing UI updates over that WebSocket. citeturn14view0

The single most important architectural constraint is Streamlit’s rerun model: user interactions typically trigger a rerun of the script from top to bottom, then Streamlit diffs and updates the UI. Design choices that fight this model (e.g., heavy network calls or repeated data loading at module import or early in the script) compound into latency and cost. Streamlit explicitly positions caching and state features as the mechanisms for efficiency within this rerun model. citeturn25view0turn20search16

### The two levers for reducing rerun cost: batching and partial reruns

**Batching widget-triggered reruns with forms.** `st.form` batches widget updates so values are “sent to Streamlit in a batch” when the form submit button is pressed. This is a practical way to stop “death-by-a-thousand-reruns” when a page has multiple filters or inputs. citeturn1search8turn1search22

**Partial reruns with fragments.** Streamlit introduced fragments to rerun a *portion* of code instead of the full script, which becomes increasingly valuable as the app grows. The docs explicitly describe fragments as a performance feature for large/complex apps by reducing unnecessary reruns. citeturn1search1turn1search5

image_group{"layout":"carousel","aspect_ratio":"16:9","query":["Streamlit client server architecture diagram WebSocket sessions","Streamlit caching st.cache_data st.cache_resource diagram","Streamlit fragments partial rerun diagram","Supabase Postgres connection pooling Supavisor diagram"],"num_per_query":1}

### Stress and failure analysis of the execution model

Streamlit’s architecture creates predictable failure modes under real load:

**CPU amplification via reruns.** If expensive computation or data retrieval sits “above” your UI branching logic (or is executed unconditionally), it runs on every rerun and multiplies by concurrent sessions. This is the core reason caching and “interactive batching” (`st.form`) exist. citeturn1search12turn3view0

**Cross-user coupling via global caches/resources.** Streamlit caching defaults to sharing cached values across users/sessions (depending on decorator scope), which is great for performance but becomes a correctness and isolation risk if you cache user-specific data globally. Streamlit’s docs emphasize that cached values can be available to all users and that per-session data belongs in Session State. citeturn13search0turn25view4turn13search11

**Replica + load balancer session hazards.** In multi-replica deployments, Streamlit calls out that some features will not work without session affinity (“stickiness”) because HTTP requests for media/files may be routed to a different replica than the one holding session context, leading to missing media files and file upload errors. citeturn14view0

## Application architecture and project structure for maintainability

Streamlit does not impose an architecture, so production-grade apps need a *deliberate* separation between UI code and “system” code (data access, domain logic, configuration, observability). This separation reduces rerun work, controls side effects, and makes testing feasible.

### Recommended high-level layering

A resilient Streamlit application can be treated as three layers:

**Presentation layer (Streamlit pages/components).** Purely renders UI and converts UI state into explicit requests for data/actions.

**Application/services layer.** Stateless “use cases” that:
- validate inputs,
- fetch or mutate data (via a repository/data-access layer),
- apply business rules,
- return serializable outputs.

**Infrastructure layer.** Database connections, query execution, external APIs, secrets loading, telemetry/logging.

This layering is strongly aligned with Streamlit’s caching model: cache infrastructure objects as “resources” and cache pure data-returning computations as “data.” citeturn3view1turn25view4turn20search16

### Multipage structure that scales with complexity

Streamlit supports multipage apps using the `pages/` directory (simple) or the newer `st.Page`/`st.navigation` approach (more flexible). With the directory approach, Streamlit identifies pages by `.py` files in `pages/` next to the entrypoint; the entrypoint acts as the “homepage.” citeturn1search2turn1search37

A production-friendly repository layout typically looks like:

```text
my_app/
  .streamlit/
    config.toml
    secrets.toml  # local only; do not commit
  app.py          # entrypoint / navigation frame
  pages/
    01_dashboard.py
    02_explorer.py
    03_admin.py
  src/
    core/
      settings.py
      errors.py
      logging.py
    data/
      db.py
      queries.py
      repositories.py
    services/
      analytics.py
      admin_actions.py
    ui/
      components.py
      formatters.py
  tests/
    test_services.py
    test_pages_smoke.py
```

This structure is designed to keep Streamlit pages thin and make the non-UI layers testable using Streamlit’s native app testing framework or conventional unit tests. citeturn15search3turn15search7

### Configuration as code, but not secrets as code

Streamlit supports a `.streamlit/config.toml` with extensive configuration options (server, client, logging, security, etc.). It is explicitly designed to be defined per-project or globally, and overridden by env vars or CLI flags. citeturn17view0turn2search26

Do not store secrets in the repo. Streamlit’s deployment docs explicitly call storing unencrypted secrets in a git repository “a bad practice” and recommend storing them outside code and passing as environment variables or via Streamlit’s secrets management. citeturn2search12turn2search0

## Caching and state management patterns that stay correct under concurrency

Streamlit provides two caching decorators with intentionally different semantics:

- `st.cache_data`: caches **data** outputs; cached objects are stored in pickled form and each caller gets its own copy, which reduces mutation/race hazards. It supports TTL and cache clearing. citeturn25view4turn3view0turn16search13  
- `st.cache_resource`: caches **resource** objects (e.g., DB connections); global resources are shared across users/sessions/reruns and must be thread-safe; session-scoped resources exist only for a session. It also supports validation functions (useful for DB connection health checks) and cache clearing. citeturn3view1turn20search3

### Production caching rules that prevent correctness regressions

**Rule: cache only what is either globally valid or keyed by the full user context.** Streamlit’s caching can be global across users/sessions; misuse can leak user-specific data across sessions. When data is user-specific, store it in Session State (per session) or include a stable user identifier in the cache key and only do so if your threat model allows it. citeturn25view4turn13search11

**Rule: never mutate cached data objects.** `st.cache_data` returns copies, but mutations after retrieval can still create confusing behavior. Streamlit’s guidance emphasizes `st.cache_data` as the safer default and positions `st.cache_resource` as mutable-singleton behavior that must be treated carefully. citeturn16search13turn3view1

**Rule: treat cache invalidation as a first-class API.** Both `st.cache_data` and `st.cache_resource` support clearing caches (`func.clear()` or global clear). Production systems should define explicit invalidation paths when writes occur so the UI cannot show stale data indefinitely. citeturn25view4turn3view1

### Handling unhashable/infrastructure arguments correctly

Cached functions require hashable arguments; Streamlit explicitly calls out that “unhashable argument (like a database connection)” should be excluded using an underscore prefix in the argument name, or alternative hashing configuration. This is a common pattern when you want `engine` caching but data caching keyed on query parameters. citeturn3view0turn3view1

### Async is usually a trap in Streamlit today

Streamlit’s caching docs explicitly state that caching async functions is not supported, and `st.cache_resource` warns that async objects are not officially supported and can cause “Event loop closed” errors due to Streamlit’s lifecycle. In practice, this means most production Streamlit apps should prefer synchronous database access patterns (and use connection pooling instead of async concurrency for DB throughput). citeturn3view0turn3view1turn21view0

## Supabase PostgreSQL integration: secure connectivity and fast query patterns

Supabase provides multiple Postgres connection options, and the choice affects reliability and performance.

### Connection mode selection for Streamlit deployments

Supabase’s documentation distinguishes:

- **Direct connection**: ideal for persistent servers (VMs/long-running containers). Direct connections use IPv6 by default; if your environment doesn’t support IPv6, use session pooler mode or an IPv4 add-on. citeturn3view3  
- **Pooler session mode**: a proxy-based option recommended as an alternative to direct connection when connecting via IPv4 networks. citeturn3view3  
- **Pooler transaction mode**: “ideal for serverless or edge functions” with many transient connections; **does not support prepared statements**, requiring client-specific disabling. citeturn3view3turn11search3  

A typical Streamlit app running on Docker/Kubernetes is a persistent service, so direct connection (or session pooler if IPv4 is required) is usually the most stable baseline. citeturn3view3turn2search2turn13search1

### TLS, SSL modes, and certificate verification

PostgreSQL supports SSL/TLS to encrypt client/server communications. citeturn12search15  
Supabase provides guidance on SSL enforcement and explicitly notes that different Postgres SSL modes provide different security properties; you should choose a mode that meets your enforcement and verification needs. citeturn12search0

For strict production settings, Supabase’s `psql` guide demonstrates using `sslmode=verify-full` with an added `sslrootcert` for certificate verification. citeturn12search8

### Network-level hardening

Supabase supports network restrictions (IP allowlists) for connections to Postgres and its pooler, enforced before traffic reaches the database; even when not restricted by IP, clients must still authenticate with valid DB credentials. citeturn12search2turn12search17

This is powerful for production, but it introduces an operational dependency: if your Streamlit deployment has unstable/outbound IPs (common in some cloud/serverless setups), maintaining allowlists can become a deployment constraint you must plan for. citeturn12search2turn14view0

### Prepared statements vs Supabase poolers: a hidden compatibility cliff

Supabase is explicit: **transaction mode does not support prepared statements** and you must disable them for your connection library. citeturn3view3turn11search6

This matters because modern drivers may auto-prepare. For example, psycopg has an automatic prepared statement system and documents that you can disable prepared statements by setting `prepare_threshold` to `None`. It also warns that, unless a pooler explicitly supports them, prepared statements are generally not compatible with connection pooling middleware because “the same client connection may change the server session it refers to.” citeturn7view0turn3view3

#### Practical guidance for Streamlit + Supabase poolers

- If you use **direct connection** or **session pooler**: prepared statements can be beneficial, but measure; planning time often isn’t your dominant cost unless latency is very low and queries repeat at high rate. citeturn11search2turn24view0  
- If you use **transaction pooler**: disable prepared statements in your driver/ORM. Supabase provides a troubleshooting guide and examples for disabling prepared statements across libraries. citeturn11search6turn3view3

### Query performance fundamentals that translate directly to Streamlit

In production, Streamlit performance is often dominated by database time + network latency. That makes standard Postgres tuning techniques disproportionately valuable:

- Use `EXPLAIN` / `EXPLAIN ANALYZE` to inspect query plans and confirm whether planner estimates match reality. citeturn11search0turn11search4  
- Use appropriate index types (B-tree by default; other index types exist for specialized workloads). citeturn11search12turn11search1  
- If you use Supabase Row Level Security policies, index the columns used in RLS predicates; Supabase reports very large improvements in some cases (example given: `auth.uid() = user_id`). citeturn12search3turn12search7  
- For expensive aggregations that back dashboards, consider Postgres materialized views; the Postgres docs explicitly note materialized views can be much faster than querying underlying tables/views, with the tradeoff of staleness until refreshed. citeturn15search0turn15search4  

## SQLAlchemy vs direct SQL for Supabase PostgreSQL in Streamlit

This section treats “SQLAlchemy” in the way production systems actually experience it: **SQLAlchemy Core (engine + SQL expressions/text)** vs **SQLAlchemy ORM**, and compares both against **direct driver usage** (DBAPI via psycopg/psycopg2).

### Performance implications

**Network dominates; layering costs are second-order unless you fetch huge result sets.** SQLAlchemy itself stresses that an `Engine` is intended to be created once per process, used concurrently, and manages many DBAPI connections via pooling; this typically improves performance vs repeatedly opening DB connections (which is a common Streamlit anti-pattern). citeturn24view0turn3view1

**ORM overhead is real when materializing many objects.** SQLAlchemy’s own performance FAQ includes dedicated guidance for result-fetching slowness and ORM-specific performance considerations, which is a signal that ORM object materialization can be a bottleneck for large datasets or heavy per-row logic. citeturn23view0turn8search13

**Reliable connection reuse matters more than micro-optimizing the query wrapper.** SQLAlchemy’s pooling docs describe “pre-ping” (`pool_pre_ping`) to test liveness on checkout (typically with a lightweight `SELECT 1`) and automatically recycle stale connections. This directly addresses a common production failure mode: stale connections in long-lived processes. citeturn24view2turn3view1

**Prepared statements and poolers can flip expected wins.** If you use Supabase transaction pooling, prepared statements must be disabled; some drivers (e.g., psycopg) auto-prepare unless configured otherwise. This can create runtime failures unless explicitly handled, and it can also change performance characteristics. citeturn3view3turn7view0turn11search6

### Maintainability and developer productivity

SQLAlchemy’s official positioning is that it has two components: **Core** and an optional **ORM**; many applications use Core only to keep “succinct and exact control over database interactions.” citeturn23view3turn24view0

In practice:

- **Direct SQL (driver cursors / pandas read_sql)** can be most maintainable for analytics-heavy Streamlit apps *if* you adopt conventions: centralized query strings, parameterization, and structured result mapping. This keeps control high and avoids ORM pitfalls like N+1 query patterns. citeturn21view0turn15search1  
- **SQLAlchemy Core** often improves maintainability without sacrificing query control by standardizing connection pooling, transactions, and parameter binding while still letting you write explicit SQL (`text(...)`) or build SQL expressions. citeturn24view0turn23view3  
- **SQLAlchemy ORM** tends to pay off when your app has a real domain model (relationships, invariants, repeated CRUD patterns) and you want centralized model definitions and session-based units of work—but you must be disciplined about result sizes and query patterns. citeturn23view0turn24view0  

### Query flexibility and control

A useful way to frame “flexibility” in this stack:

- **Maximum control:** direct SQL (especially for complex joins, CTE-heavy analytics, Postgres-specific features). citeturn11search0turn11search12  
- **High control with better ergonomics:** SQLAlchemy Core (`text`, expressions) while still being “king” for apps built around textual SQL/expression constructs. citeturn24view0  
- **Productive abstraction with caveats:** ORM when your workload is object-centric rather than set/analytics-centric. citeturn23view0  

### Compatibility with Streamlit caching and state

Streamlit’s built-in SQL connection type is already SQLAlchemy-based:

- Streamlit’s `SQLConnection` is backed by a SQLAlchemy engine; its `.query()` method supports caching and simple retries for read-only queries, and `.session` provides a SQLAlchemy Session for writes/transactions. citeturn3view2turn21view0  
- `st.connection` returns connections that are internally cached using `st.cache_resource`, and connections with global scope are shared between sessions. citeturn2search19turn20search6

This means: **even if you “don’t use SQLAlchemy,” you may still depend on it via Streamlit’s connection system.** citeturn3view2turn20search6

The most compatible pattern is to:
- cache the **engine/connection** as a resource (`st.connection` already does this), and
- cache **query results** as data keyed by `(sql, params, user_context_if_needed)` using TTL. citeturn20search6turn25view4turn21view0

### Recommended production usage patterns

A pragmatic, production-grade recommendation for Streamlit + Supabase Postgres:

**Default recommendation: use Streamlit `SQLConnection` (SQLAlchemy engine) + explicit SQL.**  
Use `conn.query()` for read-only workloads with TTL caching; it implements caching behavior identical to `st.cache_data`, and supports `params` for parameterized queries. citeturn21view0turn15search1

**Use `.session` only for explicit writes/transactions, and isolate writes behind user actions.**  
Streamlit’s docs recommend the context manager pattern for writes, transactions, and more complex operations. citeturn21view0

**Add SQLAlchemy ORM only when the app’s domain complexity justifies it.**  
If your app is a dashboard/explorer with mostly read queries and set-based transformations, ORM can reduce clarity and create performance hazards. If you have significant business logic and repeated CRUD patterns, ORM can increase productivity—just keep result sizes bounded and measure. citeturn23view0turn24view0turn11search0

**If you must use Supabase transaction pooling, enforce prepared-statement settings in one place.**  
Supabase requires prepared statements be disabled in transaction mode; ensure your driver/ORM is configured accordingly (e.g., psycopg `prepare_threshold=None`). citeturn3view3turn7view0turn11search6

## Deployment and scalability patterns that don’t break sessions

### Containerization and orchestration

Streamlit provides official deployment tutorials for Docker and Kubernetes. The Docker guide emphasizes containerizing first, then choosing a hosting environment; the Kubernetes guide builds on that containerization step. citeturn2search2turn13search1

### Horizontal scaling requires session-aware load balancing

Streamlit’s architecture docs explicitly state that, with load balancing or replication, some features will not work without session affinity/stickiness, and it provides mitigation strategies (session affinity, Base64 data URIs for media, or external file storage). citeturn14view0

Additionally, Streamlit’s server configuration includes a `cookieSecret` and notes that if deploying on multiple replicas, it should be set to the same value across replicas. citeturn19view0

**Operational implication:** if you scale replicas without sticky sessions, you should expect intermittent UI breakage and file/media issues. If you *do* enable stickiness, you still need to plan for pod eviction/restarts (session loss) and for the fact that in-memory caches are per-replica. citeturn14view0turn13search18

## Reliability, testing, and observability

### Reliability controls inside Streamlit configuration

Several Streamlit config options have direct production reliability impact:

- **CORS/XSRF protections** are enabled by default (`server.enableCORS = true`, `server.enableXsrfProtection = true`), and Streamlit notes they interact (if XSRF on and CORS off, Streamlit will enable both). citeturn19view0  
- **Disconnected session TTL** controls how long Streamlit may retain session artifacts after a WebSocket disconnect; Streamlit warns that with load balancing or replication you must enable stickiness to guarantee reconnection to the existing session. citeturn19view0turn14view0  
- Streamlit explicitly warns against using Streamlit’s built-in HTTPS options (`server.sslCertFile`, `server.sslKeyFile`) in production, recommending SSL termination at a load balancer/reverse proxy. citeturn19view0

### Database reliability: connection reuse, health checks, and pool sizing

On the Streamlit side, prefer caching connection resources and validating them:

- `st.cache_resource` provides a `validate` hook intended for verifying the health of cached resources like database connections. citeturn3view1  
- SQLAlchemy’s pooling recommends `pool_pre_ping` to detect and recycle dead connections on checkout. citeturn24view2  

On the Supabase side, connection capacity is engineered and limited:

- Supabase provides guidance on pool sizing and notes that pool size and connection limits depend on compute size; it also documents how Supavisor pool size and port behavior relate to session/transaction modes. citeturn11search10turn20search4turn20search17  
- Supabase provides a “Connection management” guide to observe/manage connection resources. citeturn20search8

### Testing strategy that matches Streamlit’s execution model

Streamlit offers a native app testing framework (`AppTest`) that runs headless tests, simulates user input, and inspects rendered output. This is designed specifically to test Streamlit code without browser automation overhead. citeturn15search3turn15search15turn15search7

A production-grade test pyramid for Streamlit typically includes:
- unit tests for pure service functions (fast, stable),
- integration tests for database queries as needed (ideally against a test DB),
- `AppTest` smoke tests for key pages and flows. citeturn15search7turn15search19

### Observability and security logging

Streamlit supports configurable logging level and message formats via `.streamlit/config.toml`. citeturn17view0  
For security-meaningful logging and monitoring practices (what to log, how to avoid leaking secrets, and how to make logs useful for incident response), the entity["organization","OWASP","web security nonprofit"] logging guidance is a solid baseline. citeturn15search2turn15search22

## Security hardening checklist for Streamlit + Supabase Postgres

### Secrets and credentials handling

- Use Streamlit secrets management (`st.secrets`) or environment variables; avoid committing secrets to git repositories. citeturn2search0turn2search12  
- For deployments, manage secrets outside code; Streamlit’s deployment docs reinforce this as a best practice. citeturn2search23turn2search12  

### Safe query construction and SQL injection resistance

- Use parameterized queries / prepared statements with variable binding rather than string concatenation; this is a core defense recommended by entity["organization","OWASP","web security nonprofit"]. citeturn15search1turn15search5  
- Streamlit’s `SQLConnection.query()` supports `params` and highlights that parameter syntax is driver-dependent (PEP 249 paramstyle). citeturn21view0

### Supabase-specific data protections

- Treat Supabase Row Level Security (RLS) as defense-in-depth; Supabase explicitly notes its value even when accessed through third-party tooling. citeturn12search7turn1search3  
- Understand Supabase API keys: the `service_role` key has full access and bypasses RLS; it should never be exposed to clients. This is critical even if Streamlit runs server-side, because accidental logging/printing or misdeployment can still leak secrets. citeturn1search7turn12search20  
- Optimize RLS performance by indexing columns used by policies; Supabase provides concrete examples and reports large improvements in some scenarios. citeturn12search3turn1search28  

### Network and transport protections

- Prefer TLS-encrypted connections; PostgreSQL supports SSL/TLS, and Supabase provides SSL enforcement guidance. citeturn12search15turn12search0  
- Use Supabase network restrictions (IP allowlists) where feasible for database connections and pooler connections. citeturn12search2turn12search17  

### Streamlit server hardening

- Keep CORS and XSRF protections enabled unless you have a well-understood edge proxy model and an explicit reason to change them. citeturn19view0  
- In production, do SSL termination at a reverse proxy/load balancer; Streamlit explicitly warns against using its built-in SSL options in production. citeturn19view0  
- When deploying multiple replicas, set a consistent `cookieSecret` across replicas and enforce session stickiness at the proxy. citeturn19view0turn14view0  

### A concrete, production-aligned database access pattern

Below is a production-oriented pattern that aligns Streamlit reruns with database efficiency:

```python
import streamlit as st

# Resource: once per process (Streamlit also caches st.connection internally)
conn = st.connection("sql")  # configured via secrets.toml

@st.cache_data(ttl=300)
def load_dashboard_data(status: str):
    # Prefer parameterized queries; cache is keyed by function args.
    return conn.query(
        "SELECT * FROM events WHERE status = :status ORDER BY created_at DESC LIMIT 500",
        params={"status": status},
        ttl=0,  # rely on st.cache_data for caching semantics
    )

status = st.selectbox("Status", ["active", "inactive"])
df = load_dashboard_data(status)
st.dataframe(df)
```

This combines:
- cached connection resource behavior (`st.connection` uses `st.cache_resource` internally), citeturn20search6  
- safe parameterization, citeturn15search1turn21view0  
- bounded result size and deterministic ordering (crucial for UI correctness), citeturn11search0  
- explicit caching TTL plus a clear invalidation story (`st.cache_data.clear()` or function `.clear()` after writes). citeturn25view4turn3view0  

**Bottom line on SQLAlchemy usage in this stack:** because Streamlit’s SQLConnection is SQLAlchemy-based, the production question is less “SQLAlchemy or not” and more “ORM or not.” For most Supabase-backed Streamlit apps, **SQLAlchemy Engine + explicit SQL (and Streamlit caching)** is the highest-performance, lowest-surprise baseline; only introduce the ORM when you have a domain model that genuinely benefits from it and you can enforce bounded result sets and disciplined query patterns. citeturn21view0turn23view0turn24view0turn3view3