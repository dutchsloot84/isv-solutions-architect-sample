import client from "prom-client";

export const processed = new client.Counter({
  name: "messages_processed_total",
  help: "Messages processed",
});

export function metrics() {
  return client.register.metrics();
}
