from __future__ import annotations

import logging
import os

import fastmcp
from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from contract_risk_analyzer.tools.compare_contracts import compare_contracts
from contract_risk_analyzer.tools.extract_clauses import extract_clauses
from contract_risk_analyzer.tools.flag_risk_terms import flag_risk_terms
from contract_risk_analyzer.tools.summarize_obligations import summarize_obligations

logger = logging.getLogger("contract_risk_analyzer.server")

mcp = FastMCP("contract-risk-analyzer")


def _configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _log_http_routes(app) -> None:
    for i, route in enumerate(app.routes):
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        logger.info(
            "HTTP route[%s] %s path=%r methods=%r",
            i,
            type(route).__name__,
            path,
            sorted(methods) if methods else methods,
        )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request; highlight 404s for MCP path debugging."""

    async def dispatch(self, request: Request, call_next):
        logger.info(
            "request %s %s client=%s",
            request.method,
            request.url.path,
            request.client.host if request.client else None,
        )
        response = await call_next(request)
        if response.status_code == 404:
            logger.warning(
                "response 404 for %s %s (check MCP client base URL vs streamable_http_path)",
                request.method,
                request.url.path,
            )
        else:
            logger.info(
                "response %s for %s %s",
                response.status_code,
                request.method,
                request.url.path,
            )
        return response


_configure_logging()


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@mcp.tool()
async def extract_clauses_tool(file_path: str, clause_type: str):
    return await extract_clauses(file_path=file_path, clause_type=clause_type)


@mcp.tool()
def flag_risk_terms_tool(file_path: str):
    return flag_risk_terms(file_path=file_path)


@mcp.tool()
def summarize_obligations_tool(file_path: str):
    return summarize_obligations(file_path=file_path)


@mcp.tool()
def compare_contracts_tool(file_path_a: str, file_path_b: str):
    return compare_contracts(file_path_a=file_path_a, file_path_b=file_path_b)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    http_path = fastmcp.settings.streamable_http_path

    logger.info("Starting FastMCP server module file=%s", __file__)
    logger.info(
        "FastMCP settings: streamable_http_path=%r transport=%r stateless_http=%r host=%r port=%r",
        http_path,
        fastmcp.settings.transport,
        fastmcp.settings.stateless_http,
        host,
        port,
    )

    preview = mcp.http_app(transport="http", path=http_path)
    _log_http_routes(preview)

    mcp.run(
        transport="http",
        host=host,
        port=port,
        path=http_path,
        log_level=os.getenv("UVICORN_LOG_LEVEL", "info"),
        middleware=[Middleware(RequestLoggingMiddleware)],
        uvicorn_config={"access_log": True},
    )

