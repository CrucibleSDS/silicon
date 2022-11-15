FROM python:3.10.6-slim

# Set pip to have no saved cache
ENV PIP_NO_CACHE_DIR=false \
    POETRY_VIRTUALENVS_CREATE=false \
    MAX_WORKERS=10

# Install poetry
RUN pip install -U poetry

# Create the working directory
WORKDIR /silicon

# Install project dependencies
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-dev

# Copy the Gunicorn config
COPY ./gunicorn_conf.py /gunicorn_conf.py

# Copy the source code in last to optimize rebuilding the image
COPY . .

EXPOSE 80

# Start Gunicorn with Uvicorn workers.
CMD ["sh", "-c", "poetry run alembic upgrade head && gunicorn -k uvicorn.workers.UvicornWorker -c /gunicorn_conf.py silicon:app"]
