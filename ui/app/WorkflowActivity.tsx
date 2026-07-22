export function workflowIsProcessing(status?: string) {
  if (!status) return false;
  return status.endsWith("_running") || status === "submission_in_progress";
}

export function workflowActivityLabel(status?: string) {
  if (!status) return "Working";
  if (status === "submission_in_progress") return "Submission in progress";
  const subject = status.replace(/_(requested|running)$/, "").replaceAll("_", " ");
  return `${subject.replace(/\b\w/g, letter => letter.toUpperCase())} in progress`;
}

export function WorkflowActivity({ status }: { status?: string }) {
  if (!workflowIsProcessing(status)) return null;
  return <span className="workflow-activity" role="status"><i aria-hidden="true"/>{workflowActivityLabel(status)}</span>;
}
