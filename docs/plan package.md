
# Approved hardening overlay: [docs/specs/MIGRATION_HARDENING_PLAN.md](docs/specs/MIGRATION_HARDENING_PLAN.md)

# PLAN

## Plan intent

This plan covers the **first real delivery slice** of the backend:

* authenticated upload acceptance
* file persistence
* import batch + job creation
* SQS enqueue
* worker consumption
* job state tracking
* job status API
* audit emission
* route/version consistency

But the first task is **hardening**, not expansion.

---

## Phase 1 goal

Turn the current upload → batch/job → SQS → worker → job status path into a **safe, boring, traceable execution core**.

This phase does **not** include:

* import parsing
* turnover logic
* board APIs
* Redis
* AI
* automations
* real business processing

---

## Module boundaries

## Module 1 — Auth and request context

Owns:

* JWT verification
* `tenant_id` extraction
* `user_id` extraction
* request ID attachment
* request-scoped context object

Must not own:

* DB access
* upload orchestration
* queue behavior

Current status:

* already present
* keep, lightly validate, do not redesign unless needed

---

## Module 2 — Upload acceptance route

Owns:

* HTTP form parsing
* HTTP validation
* dependency injection
* response mapping

Must not own:

* hashing
* file storage
* DB orchestration
* SQS send
* audit writes

Current status:

* exists but too thick
* must be thinned

---

## Module 3 — Upload orchestration service

Owns:

* file hash computation
* file persistence call
* batch creation
* job creation
* enqueue call
* enqueue failure handling
* upload audit emission

Must not own:

* direct HTTP concerns
* worker execution
* board/business logic

Current status:

* partially present as `UploadService`
* must become the single owner of upload acceptance flow

---

## Module 4 — File storage adapter

Owns:

* local file path generation
* write bytes
* best-effort delete on rollback path
* return immutable `file_uri`

Must not own:

* metadata validation
* DB writes
* queue calls

Current status:

* currently embedded in route
* must be extracted

---

## Module 5 — Repositories and transactional persistence

Owns:

* batch insert
* job insert
* tenant-scoped reads
* state transitions
* atomic batch + job create
* valid state transition enforcement

Must not own:

* queue logic
* HTTP logic
* file logic

Current status:

* exists, but:

  * batch + job create are split
  * repositories open separate DB connections
  * schema side effects exist in constructors
* first fix is transactional consistency, not redesign of the whole persistence layer

---

## Module 6 — Queue transport

Owns:

* send message
* receive messages
* delete message

Must not own:

* payload meaning
* retries policy decisions
* job state changes

Current status:

* exists and is acceptable as transport-only

---

## Module 7 — Worker execution

Owns:

* payload validation
* job lookup
* conditional job claiming
* state transitions during execution
* ack/no-ack decision support

Must not own:

* business import logic yet
* route concerns
* upload logic

Current status:

* exists but unsafe
* this is the highest-priority hardening module

---

## Module 8 — Job status API

Owns:

* tenant-scoped job lookup
* response mapping for job state

Must not own:

* repository mutation
* recovery logic

Current status:

* exists and is mostly acceptable

---

## Module 9 — Audit

Owns:

* append-only audit emission for upload acceptance

Must not own:

* route orchestration
* business branching

Current status:

* exists but is duplicated across route and service
* must be consolidated

---

## Module 10 — API surface consistency

Owns:

* consistent version prefix for product routes
* unversioned health/readiness
* removal of duplicate health story

Current status:

* inconsistent
* must be normalized now before clients grow around bad paths

---

# Data flow

## Current desired flow after hardening

1. Client sends authenticated multipart upload request
2. Route validates HTTP input and request context
3. Route calls one upload service method
4. Service computes file hash
5. Service persists file through storage adapter
6. Service creates import batch and job in one DB transaction
7. Service sends SQS message
8. If enqueue fails:

   * service marks job as `failed`
   * service returns failure to route
9. If enqueue succeeds:

   * service emits single audit event
   * service returns `job_id` and `batch_id`
10. Route returns accepted response
11. Worker receives message
12. Worker validates payload
13. Worker loads job and checks current state
14. Worker claims job with valid transition `queued → running`
15. Worker executes stub processing
16. Worker transitions `running → completed`
17. Worker deletes message only on valid terminal outcome
18. Client polls job status endpoint

---

# Risks and failure points

## 1. Message loss

Current risk:

* worker deletes messages on failure paths

Plan response:

* no unconditional delete
* delete only on success, invalid payload, or confirmed missing job

---

## 2. DB and queue inconsistency

Current risk:

* batch/job can exist without queue message

Plan response:

* atomic batch + job transaction
* enqueue after commit
* if enqueue fails, mark job `failed`

---

## 3. Thick route regression

Current risk:

* upload route keeps becoming the orchestrator

Plan response:

* route calls one service method only
* all upload flow orchestration moves to service

---

## 4. Duplicate message delivery

Current risk:

* worker can re-run terminal jobs

Plan response:

* worker reads job first
* terminal states become idempotent no-op + ack

---

## 5. Undefined failure semantics

Current risk:

* system behavior is unclear when queue, DB, or worker fails

Plan response:

* explicitly define behavior per failure path in pseudocode

---

## 6. Audit duplication

Current risk:

* route and service both emit upload-related audit

Plan response:

* only upload service emits upload acceptance audit

---

## 7. API contract drift

Current risk:

* `/v1/me` but `/uploads` and `/jobs` unversioned

Plan response:

* all product routes under `/v1`
* health/readiness stay unversioned

---

# Pseudocode blocks

## PSEUDOCODE: request_context

```text
1. Receive HTTP request
2. Extract bearer token
3. Validate JWT using configured verifier
4. If token invalid, return 401
5. Extract user_id from sub claim
6. Extract tenant_id from tenant claim
7. If tenant_id missing, return 403
8. Read request_id from request context storage
9. Return RequestContext(user_id, tenant_id, request_id)
```

## PSEUDOCODE: upload_route

```text
1. Receive multipart upload request
2. Resolve RequestContext
3. Validate file exists and filename is present
4. Parse metadata_json
5. If metadata_json is not valid JSON object, return 400
6. Read file bytes
7. If file is empty, return 400
8. Call UploadService.accept_upload with context, filename, metadata, and file bytes
9. If service raises enqueue or persistence failure, return error with request_id
10. Return job_id, batch_id, request_id
```

## PSEUDOCODE: upload_service_accept_upload

```text
1. Receive tenant_id, user_id, request_id, filename, file_bytes, metadata
2. Compute file hash
3. Persist file using storage adapter
4. If file persistence fails, raise error
5. Create ImportBatch and Job models
6. Persist batch and job in one database transaction
7. If DB transaction fails, best-effort delete stored file and raise error
8. Build job payload with required fields
9. Send message to SQS
10. If SQS send fails, transition job from queued to failed with enqueue error and raise error
11. Emit single upload_accepted audit event
12. Return job_id and batch_id
```

## PSEUDOCODE: transactional_batch_and_job_create

```text
1. Receive batch model and job model
2. Open one database transaction
3. Insert import batch
4. Insert job with state queued
5. Commit transaction
6. Return persisted batch and job identifiers
```

## PSEUDOCODE: worker_loop

```text
1. Poll SQS for messages
2. For each message, parse body
3. Validate required payload fields
4. If payload invalid, log and delete message
5. Call execute_message
6. If execute_message returns success or idempotent terminal no-op, delete message
7. If execute_message raises, do not delete message
8. Continue polling
```

## PSEUDOCODE: execute_message

```text
1. Receive valid payload
2. Load job by tenant_id and job_id
3. If job does not exist, log and signal non-retryable missing job
4. If job state is completed or failed, return idempotent no-op
5. Transition queued to running using conditional state update
6. If claim fails, reload job
7. If job is terminal, return idempotent no-op
8. Perform stub processing only
9. Transition running to completed
10. Return success
11. If any unexpected error occurs after claim, raise error
```

## PSEUDOCODE: conditional_state_transition

```text
1. Receive tenant_id, job_id, allowed_from states, target state, optional error
2. Update row only if current state is in allowed_from
3. If no row updated, return no result
4. Return updated job row
```

## PSEUDOCODE: job_status_route

```text
1. Receive job_id and RequestContext
2. Load job by tenant_id and job_id
3. If no job found, return 404
4. Return job_id, status, timestamps, error, request_id
```

## PSEUDOCODE: upload_audit

```text
1. Receive tenant_id, user_id, batch_id, job_id, request_id
2. Append upload_accepted audit record once
3. Return success
```

## PSEUDOCODE: api_prefix_normalization

```text
1. Review mounted product routers
2. Apply one shared product prefix /v1
3. Keep health and readiness unversioned
4. Remove duplicate health surface or mark one as dead code to remove
5. Return normalized route map
```

---

# Execution order

## Step 1

Worker safety

Why first:

* current system can lose work

## Step 2

Upload service ownership

Why second:

* route must stop being orchestrator before behavior grows

## Step 3

Transactional batch + job creation

Why third:

* consistency must exist before real work is added

## Step 4

State transition enforcement

Why fourth:

* duplicate delivery and invalid transitions must be blocked

## Step 5

Audit consolidation

Why fifth:

* remove duplicate side effects once flow ownership is clear

## Step 6

API consistency cleanup

Why sixth:

* normalize contract before external clients depend on it

---

# Phase 1 completion criteria

Phase 1 is done when all of these are true:

* upload route only handles HTTP concerns
* one upload service method owns file → DB → queue → audit flow
* batch and job are created atomically
* enqueue failure marks job failed
* worker no longer deletes messages on execution failure
* terminal jobs are idempotent on redelivery
* job status endpoint reflects truthful state
* only one upload acceptance audit event is emitted
* product routes use one version prefix
* health/readiness remain unversioned
