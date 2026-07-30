FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN python -m pip install --no-cache-dir "PyYAML>=6.0,<7.0"
COPY runner/ /app/runner/

USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["python", "/app/runner/container_commit_service.py"]
