import express from "express";
import client from "prom-client";

const app = express();
app.use(express.json());

const counter = new client.Counter({ name: "upserts_total", help: "Upserts" });

app.post("/oauth/token", (_req, res) => {
  res.json({ access_token: "fake-token" });
});

app.post("/upsert", (req, res) => {
  counter.inc();
  console.log(
    JSON.stringify({
      message: "upsert",
      body: req.body,
      correlationId: req.headers["x-correlation-id"],
    }),
  );
  res.json({ ok: true });
});

app.get("/metrics", async (_req, res) => {
  res.set("Content-Type", "text/plain");
  res.send(await client.register.metrics());
});

app.listen(3002, () => console.log("salesforce mock on 3002"));
