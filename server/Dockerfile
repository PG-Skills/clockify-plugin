FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml ./
COPY src ./src
RUN uv pip install --system .
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/.well-known/oauth-authorization-server').status==200 else 1)"
CMD ["python", "-m", "clockify_mcp.serve"]
