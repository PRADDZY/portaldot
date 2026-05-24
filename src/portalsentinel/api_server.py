from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from portalsentinel.api import make_router
from portalsentinel.bootstrap import build_service
from portalsentinel.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    service = build_service(settings)
    app = FastAPI(title="PortalSentinel API", version="0.1.0")
    app.include_router(make_router(service))
    return app


def main() -> None:
    settings = get_settings()
    uvicorn.run("portalsentinel.api_server:create_app", factory=True, host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    main()

