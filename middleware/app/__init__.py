"""Middleware package — HTTP layer on top of the installable backend `app`.

Backend lives in backend/ and gets `pip install -e ./backend`. Then we import
it as `app.*` (models, services, etc.). Middleware-internal code uses relative
imports like `from ..schemas import ...`.
"""
