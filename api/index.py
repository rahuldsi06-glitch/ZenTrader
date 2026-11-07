"""
Vercel Serverless Entrypoint for ZenTrader
"""
import sys
import os

# Add root folder to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentrader.ui.server import app

# Vercel looks for the ASGI 'app' instance
