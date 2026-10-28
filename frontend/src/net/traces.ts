/**
 * Links to a model attempt's trace, in Langfuse or Jaeger, when the Host set
 * VITE_TRACE_URL (for example https://cloud.langfuse.com/project/<id>/traces/{traceId}).
 */
export function traceUrl(traceId: string | null): string | null {
  const template = import.meta.env.VITE_TRACE_URL as string | undefined;
  return template && traceId ? template.replace("{traceId}", traceId) : null;
}
