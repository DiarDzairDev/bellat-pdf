# wsgi.py

from starlette.middleware.wsgi import WSGIMiddleware
from fastapi import FastAPI
from main import app as fastapi_app

# Wrap FastAPI inside WSGIMiddleware
application = WSGIMiddleware(fastapi_app)
