export const TASK_COLS = [
  "INSPECT",
  "CARPET_BID",
  "MAKE_READY_BID",
  "PAINT",
  "MAKE_READY",
  "HOUSEKEEPING",
  "CARPET_CLEAN",
  "FINAL_WALK",
  "QUALITY_CONTROL",
] as const;

export const TASK_DISPLAY: Record<string, string> = {
  INSPECT: "Inspection",
  CARPET_BID: "Carpet Bid",
  MAKE_READY_BID: "Make Ready Bid",
  PAINT: "Paint",
  MAKE_READY: "Make Ready",
  HOUSEKEEPING: "Housekeeping",
  CARPET_CLEAN: "Carpet Clean",
  FINAL_WALK: "Final Walk",
  QUALITY_CONTROL: "Quality Control",
  CARPET: "Carpet",
  CLEAN: "Cleaning",
  APPLIANCE_CHECK: "Appliance Check",
};

export const STATUS_OPTIONS = [
  "Vacant ready",
  "Vacant not ready",
  "On notice",
] as const;

export const EXEC_MAP: Record<string, string> = {
  NOT_STARTED: "Not Started",
  SCHEDULED: "Scheduled",
  IN_PROGRESS: "In Progress",
  COMPLETED: "Completed",
};

export const EXEC_REV: Record<string, string> = {
  ...Object.fromEntries(Object.entries(EXEC_MAP).map(([key, value]) => [value, key])),
  "N/A": "COMPLETED",
  Canceled: "COMPLETED",
};

export const EXEC_LABELS = ["Not Started", "Scheduled", "In Progress", "Completed"] as const;

export const EXEC_LABELS_EXTENDED = [
  "Not Started",
  "Scheduled",
  "In Progress",
  "Completed",
  "N/A",
  "Canceled",
] as const;

export const BLOCK_OPTIONS = [
  "Not Blocking",
  "—",
  "Key Delivery",
  "Vendor Delay",
  "Parts on Order",
  "Permit Required",
  "Other",
] as const;

export const WD_OPTS = ["No", "Yes", "Yes stack"] as const;

export const NOTE_SEVERITIES = ["INFO", "WARNING", "CRITICAL"] as const;

export const READINESS_LABELS: Record<string, string> = {
  READY: "Ready",
  IN_PROGRESS: "In Progress",
  NOT_STARTED: "Not Started",
  BLOCKED: "Blocked",
  NO_TASKS: "No Tasks",
};
