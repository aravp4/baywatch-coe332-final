FROM python:3.14

# Install uv
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"

WORKDIR /code

#uv project from repo w/ new uv lock and pyproject files
COPY pyproject.toml /code/pyproject.toml
COPY uv.lock /code/uv.lock

#Dependencies from the root
RUN uv sync

#Copy code necessary for the project
COPY src/api.py /code/api.py
COPY src/jobs.py /code/jobs.py
COPY src/worker.py /code/worker.py

#Copy tests
COPY test/test_api.py /code/test_api.py
COPY test/test_jobs.py /code/test_jobs.py
COPY test/test_worker.py /code/test_worker.py

#Command to run the application
CMD ["uv", "run", "--", "fastapi", "dev", "--host", "0.0.0.0", "api.py"]