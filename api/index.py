"""
Vercel Serverless Entrypoint for ZenTrader
"""
import sys
import os
import traceback

# Add root folder to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from zentrader.ui.server import app
except Exception as e:
    tb = traceback.format_exc()
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    app = FastAPI(title="ZenTrader Error Diagnostics")

    @app.get("/{full_path:path}")
    def error_page(full_path: str = ""):
        return HTMLResponse(
            f"<html><body style='background:#0b0e14;color:#f87171;font-family:monospace;padding:24px;'>"
            f"<h2>ZenTrader Serverless Diagnostic Traceback</h2>"
            f"<pre style='background:#1e293b;padding:16px;border-radius:8px;overflow-x:auto;'>{tb}</pre>"
            f"</body></html>",
            status_code=500
        )
