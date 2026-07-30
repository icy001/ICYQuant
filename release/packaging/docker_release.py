"""
Docker packaging for ICYQuant services.

Generates Docker configurations including Dockerfiles for each service,
docker-compose.yml for local development, multi-stage build configs,
and health check configurations. Supports Development, Production, and CI environments.
"""

from __future__ import annotations

import os
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class DockerEnvironment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    CI = "ci"


@dataclass
class DockerFileConfig:
    service_name: str
    base_image: str
    work_dir: str
    port: int
    environment: DockerEnvironment
    dependencies: list[str] = field(default_factory=list)
    health_check_path: str = "/health"
    health_check_interval: int = 30
    health_check_timeout: int = 5
    health_check_retries: int = 3
    cpu_limit: str = "2.0"
    memory_limit: str = "2g"


@dataclass
class GeneratedFile:
    path: str
    content: str
    file_type: str = "dockerfile"


@dataclass
class DockerReleaseResult:
    success: bool
    generated_files: list[GeneratedFile] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    environment: DockerEnvironment = DockerEnvironment.DEVELOPMENT
    service_count: int = 0

    @property
    def file_paths(self) -> list[str]:
        return [f.path for f in self.generated_files]


class DockerRelease:
    """
    Generates Docker configurations for ICYQuant services.

    Produces Dockerfiles with multi-stage builds, docker-compose.yml
    for local development, and health check configurations tailored to
    each environment (development, production, CI).
    """

    def __init__(self, output_dir: str = "deploy/docker") -> None:
        self.output_dir = output_dir
        self._services: list[str] = []
        self._configs: dict[str, DockerFileConfig] = {}

    def add_service(
        self,
        service_name: str,
        *,
        base_image: str = "python:3.11-slim",
        work_dir: str = "/app",
        port: int = 8000,
        environment: DockerEnvironment = DockerEnvironment.PRODUCTION,
        dependencies: Optional[list[str]] = None,
        health_check_path: str = "/health",
        cpu_limit: str = "2.0",
        memory_limit: str = "2g",
    ) -> None:
        config = DockerFileConfig(
            service_name=service_name,
            base_image=base_image,
            work_dir=work_dir,
            port=port,
            environment=environment,
            dependencies=dependencies or [],
            health_check_path=health_check_path,
            cpu_limit=cpu_limit,
            memory_limit=memory_limit,
        )
        self._services.append(service_name)
        self._configs[service_name] = config

    def generate(self, environment: DockerEnvironment) -> DockerReleaseResult:
        generated: list[GeneratedFile] = []
        errors: list[str] = []
        warnings: list[str] = []

        for service_name in self._services:
            config = self._configs.get(service_name)
            if config is None:
                errors.append(f"Missing config for service: {service_name}")
                continue
            try:
                dockerfile = self._generate_dockerfile(config, environment)
                file_path = os.path.join(
                    self.output_dir, service_name, "Dockerfile"
                )
                generated.append(GeneratedFile(
                    path=file_path,
                    content=dockerfile,
                    file_type="dockerfile",
                ))
            except Exception as e:
                errors.append(f"Failed to generate Dockerfile for {service_name}: {e}")

        try:
            compose = self._generate_compose(environment)
            compose_path = os.path.join(self.output_dir, "docker-compose.yml")
            generated.append(GeneratedFile(
                path=compose_path,
                content=compose,
                file_type="compose",
            ))
        except Exception as e:
            errors.append(f"Failed to generate docker-compose.yml: {e}")

        if environment == DockerEnvironment.PRODUCTION:
            try:
                ignore = self._generate_dockerignore()
                ignore_path = os.path.join(self.output_dir, ".dockerignore")
                generated.append(GeneratedFile(
                    path=ignore_path,
                    content=ignore,
                    file_type="dockerignore",
                ))
            except Exception as e:
                warnings.append(f"Failed to generate .dockerignore: {e}")

        success = len(errors) == 0
        return DockerReleaseResult(
            success=success,
            generated_files=generated,
            validation_errors=errors,
            warnings=warnings,
            environment=environment,
            service_count=len(self._services),
        )

    def _generate_dockerfile(
        self, config: DockerFileConfig, env: DockerEnvironment
    ) -> str:
        if env == DockerEnvironment.DEVELOPMENT:
            return self._dockerfile_dev(config)
        elif env == DockerEnvironment.CI:
            return self._dockerfile_ci(config)
        else:
            return self._dockerfile_prod(config)

    def _dockerfile_dev(self, config: DockerFileConfig) -> str:
        return textwrap.dedent(f"""\
            # Development Dockerfile for {config.service_name}
            FROM {config.base_image}

            WORKDIR {config.work_dir}

            ENV PYTHONDONTWRITEBYTECODE=1 \\
                PYTHONUNBUFFERED=1 \\
                APP_ENV=development

            RUN apt-get update && apt-get install -y --no-install-recommends \\
                build-essential \\
                curl \\
                && rm -rf /var/lib/apt/lists/*

            COPY pyproject.toml ./
            RUN pip install --no-cache-dir -e ".[dev]"

            COPY . .

            EXPOSE {config.port}

            HEALTHCHECK --interval={config.health_check_interval}s \\
                --timeout={config.health_check_timeout}s \\
                --retries={config.health_check_retries}s \\
                CMD curl -f http://localhost:{config.port}{config.health_check_path} || exit 1

            CMD ["uvicorn", "{config.service_name}.main:app", \\
                 "--host", "0.0.0.0", \\
                 "--port", "{config.port}", \\
                 "--reload"]
        """)

    def _dockerfile_ci(self, config: DockerFileConfig) -> str:
        return textwrap.dedent(f"""\
            # CI Dockerfile for {config.service_name}
            FROM {config.base_image} AS builder

            WORKDIR {config.work_dir}

            ENV PYTHONDONTWRITEBYTECODE=1 \\
                PYTHONUNBUFFERED=1 \\
                APP_ENV=ci

            RUN apt-get update && apt-get install -y --no-install-recommends \\
                build-essential \\
                && rm -rf /var/lib/apt/lists/*

            COPY pyproject.toml ./
            RUN pip install --no-cache-dir -e "."

            COPY . .

            # Test stage
            FROM builder AS tester
            RUN pip install --no-cache-dir pytest pytest-asyncio httpx
            CMD ["pytest", "tests/", "-v", "--tb=short"]

            # Runtime stage
            FROM {config.base_image} AS runtime

            WORKDIR {config.work_dir}

            ENV PYTHONDONTWRITEBYTECODE=1 \\
                PYTHONUNBUFFERED=1 \\
                APP_ENV=ci

            COPY --from=builder {config.work_dir} {config.work_dir}
            COPY --from=builder /usr/local/lib /usr/local/lib
            COPY --from=builder /usr/local/bin /usr/local/bin

            EXPOSE {config.port}

            HEALTHCHECK --interval={config.health_check_interval}s \\
                --timeout={config.health_check_timeout}s \\
                --retries={config.health_check_retries}s \\
                CMD curl -f http://localhost:{config.port}{config.health_check_path} || exit 1

            CMD ["uvicorn", "{config.service_name}.main:app", \\
                 "--host", "0.0.0.0", \\
                 "--port", "{config.port}"]
        """)

    def _dockerfile_prod(self, config: DockerFileConfig) -> str:
        return textwrap.dedent(f"""\
            # Production Dockerfile for {config.service_name}
            # Multi-stage build for minimal image size
            FROM {config.base_image} AS builder

            WORKDIR {config.work_dir}

            ENV PYTHONDONTWRITEBYTECODE=1 \\
                PYTHONUNBUFFERED=1 \\
                APP_ENV=production

            RUN apt-get update && apt-get install -y --no-install-recommends \\
                build-essential \\
                curl \\
                && rm -rf /var/lib/apt/lists/*

            COPY pyproject.toml ./
            RUN pip install --no-cache-dir -e "."

            COPY . .

            # Runtime stage - minimal image
            FROM {config.base_image} AS runtime

            WORKDIR {config.work_dir}

            ENV PYTHONDONTWRITEBYTECODE=1 \\
                PYTHONUNBUFFERED=1 \\
                APP_ENV=production

            COPY --from=builder {config.work_dir} {config.work_dir}
            COPY --from=builder /usr/local/lib /usr/local/lib
            COPY --from=builder /usr/local/bin /usr/local/bin

            RUN groupadd -r appuser && useradd -r -g appuser appuser \\
                && chown -R appuser:appuser {config.work_dir}

            USER appuser

            EXPOSE {config.port}

            HEALTHCHECK --interval={config.health_check_interval}s \\
                --timeout={config.health_check_timeout}s \\
                --retries={config.health_check_retries}s \\
                CMD curl -f http://localhost:{config.port}{config.health_check_path} || exit 1

            CMD ["uvicorn", "{config.service_name}.main:app", \\
                 "--host", "0.0.0.0", \\
                 "--port", "{config.port}", \\
                 "--workers", "4"]
        """)

    def _generate_compose(self, environment: DockerEnvironment) -> str:
        services_section: list[str] = []
        for service_name in self._services:
            config = self._configs[service_name]
            service_def = self._compose_service(config, environment)
            services_section.append(service_def)

        services_yaml = "\n".join(services_section)

        return textwrap.dedent(f"""\
            # Docker Compose for ICYQuant - {environment.value}
            version: "3.9"

            services:
            {textwrap.indent(services_yaml, "  ")}

            volumes:
              postgres_data:
              redis_data:

            networks:
              icynet:
                driver: bridge
        """)

    def _compose_service(
        self, config: DockerFileConfig, environment: DockerEnvironment
    ) -> str:
        env_vars = self._environment_variables(config, environment)
        return textwrap.dedent(f"""\
            {config.service_name}:
              build:
                context: .
                dockerfile: {self.output_dir}/{config.service_name}/Dockerfile
                target: {"runtime" if environment == DockerEnvironment.PRODUCTION else ""}
              image: icyquant/{config.service_name}:{environment.value}
              container_name: icyquant-{config.service_name}
              ports:
                - "{config.port}:{config.port}"
              environment:
            {textwrap.indent(env_vars, "    ")}
              volumes:
                - ./configs:/app/configs:ro
              networks:
                - icynet
              healthcheck:
                test: ["CMD", "curl", "-f", "http://localhost:{config.port}{config.health_check_path}"]
                interval: {config.health_check_interval}s
                timeout: {config.health_check_timeout}s
                retries: {config.health_check_retries}
              deploy:
                resources:
                  limits:
                    cpus: "{config.cpu_limit}"
                    memory: {config.memory_limit}
              restart: unless-stopped
        """)

    def _environment_variables(
        self, config: DockerFileConfig, environment: DockerEnvironment
    ) -> str:
        base = f"""\
            APP_ENV: {environment.value}
            SERVICE_NAME: {config.service_name}
            PYTHONUNBUFFERED: "1"
        """
        if environment == DockerEnvironment.DEVELOPMENT:
            base += """\
            LOG_LEVEL: DEBUG
            RELOAD: "true"
        """
        elif environment == DockerEnvironment.PRODUCTION:
            base += """\
            LOG_LEVEL: INFO
            RELOAD: "false"
        """
        else:
            base += """\
            LOG_LEVEL: WARNING
            RELOAD: "false"
        """
        return base

    def _generate_dockerignore(self) -> str:
        return textwrap.dedent("""\
            __pycache__
            *.pyc
            *.pyo
            .git
            .gitignore
            .env
            .venv
            venv
            .pytest_cache
            .mypy_cache
            .ruff_cache
            tests
            docs
            *.md
            !README.md
            .idea
            .vscode
            node_modules
            .DS_Store
            *.log
        """)