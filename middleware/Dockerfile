# Middleware Dockerfile (development placeholder — the compose service is
# currently commented out).
#
# NOTE: requirements.txt now installs the backend via `-e ../backend`, which is
# NOT present in this image's build context (./middleware). Containerizing the
# middleware therefore requires building from the repository root and COPYing
# both `backend/` and `middleware/` into the image (so the editable install can
# find `../backend`). That full containerization is tracked as future work; for
# local development run the app directly per the README.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
