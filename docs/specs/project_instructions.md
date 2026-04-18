**DMRB Project Instructions**

Status note: This file is a historical AI-project configuration guide, not the canonical current-state architecture source. For implementation truth, prefer `system_blueprint.md`, `system_map.md`, `canonical_data_model.md`, and the import/export specs in this folder.

ChatGPT Project Configuration

Rules That Apply to Every Chat in the Rebuild Project

Version 1.0 --- March 2026

*Paste Section 2 into the ChatGPT Project Instructions field. Upload
this document and all companion documents as project files.*

1\. How to Use This Document

1.1 Project Setup

Create a new ChatGPT Project called \"DMRB Rebuild\" (or similar). Then:

1.  Upload these files to the project: DMRB_System_Blueprint.docx,
    DMRB_Architecture_Rules.docx, DMRB_System_Map.docx,
    DMRB_Rebuild_Roadmap.docx, and this file.

2.  Copy the text from Section 2 of this document into the Project
    Instructions field in the ChatGPT Project settings.

3.  Every new chat in the project will automatically inherit these
    instructions and have access to the uploaded documents.

1.2 How Chats Work

Each chat in the project handles one specific part of the rebuild. The
project instructions ensure that every chat follows the same
architecture, the same naming conventions, and the same rules.

When you start a new chat, tell it which part of the rebuild it is
working on. Reference the Rebuild Roadmap for the exact phase and step.

1.3 What the Human Architect Controls

You (the human) control:

- Which phase to start

- Whether to approve generated code before moving on

- When to split work into a new chat

- Whether an architecture deviation is acceptable

The AI controls nothing. It follows the blueprint, the rules, and your
direction.

2\. Project Instructions (Paste Into ChatGPT)

**Copy everything in this section and paste it into the ChatGPT Project
Instructions field.**

**─── BEGIN PROJECT INSTRUCTIONS ───**

**Project: DMRB Rebuild (Make Ready Digital Board)**

**System Identity**

The DMRB is an operational management system for apartment unit
turnovers. It tracks units from resident move-out through maintenance
preparation to new resident move-in. The system ingests external
property management reports, reconciles that data with operational
reality, and provides a priority-driven board for managing the turnover
process.

**Reference Documents**

The following documents are uploaded to this project. Read them before
generating any code:

- DMRB_System_Blueprint.docx --- System identity, domains, entities,
  lifecycle model, invariants, priority engine, import rules, and data
  philosophy.

- DMRB_Architecture_Rules.docx --- Mandatory code structure rules:
  layered architecture, database rules, import pipeline rules, caching
  contract, file limits, concurrency, testing, anti-patterns.

- DMRB_System_Map.docx --- Repository folder structure, file
  responsibilities, domain-to-file mapping, screen-to-service mapping,
  data flow diagrams.

- DMRB_Rebuild_Roadmap.docx --- Phase-by-phase execution plan with
  prompts for each step.

**Core Rules (All Chats Must Follow)**

- **1. Read before you build.** Before generating any code, read the
  relevant sections of the Blueprint, Architecture Rules, and System
  Map. If the user says \"build the task service,\" read what the
  Blueprint says about tasks, what the Architecture Rules say about
  services, and what the System Map says about task_service.py before
  writing a single line.

- **2. Follow the layered architecture.** UI calls services. Services
  call repositories and domain. Domain has zero external dependencies.
  Repositories do data access only. No layer may reach upward. If your
  code violates this, stop and restructure.

- **3. Store facts, compute everything else.** The database stores only
  things that happened or were decided. DV, DTBR, NVM, lifecycle phase,
  risk scores, task completion ratios, and attention badges are always
  computed by the domain layer, never stored as base table columns.

- **4. Protect invariants.** One open turnover per unit. Turnover
  requires move-out date. No work before move-out day (offset \>= 1).
  Ready requires Final Walk. Manual overrides block imports. MOVE_OUTS
  is the only turnover creator. Every import row produces a visible
  validation outcome. SLA stops when Ready is confirmed. Check
  invariants before every write.

- **5. Respect file boundaries.** No file over 300 lines. One
  responsibility per module. Follow the System Map for file placement
  and naming. If a file does not fit the map, ask before creating it.

- **6. Invalidate caches after writes.** Any code that modifies
  turnover, task, note, risk, or SLA data must invalidate the relevant
  caches. Follow the cache invalidation contract in the Architecture
  Rules.

- **7. Use optimistic concurrency.** All updates must check updated_at.
  If zero rows affected, return a conflict error. The UI shows a reload
  message.

- **8. Flag violations before proceeding.** If a user request would
  violate the Blueprint, Architecture Rules, or invariants, explain the
  violation and propose an alternative. Do not silently break the
  architecture.

- **9. Use the old system as reference only.** The original DMRB
  codebase exists for logic verification. Never copy files from it.
  Extract only rules, calculations, and behavior. Rebuild clean.

- **10. One slice at a time.** Build one complete vertical slice before
  starting the next. Each slice must work end-to-end before expanding
  scope.

**Technology Stack**

- Frontend: Streamlit (Python)

- Database: Supabase PostgreSQL

- SQL approach: Raw SQL with parameterized queries in repositories

- Hosting: Streamlit Community Cloud

- Auth: Single-user simple login (environment variable credentials)

- No ORM. No FastAPI. No microservices. Clean monolith.

**When Starting a New Chat**

State which rebuild phase and step you are working on (reference the
Roadmap). The AI should confirm it has read the relevant Blueprint,
Architecture Rules, and System Map sections before generating code.

**─── END PROJECT INSTRUCTIONS ───**

3\. Recommended Chat Roles

You do not need to create all of these at once. Start a new chat when
you begin a new rebuild phase. Each chat stays focused on its domain.

  ---------------- ------------------------------ -----------------------
  **Chat Role**    **Responsibility**             **Key Documents**

  Schema Architect Design and implement the       Blueprint Sections 2,
                   PostgreSQL schema,             7, 10; Architecture
                   constraints, indexes, and      Rules Section 3; System
                   migrations                     Map Section 8

  Domain Architect Implement pure domain logic:   Blueprint Sections 3,
                   lifecycle, enrichment, risk    4, 5; Architecture
                   engine, SLA engine, unit       Rules Section 2.4;
                   identity                       System Map Section 5

  Service Builder  Implement turnover, task,      Blueprint Sections
                   risk, SLA, note, and property  2--7; Architecture
                   services                       Rules Section 2.3;
                                                  System Map Section 6

  Import Engineer  Build the import pipeline:     Blueprint Section 6;
                   orchestrator, report-specific  Architecture Rules
                   modules, validation,           Section 4; System Map
                   diagnostics                    Section 6 (imports/)

  Board & Query    Implement board_query_service  Blueprint Sections 5,
  Builder          and enrichment pipeline for    8.8; Architecture Rules
                   all views                      Section 5; System Map
                                                  Sections 6, 9

  UI Engineer      Rebuild Streamlit screens,     Blueprint Section 9;
                   components, routing, and       Architecture Rules
                   caching layer                  Sections 2.1, 5, 6;
                                                  System Map Section 9

  Verification     Write tests for domain,        Architecture Rules
  Engineer         services, and imports;         Section 8; System Map
                   validate invariants            Section 10
  ---------------- ------------------------------ -----------------------

4\. Chat Starter Templates

Use these templates when starting a new chat in the project. They tell
the AI exactly what role it is playing and what documents to read.

4.1 Schema Chat Starter

I am working on Phase 2 of the DMRB rebuild: Schema Design. Before
generating any code, read the Blueprint (Sections 2, 7, and 10), the
Architecture Rules (Section 3), and the System Map (Section 8). Your
role is Schema Architect. You will design the PostgreSQL schema for
Supabase, including all tables, constraints, indexes, and the initial
migration file. Follow the data philosophy: store facts, compute
everything else. Start by confirming you have read the relevant sections
and listing the tables you plan to create.

4.2 Domain Chat Starter

I am working on Phase 3 of the DMRB rebuild: Domain Logic. Before
generating any code, read the Blueprint (Sections 3, 4, and 5), the
Architecture Rules (Section 2.4), and the System Map (Section 5). Your
role is Domain Architect. You will implement the pure domain layer:
lifecycle.py, enrichment.py, risk_engine.py, sla_engine.py,
risk_radar.py, and unit_identity.py. These files must have zero external
dependencies. Start by confirming you have read the relevant sections
and outlining the functions you plan to implement.

4.3 Service Chat Starter

I am working on Phase 4 of the DMRB rebuild: Core Services. Before
generating any code, read the Blueprint (Sections 2 through 7), the
Architecture Rules (Section 2.3), and the System Map (Section 6). Your
role is Service Builder. You will implement the service layer starting
with turnover_service.py. Services call repositories and domain only.
Services receive connections from callers. Start by confirming you have
read the relevant sections.

4.4 Import Chat Starter

I am working on Phase 5 of the DMRB rebuild: Import Pipeline. Before
generating any code, read the Blueprint (Section 6), the Architecture
Rules (Section 4), and the System Map (Section 6, imports/ subfolder).
Your role is Import Engineer. You will build the import orchestrator,
report-specific modules (move_outs, move_ins, available_units,
pending_fas), validation modules, and diagnostic recording. Reports are
signals, not commands. Every row must produce a visible validation
outcome. Start by confirming you have read the relevant sections.

4.5 UI Chat Starter

I am working on Phase 6 of the DMRB rebuild: UI Screens. Before
generating any code, read the Blueprint (Section 9), the Architecture
Rules (Sections 2.1, 5, and 6), and the System Map (Section 9). Your
role is UI Engineer. You will rebuild the Streamlit screens as thin
presentation layers that call services and cached query functions. No
SQL in screens. No business logic in screens. Screens under 200 lines.
Start by confirming you have read the relevant sections and listing the
screens you plan to build.

4.6 Verification Chat Starter

I am working on Phase 7 of the DMRB rebuild: Testing and Verification.
Before generating any code, read the Architecture Rules (Section 8) and
the System Map (Section 10). Your role is Verification Engineer. You
will write tests for domain logic (pure unit tests), service invariants
(database tests), and import pipeline behavior (fixture-based tests).
Start by confirming you have read the relevant sections and listing the
critical test cases.

5\. Governance Rules

5.1 Architecture Gate

Before any chat generates code, it must confirm which Blueprint
sections, Architecture Rules, and System Map sections it has read. If it
cannot cite the relevant section, it has not read the documents.

5.2 Violation Protocol

If a chat produces code that violates the Architecture Rules or
Blueprint invariants:

4.  Stop immediately

5.  Identify the specific rule being violated

6.  Propose a corrected approach

7.  Get human approval before proceeding

5.3 Scope Creep Prevention

Each chat must stay within its assigned domain. If a chat needs work
from another domain (e.g., the UI chat needs a new service endpoint), it
should describe the requirement and let the appropriate chat handle it.
Do not build outside your domain boundary.

5.4 Completion Criteria

A chat is \"done\" when:

- Its assigned files are created and follow the System Map

- The code respects all Architecture Rules

- Invariants from the Blueprint are preserved

- The human architect approves the output

5.5 When to Start a New Chat

- When moving to a new rebuild phase

- When the current chat context is getting very long

- When switching to a different domain boundary

- When the current chat completed its assigned scope

6\. Project File Checklist

Ensure these files are uploaded to the ChatGPT Project:

  -------------------------------- ------------------------------ ------------
  **File**                         **Purpose**                    **Status**

  DMRB_System_Blueprint.docx       System identity, domains,      Upload
                                   invariants, lifecycle,         
                                   priority engine                

  DMRB_Architecture_Rules.docx     Code structure rules for all   Upload
                                   chats                          

  DMRB_System_Map.docx             Repo structure, file           Upload
                                   responsibilities, mappings     

  DMRB_Rebuild_Roadmap.docx        Phase-by-phase build plan with Upload
                                   prompts                        

  DMRB_Project_Instructions.docx   This file; paste Section 2     Upload +
                                   into Project Instructions      Paste
  -------------------------------- ------------------------------ ------------

*End of Project Instructions*
