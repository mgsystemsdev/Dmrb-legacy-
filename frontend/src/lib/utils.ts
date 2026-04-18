export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }

  return new Date(value).toLocaleDateString();
}

export function formatTaskCompletion(
  completion: [number, number] | null | undefined,
): string {
  if (!completion) {
    return "—";
  }

  return `${completion[0]}/${completion[1]}`;
}
