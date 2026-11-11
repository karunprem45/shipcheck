# Multi-stage: build the Go gate, then run it next to the Python agent.
FROM golang:1.22 AS gate
WORKDIR /src
COPY gate/ .
RUN CGO_ENABLED=0 go build -o /shipcheck-gate .

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY agent/ agent/
COPY metrics/ metrics/
COPY gate/policy.json /app/policy.json
COPY --from=gate /shipcheck-gate /usr/local/bin/shipcheck-gate
RUN pip install --no-cache-dir anthropic bandit
WORKDIR /app/agent
ENTRYPOINT ["python", "-m", "shipcheck_agent.cli"]
