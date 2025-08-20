FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install .
COPY partner_app ./partner_app
CMD ["uvicorn", "partner_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
