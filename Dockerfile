# Build stage
FROM python:3.11-slim AS build
WORKDIR /app
RUN pip install uv
COPY pyproject.toml .
COPY src/ src/
RUN uv pip install --system --no-cache .

# Runtime stage
FROM python:3.11-slim
WORKDIR /app
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin/pmmcp /usr/local/bin/pmmcp
COPY src/ src/

# Lock in the Python invocation → args from podman run append to it
ENTRYPOINT ["python", "-m", "pmmcp"]

# Optional: default flags if you want any when no args are passed
# (usually leave as empty list for pure CLI tool)
CMD []
