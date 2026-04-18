# User Data Flow Diagram

This diagram tracks the interactive journey of a Service Manager through the DMRB system, from authentication and scope selection to operational execution and manual data overrides.

```mermaid
flowchart TD

%% --- User Entry Points ---
subgraph User
    Manager[Service Manager]
end

%% --- Screens / Pages ---
subgraph UI_Screens
    Login[Login Screen]
    Dashboard[DMRB Board / Morning Workflow]
    Sidebar[Global Sidebar]
    UnitDetail[Unit Detail View]
    TaskPanel[Task Execution Panel]
end

%% --- User_Actions ---
subgraph User_Actions
    SelectPhase[Select Property/Phase]
    SearchUnit[Search / Unit Lookup]
    MarkComplete[Mark Task as Completed]
    EditDates[Manually Override Dates]
end

%% --- System Responses ---
subgraph System_Responses
    LoadBoard[Filter & Load Board Units]
    CreateTO[Auto-Create On-Notice Turnovers]
    SLA_Risk[Recalculate SLA & Risk Flags]
end

%% --- Data Touched ---
subgraph Data_Layer
    DB_User[(app_user)]
    DB_TO[(turnover)]
    DB_Task[(task)]
    DB_Audit[(audit_log)]
    Session[Streamlit Session State]
end

%% --- Flow ---
Manager -- "Enters credentials" --> Login
Login -- "Submit Login" --> DB_User
DB_User -- "Auth Success" --> Session

Manager -- "Selects scope" --> Sidebar
Sidebar -- "Select Phase" --> Session
Session -- "FILTER [implicit]" --> LoadBoard

LoadBoard -- "Trigger: [implicit] on-notice sync" --> CreateTO
CreateTO -- "WRITE (New Turnovers)" --> DB_TO
CreateTO -- "WRITE (Creation Audit)" --> DB_Audit

Manager -- "Scans Board" --> Dashboard
Dashboard -- "Select Unit" --> UnitDetail

Manager -- "Executes Work" --> TaskPanel
TaskPanel -- "Mark Task Complete" --> MarkComplete
MarkComplete -- "USER_WRITE (completion date)" --> DB_Task
MarkComplete -- "WRITE (Task Audit)" --> DB_Audit
MarkComplete -- "Trigger Readiness Update" --> SLA_Risk

Manager -- "Corrects report error" --> UnitDetail
UnitDetail -- "Manual Override" --> EditDates
EditDates -- "USER_WRITE (Set override timestamp)" --> DB_TO
EditDates -- "WRITE (Field Audit)" --> DB_Audit
EditDates -- "Recalculate Priority" --> SLA_Risk

SLA_Risk -- "WRITE (Risk markers)" --> DB_TO
SLA_Risk -- "Refresh UI" --> Dashboard
```
