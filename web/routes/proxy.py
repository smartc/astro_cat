"""
Reverse proxy routes to forward requests to secondary services.
This allows the main app to proxy requests to sqlite_web (8081),
WebDAV (8082), and S3 backup (8083) services, enabling operation
behind a single Apache/nginx reverse proxy.
"""

import logging
import os
import re
import httpx
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def get_services():
    """Get service configuration with ports from environment variables."""
    return {
        "db-browser": {
            "host": "127.0.0.1",
            "port": int(os.environ.get('ASTROCAT_DB_BROWSER_PORT', '8081')),
            "rewrite_urls": True
        },
        "s3-backup": {
            "host": "127.0.0.1",
            "port": int(os.environ.get('ASTROCAT_S3_BACKUP_PORT', '8083')),
            "rewrite_urls": False
        },
        "webdav": {
            "host": "127.0.0.1",
            "port": int(os.environ.get('ASTROCAT_WEBDAV_PORT', '8082')),
            "rewrite_urls": False
        },
    }

# Timeout for proxy requests
PROXY_TIMEOUT = 30.0


def rewrite_html_urls(content: bytes, base_path: str) -> bytes:
    """Rewrite absolute URLs in HTML to use the proxy base path."""
    try:
        html = content.decode('utf-8')

        # Rewrite common absolute URL patterns
        # /static/ -> /db-browser/static/
        html = re.sub(r'(href|src|action)="(/static/)', rf'\1="{base_path}\2', html)
        html = re.sub(r"(href|src|action)='(/static/)", rf"\1='{base_path}\2", html)

        # Rewrite other absolute paths that sqlite_web might use
        # /query, /table, etc.
        html = re.sub(r'(href|src|action)="(/(?:query|table|index|row|import|export|sql))', rf'\1="{base_path}\2', html)
        html = re.sub(r"(href|src|action)='(/(?:query|table|index|row|import|export|sql))", rf"\1='{base_path}\2", html)

        # Rewrite form actions
        html = re.sub(r'(action)="(/)', rf'\1="{base_path}\2', html)

        return html.encode('utf-8')
    except Exception as e:
        logger.warning(f"Failed to rewrite HTML URLs: {e}")
        return content


async def proxy_request(request: Request, service_name: str, path: str) -> Response:
    """Proxy a request to an internal service."""
    services = get_services()
    if service_name not in services:
        raise HTTPException(status_code=404, detail=f"Unknown service: {service_name}")

    service = services[service_name]
    target_url = f"http://{service['host']}:{service['port']}/{path}"

    logger.info(f"Proxying {request.method} {request.url.path} -> {target_url}")

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
                if key_lower not in ('transfer-encoding', 'connection', 'keep-alive', 'content-length'):
                    # Rewrite Location header for redirects
                    if key_lower == 'location' and response.status_code in (301, 302, 303, 307, 308):
                        original_value = value
                        # Replace internal URL with proxy URL
                        internal_base = f"http://{service['host']}:{service['port']}"
                        if value.startswith(internal_base):
                            value = f"/{service_name}" + value[len(internal_base):]
                        elif value.startswith('/'):
                            # Relative redirect - prepend proxy path
                            value = f"/{service_name}{value}"
                        logger.info(f"Rewriting Location header: {original_value} -> {value}")
                    response_headers[key] = value

            # Get response content
            content = response.content
            content_type = response.headers.get('content-type', '')

            # Rewrite URLs in HTML responses if enabled for this service
            if service.get('rewrite_urls') and 'text/html' in content_type:
                base_path = f"/{service_name}"
                content = rewrite_html_urls(content, base_path)
                # Update content-length after rewriting
                response_headers['content-length'] = str(len(content))

            return Response(
                content=content,
                status_code=response.status_code,
                headers=response_headers,
                media_type=content_type
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


# WebDAV proxy - browser access methods
@router.get("/webdav/{path:path}")
async def proxy_webdav_get(request: Request, path: str):
    """Proxy GET requests to WebDAV server."""
    logger.info(f"WebDAV proxy route hit: path={path}")
    return await proxy_request(request, "webdav", path)


@router.get("/webdav")
async def proxy_webdav_root(request: Request):
    """Proxy root GET request to WebDAV."""
    return await proxy_request(request, "webdav", "")


@router.options("/webdav/{path:path}")
async def proxy_webdav_options(request: Request, path: str):
    """Proxy OPTIONS requests to WebDAV server."""
    return await proxy_request(request, "webdav", path)


@router.options("/webdav")
async def proxy_webdav_root_options(request: Request):
    """Proxy root OPTIONS request to WebDAV."""
    return await proxy_request(request, "webdav", "")


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
