import json
import logging
import uuid
from fastapi import FastAPI, Depends, Header
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

from .db import SessionLocal, engine
from . import models
from .pubsub_client import publish_order

models.Base.metadata.create_all(bind=engine)

app = FastAPI()
REQUEST_COUNT = Counter("requests_total", "Total requests")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("partner-app")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/orders")
def create_order(
    order: dict,
    db: Session = Depends(get_db),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    correlation_id: str
    | None = Header(default=None, alias="X-Correlation-ID"),
):
    REQUEST_COUNT.inc()
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    existing = (
        db.query(models.Order)
        .filter_by(idempotency_key=idempotency_key)
        .first()
    )
    if existing:
        return existing.__dict__
    db_order = models.Order(
        product=order.get("product"), idempotency_key=idempotency_key
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    publish_order(
        {
            "id": db_order.id,
            "product": db_order.product,
            "correlationId": correlation_id,
        }
    )
    logger.info(
        json.dumps(
            {"message": "order created", "correlationId": correlation_id}
        )
    )
    return db_order.__dict__


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
