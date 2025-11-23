"""
Reverse proxy routes to forward requests to secondary services.
This allows the main app to proxy requests to sqlite_web (8081),
WebDAV (8082), and S3 backup (8083) services, enabling operation
behind a single Apache/nginx reverse proxy.
"""

import logging
import httpx
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Service endpoints (internal)
SERVICES = {
    "db-browser": {"host": "127.0.0.1", "port": 8081},
    "s3-backup": {"host": "127.0.0.1", "port": 8083},
}

# Timeout for proxy requests
PROXY_TIMEOUT = 30.0


async def proxy_request(request: Request, service_name: str, path: str) -> Response:
    """Proxy a request to an internal service."""
    if service_name not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Unknown service: {service_name}")

    service = SERVICES[service_name]
    target_url = f"http://{service['host']}:{service['port']}/{path}"

    # Build headers, excluding hop-by-hop headers
    headers = {}
    for key, value in request.headers.items():
        key_lower = key.lower()
        if key_lower not in ('host', 'connection', 'keep-alive', 'transfer-encoding',
                             'te', 'trailer', 'upgrade', 'proxy-authorization',
                             'proxy-authenticate'):
            headers[key] = value

    # Add forwarding headers
    client_host = request.client.host if request.client else "unknown"
    headers['X-Forwarded-For'] = client_host
    headers['X-Forwarded-Proto'] = request.url.scheme
    headers['X-Forwarded-Host'] = request.headers.get('host', '')

    try:
        async with httpx.AsyncClient(timeout=PROXY_TIMEOUT) as client:
            # Get request body
            body = await request.body()

            # Forward the request
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                params=request.query_params,
                follow_redirects=False
            )

            # Build response headers, excluding hop-by-hop headers
            response_headers = {}
            for key, value in response.headers.items():
                key_lower = key.lower()
                if key_lower not in ('transfer-encoding', 'connection', 'keep-alive'):
                    response_headers[key] = value

            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response_headers,
                media_type=response.headers.get('content-type')
            )

    except httpx.TimeoutException:
        logger.error(f"Timeout proxying to {service_name}: {target_url}")
        raise HTTPException(status_code=504, detail=f"Service timeout: {service_name}")
    except httpx.ConnectError:
        logger.error(f"Connection error proxying to {service_name}: {target_url}")
        raise HTTPException(status_code=502, detail=f"Service unavailable: {service_name}")
    except Exception as e:
        logger.error(f"Error proxying to {service_name}: {e}")
        raise HTTPException(status_code=502, detail=str(e))


# Database Browser (sqlite_web) proxy
@router.api_route("/db-browser/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def proxy_db_browser(request: Request, path: str = ""):
    """Proxy requests to sqlite_web database browser."""
    return await proxy_request(request, "db-browser", path)


@router.get("/db-browser")
async def proxy_db_browser_root(request: Request):
    """Proxy root request to sqlite_web."""
    return await proxy_request(request, "db-browser", "")


# S3 Backup proxy
@router.api_route("/s3-backup/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def proxy_s3_backup(request: Request, path: str = ""):
    """Proxy requests to S3 backup web interface."""
    return await proxy_request(request, "s3-backup", path)


@router.get("/s3-backup")
async def proxy_s3_backup_root(request: Request):
    """Proxy root request to S3 backup."""
    return await proxy_request(request, "s3-backup", "")


# API endpoint to get proxy configuration (useful for frontend)
@router.get("/api/proxy/config")
async def get_proxy_config():
    """Return proxy configuration for frontend use."""
    return {
        "db_browser_path": "/db-browser",
        "s3_backup_path": "/s3-backup",
        "s3_backup_api_path": "/s3-backup/api",
        "enabled": True
    }
