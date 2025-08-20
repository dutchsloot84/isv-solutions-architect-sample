import { PubSub } from "@google-cloud/pubsub";
import { PROJECT_ID, SUBSCRIPTION } from "./config";
import { upsert } from "./salesforceClient";
import { log } from "./logger";
import { processed } from "./metrics";
import { failureEnabled } from "./faultToggle";

const pubsub = new PubSub({ projectId: PROJECT_ID });
const sub = pubsub.subscription(SUBSCRIPTION);
const dlq = pubsub.topic("orders-dlq");

export function listen() {
  sub.on("message", async (m) => {
    const data = JSON.parse(m.data.toString());
    const corr = data.correlationId;
    try {
      if (failureEnabled()) throw new Error("simulated");
      await upsert(data, corr);
      processed.inc();
      log("processed message", corr);
      m.ack();
    } catch (err) {
      await dlq.publishMessage({ json: data });
      log("failed message", corr);
      m.ack();
    }
  });
}
