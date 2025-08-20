export function log(message: string, correlationId?: string) {
  const payload: any = { message };
  if (correlationId) payload.correlationId = correlationId;
  console.log(JSON.stringify(payload));
}
