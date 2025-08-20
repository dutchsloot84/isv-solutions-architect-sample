import express from "express";
import { PORT } from "./config";
import { metrics } from "./metrics";
import { listen } from "./subscriber";
import { enableFailure } from "./faultToggle";

const app = express();
app.get("/metrics", async (_req, res) => {
  res.set("Content-Type", "text/plain");
  res.send(await metrics());
});

app.post("/simulate-error", (_req, res) => {
  enableFailure(true);
  res.json({ ok: true });
});

app.delete("/simulate-error", (_req, res) => {
  enableFailure(false);
  res.json({ ok: true });
});

app.listen(PORT, () => console.log(`integration hub on ${PORT}`));
listen();
