"""Entrypoint HTTP. Bind 0.0.0.0 para o Traefik (host-mode) alcançar o container."""

from .app import mcp


def main():
    mcp.run(transport="http", host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
