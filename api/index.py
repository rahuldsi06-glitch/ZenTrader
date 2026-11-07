"""
Vercel Serverless Entrypoint for ZenTrader
Defines a top-level FastAPI instance for Vercel's AST parser.
"""
import sys
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request

# Add project root directory to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# TOP-LEVEL FASTAPI INSTANCE (Required by Vercel Python AST builder)
app = FastAPI(title="ZenTrader Autonomous Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def fix_vercel_paths(request: Request, call_next):
    """Normalizes any internal Vercel rewrite paths so routing never fails."""
    path = request.scope.get("path", "")
    if path.startswith("/api/index.py"):
        request.scope["path"] = path.replace("/api/index.py", "") or "/"
    elif path == "/api" or path == "/api/":
        request.scope["path"] = "/"
    response = await call_next(request)
    return response

# Mount all ZenTrader routes from the core server
from zentrader.ui.server import app as server_app
app.include_router(server_app.router)

@app.api_route("/debug-path/{subpath:path}", methods=["GET", "POST"])
@app.api_route("/api/debug-path/{subpath:path}", methods=["GET", "POST"])
def debug_path(request: Request, subpath: str = ""):
    return {
        "url_path": request.url.path,
        "scope_path": request.scope.get("path"),
        "subpath": subpath,
        "query": str(request.query_params)
    }
