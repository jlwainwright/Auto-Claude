"""
Service Boundary Detector Module
=================================

Detects service boundaries within a project by identifying independent deployable units,
shared code vs service-specific code, inter-service dependencies, and communication patterns.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..analyzers.base import BaseAnalyzer, SKIP_DIRS, SERVICE_INDICATORS, SERVICE_ROOT_FILES


class ServiceBoundaryDetector(BaseAnalyzer):
    """Detects service boundaries and inter-service relationships."""

    def __init__(self, path: Path, analysis: dict[str, Any]):
        """
        Initialize service boundary detector.

        Args:
            path: Project root path
            analysis: Analysis dictionary to populate with results
        """
        super().__init__(path)
        self.analysis = analysis
        self.services = self.analysis.setdefault("services", {})
        self.shared_code = self.analysis.setdefault("shared_code", [])
        self.dependencies = self.analysis.setdefault("service_dependencies", {})
        self.communication = self.analysis.setdefault("communication_patterns", {})

    def detect_boundaries(self) -> None:
        """Run all service boundary detection methods."""
        self._find_deployable_units()
        self._identify_shared_code()
        self._map_dependencies()
        self._detect_communication_patterns()

    def _find_deployable_units(self) -> None:
        """
        Find independent deployable units.

        Indicators:
        - Directories with package.json, requirements.txt, or other service root files
        - Directories with Dockerfile
        - Named with service indicators (backend, frontend, api, etc.)
        """
        deployable_units = {}

        # First, check if root itself is a service
        root_is_service = self._check_if_service(self.path, "root")
        if root_is_service:
            deployable_units["root"] = {
                "path": ".",
                "type": "root",
                "config_files": self._get_config_files(self.path),
                "has_dockerfile": self._has_dockerfile(self.path),
            }

        # Scan subdirectories for services
        for item in self.path.iterdir():
            if not item.is_dir():
                continue

            # Skip known non-service directories
            if item.name in SKIP_DIRS:
                continue

            # Check if this directory is a service
            service_info = self._check_directory_as_service(item)
            if service_info:
                deployable_units[item.name] = service_info

        # Also check nested directories (e.g., apps/backend, services/auth)
        nested_services = self._find_nested_services()
        for name, info in nested_services.items():
            # Don't duplicate if already found
            if name not in deployable_units:
                deployable_units[name] = info

        if deployable_units:
            self.services["deployable_units"] = deployable_units
            self.services["total_units"] = len(deployable_units)

    def _check_if_service(self, path: Path, name: str) -> bool:
        """Check if a given path is a service."""
        # Has package/dependency file
        config_files = self._get_config_files(path)
        if config_files:
            return True

        # Has Dockerfile
        if self._has_dockerfile(path):
            return True

        # Named with service indicator
        if name.lower() in SERVICE_INDICATORS:
            return True

        return False

    def _check_directory_as_service(self, dir_path: Path) -> dict[str, Any] | None:
        """Check if a directory represents an independent service."""
        # Get config files
        config_files = self._get_config_files(dir_path)

        # Check for Dockerfile
        has_dockerfile = self._has_dockerfile(dir_path)

        # Must have at least one indicator to be considered a service
        if not config_files and not has_dockerfile:
            # Check if name is a strong service indicator
            if dir_path.name.lower() not in SERVICE_INDICATORS:
                return None

        # Determine service type from name and config
        service_type = self._infer_service_type(dir_path.name, config_files)

        return {
            "path": str(dir_path.relative_to(self.path)),
            "type": service_type,
            "config_files": config_files,
            "has_dockerfile": has_dockerfile,
        }

    def _find_nested_services(self) -> dict[str, Any]:
        """Find services in nested directories (apps/, services/, packages/)."""
        nested_services = {}
        service_containers = ["apps", "services", "packages", "microservices"]

        for container in service_containers:
            container_path = self.path / container
            if not container_path.exists() or not container_path.is_dir():
                continue

            for item in container_path.iterdir():
                if not item.is_dir():
                    continue

                if item.name in SKIP_DIRS:
                    continue

                # Check if this is a service
                service_info = self._check_directory_as_service(item)
                if service_info:
                    name = f"{container}/{item.name}"
                    nested_services[name] = service_info
                    nested_services[name]["path"] = f"{container}/{item.name}"

        return nested_services

    def _get_config_files(self, path: Path) -> list[str]:
        """Get package/dependency configuration files in a directory."""
        found = []
        for config_file in SERVICE_ROOT_FILES:
            if (path / config_file).exists():
                found.append(config_file)
        return found

    def _has_dockerfile(self, path: Path) -> bool:
        """Check if directory has a Dockerfile."""
        docker_patterns = ["Dockerfile", "dockerfile", "Dockerfile.*"]
        for pattern in docker_patterns:
            # Simple check for exact match or Dockerfile.*
            if pattern == "Dockerfile.*":
                # Check for any Dockerfile.something
                for item in path.iterdir():
                    if item.is_file() and item.name.startswith("Dockerfile."):
                        return True
            elif (path / pattern).exists():
                return True
        return False

    def _infer_service_type(self, name: str, config_files: list[str]) -> str:
        """Infer service type from name and configuration."""
        name_lower = name.lower()

        # Infer from name
        if any(kw in name_lower for kw in ["frontend", "client", "web", "ui", "app"]):
            return "frontend"
        elif any(kw in name_lower for kw in ["backend", "api", "server", "service"]):
            return "backend"
        elif any(kw in name_lower for kw in ["worker", "job", "queue", "task", "celery"]):
            return "worker"
        elif any(kw in name_lower for kw in ["scraper", "crawler", "spider"]):
            return "scraper"
        elif any(kw in name_lower for kw in ["proxy", "gateway", "router"]):
            return "proxy"
        elif any(kw in name_lower for kw in ["lib", "shared", "common", "core", "utils"]):
            return "library"
        elif any(kw in name_lower for kw in ["admin", "dashboard"]):
            return "admin"

        # Infer from config files
        if "package.json" in config_files:
            # Check if it's a frontend package
            pkg_path = self.path / name / "package.json" if name != "root" else self.path / "package.json"
            if pkg_path.exists():
                try:
                    pkg_content = pkg_path.read_text()
                    # Frontend indicators in package.json
                    if any(kw in pkg_content for kw in ["react", "vue", "angular", "next", "nuxt", "svelte"]):
                        return "frontend"
                    elif any(kw in pkg_content for kw in ["express", "fastify", "koa", "nest"]):
                        return "backend"
                except OSError:
                    pass

        return "unknown"

    def _identify_shared_code(self) -> None:
        """
        Identify shared code vs service-specific code.

        Indicators:
        - Directories named shared/, common/, utils/, core/, libs/
        - Code referenced by multiple services
        - Package dependencies on local shared packages
        """
        shared_dirs = []

        # Check for shared code directories at root
        shared_indicators = {
            "shared": "Shared utilities",
            "common": "Common code",
            "utils": "Utility functions",
            "core": "Core functionality",
            "libs": "Shared libraries",
            "lib": "Shared library",
            "packages": "Shared packages",
        }

        for dir_name, purpose in shared_indicators.items():
            dir_path = self.path / dir_name
            if dir_path.exists() and dir_path.is_dir():
                shared_dirs.append({
                    "name": dir_name,
                    "path": dir_name,
                    "purpose": purpose,
                    "files": self._count_files(dir_path),
                })

        # Check for shared code in nested locations
        nested_shared = [
            "apps/shared",
            "services/shared",
            "packages/shared",
            "src/shared",
            "lib/shared",
        ]

        for shared_path in nested_shared:
            if self._exists(shared_path):
                path_parts = shared_path.split("/")
                shared_dirs.append({
                    "name": shared_path,
                    "path": shared_path,
                    "purpose": "Shared code",
                    "files": self._count_files(self.path / shared_path),
                })

        # Check for local package dependencies (monorepo shared packages)
        local_packages = self._find_local_package_dependencies()
        if local_packages:
            for pkg_name, pkg_info in local_packages.items():
                shared_dirs.append({
                    "name": pkg_name,
                    "path": pkg_info.get("path", pkg_name),
                    "purpose": "Local package dependency",
                    "type": "local_package",
                })

        if shared_dirs:
            self.shared_code = shared_dirs
            self.services["shared_directories"] = len(shared_dirs)

    def _count_files(self, dir_path: Path) -> int:
        """Count files in a directory (non-recursive)."""
        try:
            return len([f for f in dir_path.iterdir() if f.is_file()])
        except OSError:
            return 0

    def _find_local_package_dependencies(self) -> dict[str, Any]:
        """Find local package dependencies in monorepo setup."""
        local_packages = {}

        # Check workspace configuration
        if self._exists("package.json"):
            pkg = self._read_json("package.json")
            if pkg and "workspaces" in pkg:
                workspaces = pkg["workspaces"]
                packages = []
                if isinstance(workspaces, list):
                    packages = workspaces
                elif isinstance(workspaces, dict) and "packages" in workspaces:
                    packages = workspaces["packages"]

                # Extract package names from workspace patterns
                for pattern in packages:
                    if "*" in pattern:
                        # Find matching directories
                        base_path = pattern.split("*")[0].rstrip("/")
                        if self._exists(base_path):
                            base_dir = self.path / base_path
                            for item in base_dir.iterdir():
                                if item.is_dir() and not item.name.startswith("."):
                                    pkg_json = item / "package.json"
                                    if pkg_json.exists():
                                        try:
                                            pkg_data = json.loads(pkg_json.read_text())
                                            local_packages[item.name] = {
                                                "path": f"{base_path}/{item.name}",
                                                "version": pkg_data.get("version", "unknown"),
                                            }
                                        except (OSError, json.JSONDecodeError):
                                            pass

        # Check for explicit local dependencies in service package.json files
        deployable_units = self.services.get("deployable_units", {})
        for unit_name, unit_info in deployable_units.items():
            unit_path = self.path / unit_info["path"]
            pkg_json = unit_path / "package.json"
            if pkg_json.exists():
                try:
                    pkg_data = json.loads(pkg_json.read_text())
                    deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}

                    for dep_name, dep_version in deps.items():
                        # Check for local package references (workspace:, file:, link:)
                        if isinstance(dep_version, str) and any(
                            prefix in dep_version
                            for prefix in ["workspace:", "file:", "link:", "*"]
                        ):
                            if dep_name not in local_packages:
                                local_packages[dep_name] = {
                                    "path": dep_name,
                                    "referenced_by": unit_name,
                                }
                except (OSError, json.JSONDecodeError):
                    pass

        return local_packages

    def _map_dependencies(self) -> None:
        """
        Map inter-service dependencies.

        Indicators:
        - API calls between services (fetch, axios, requests, httpx)
        - Shared database connections
        - Message queue dependencies
        - Import statements crossing service boundaries
        """
        dependency_map = {}
        deployable_units = self.services.get("deployable_units", {})

        # For each service, find dependencies on other services
        for unit_name, unit_info in deployable_units.items():
            unit_path = self.path / unit_info["path"]
            dependencies = []

            # Check for API call patterns
            api_deps = self._find_api_dependencies(unit_path, unit_name, deployable_units)
            dependencies.extend(api_deps)

            # Check for shared database
            db_deps = self._find_database_dependencies(unit_path)
            dependencies.extend(db_deps)

            # Check for message queue dependencies
            mq_deps = self._find_message_queue_dependencies(unit_path)
            dependencies.extend(mq_deps)

            # Check for local imports
            import_deps = self._find_import_dependencies(unit_path, deployable_units)
            dependencies.extend(import_deps)

            if dependencies:
                dependency_map[unit_name] = dependencies

        if dependency_map:
            self.dependencies = dependency_map

    def _find_api_dependencies(
        self, service_path: Path, service_name: str, all_services: dict
    ) -> list[dict[str, Any]]:
        """Find API dependencies on other services."""
        api_deps = []

        # Common API patterns
        api_patterns = [
            # JavaScript/TypeScript
            (r"fetch\(['\"]https?://([^'\"]+)['\"]", "HTTP fetch"),
            (r"axios\.(get|post|put|delete|patch)\(['\"]https?://([^'\"]+)['\"]", "Axios HTTP"),
            (r"https?:\/\/([^\/]+)", "HTTP URL"),
            # Python
            (r"requests\.(get|post|put|delete|patch)\(['\"]https?://([^'\"]+)['\"]", "Python requests"),
            (r"httpx\.(get|post|put|delete|patch)\(['\"]https?://([^'\"]+)['\"]", "Python httpx"),
            (r"urllib\.(request|fetch)\(['\"]https?://([^'\"]+)['\"]", "Python urllib"),
            # Go
            (r"http\.Get\(['\"]https?://([^'\"]+)['\"]", "Go http"),
            (r"resty\.([A-Z][a-z]+)\(['\"]https?://([^'\"]+)['\"]", "Go resty"),
        ]

        # Search in source files
        source_extensions = [".js", ".ts", ".tsx", ".jsx", ".py", ".go"]
        for source_file in service_path.rglob("*"):
            if source_file.suffix not in source_extensions:
                continue

            try:
                content = source_file.read_text()
                for pattern, method in api_patterns:
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        # Extract host/service name from URL
                        url = match.group(0) if not match.groups() else match.group(0)
                        host_match = re.search(r"https?://([^:/]+)", url)
                        if host_match:
                            host = host_match.group(1)
                            # Check if this host matches another service
                            for other_service, other_info in all_services.items():
                                if other_service == service_name:
                                    continue
                                if other_service.lower() in host.lower():
                                    api_deps.append({
                                        "type": "api_call",
                                        "target": other_service,
                                        "method": method,
                                        "host": host,
                                        "file": str(source_file.relative_to(service_path)),
                                    })
                                    break
            except OSError:
                continue

        return api_deps

    def _find_database_dependencies(self, service_path: Path) -> list[dict[str, Any]]:
        """Find database dependencies (shared databases indicate coupling)."""
        db_deps = []

        # Database connection patterns
        db_patterns = [
            (r"postgres(?:ql)?://([^:/]+)[^\s]*", "PostgreSQL"),
            (r"mysql://([^:/]+)[^\s]*", "MySQL"),
            (r"mongodb://([^:/]+)[^\s]*", "MongoDB"),
            (r"redis://([^:/]+)[^\s]*", "Redis"),
        ]

        # Check environment files, config files, and source code
        check_files = [
            service_path / ".env",
            service_path / ".env.example",
            service_path / "config.py",
            service_path / "config.js",
            service_path / "database.py",
            service_path / "db.py",
        ]

        for file_path in check_files:
            if not file_path.exists():
                continue

            try:
                content = file_path.read_text()
                for pattern, db_type in db_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        host = match.group(1)
                        db_deps.append({
                            "type": "database",
                            "db_type": db_type,
                            "host": host,
                            "file": str(file_path.relative_to(service_path)),
                        })
            except OSError:
                continue

        return db_deps

    def _find_message_queue_dependencies(self, service_path: Path) -> list[dict[str, Any]]:
        """Find message queue dependencies."""
        mq_deps = []

        # Message queue patterns
        mq_patterns = [
            # RabbitMQ
            (r"pika\.|amqp\.|rabbitmq", "RabbitMQ"),
            # Redis (as queue)
            (r"redis\.|from redis import|import redis", "Redis Queue"),
            # AWS SQS
            (r"boto3\.client\(['\"]sqs['\"]|aws sqs", "AWS SQS"),
            # Kafka
            (r"kafka-python|confluent-kafka|from kafka", "Kafka"),
            # Celery
            (r"from celery import|@celery\.task", "Celery"),
            # Bull/BullMQ (Node.js)
            (r"require\(['\"]bull['\"]|import.*bull", "BullMQ"),
        ]

        # Search in source and config files
        source_extensions = [".js", ".ts", ".tsx", ".jsx", ".py", ".json", ".yaml", ".yml"]
        for source_file in service_path.rglob("*"):
            if source_file.suffix not in source_extensions:
                continue
            if source_file.name in ["node_modules", "venv", ".git"]:
                continue

            try:
                content = source_file.read_text()
                for pattern, mq_type in mq_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        mq_deps.append({
                            "type": "message_queue",
                            "mq_type": mq_type,
                            "file": str(source_file.relative_to(service_path)),
                        })
                        break
            except OSError:
                continue

        return mq_deps

    def _find_import_dependencies(
        self, service_path: Path, all_services: dict
    ) -> list[dict[str, Any]]:
        """Find import dependencies crossing service boundaries."""
        import_deps = []

        # Import patterns for different languages
        import_patterns = [
            # Python: from other_service import X
            (r"from\s+(\w+)\s+import", "Python"),
            # Python: import other_service
            (r"^import\s+(\w+)", "Python"),
            # JavaScript/TypeScript: import ... from 'other_service'
            (r"import\s+.*?from\s+['\"](\w+)['\"]", "JavaScript"),
            # Go: import "other_service"
            (r"import\s+['\"](\w+)['\"]", "Go"),
        ]

        source_extensions = [".py", ".js", ".ts", ".go"]
        for source_file in service_path.rglob("*"):
            if source_file.suffix not in source_extensions:
                continue

            try:
                content = source_file.read_text()
                for pattern, lang in import_patterns:
                    matches = re.finditer(pattern, content, re.MULTILINE)
                    for match in matches:
                        imported_module = match.group(1)
                        # Check if this matches another service
                        for other_service in all_services.keys():
                            if imported_module.lower() == other_service.lower():
                                import_deps.append({
                                    "type": "import",
                                    "target": other_service,
                                    "language": lang,
                                    "file": str(source_file.relative_to(service_path)),
                                })
                                break
            except OSError:
                continue

        return import_deps

    def _detect_communication_patterns(self) -> None:
        """
        Detect service communication patterns.

        Patterns to detect:
        - REST API (HTTP/HTTPS endpoints)
        - gRPC (protobuf definitions, grpc imports)
        - Message queues (RabbitMQ, Kafka, SQS, Celery)
        - GraphQL (GraphQL schemas, resolvers)
        - WebSocket (socket.io, ws, websocket)
        - RPC (JSON-RPC, XML-RPC)
        """
        patterns = {}

        # Check for REST API
        rest_confidence = self._check_rest_pattern()
        if rest_confidence > 0:
            patterns["REST"] = {"confidence": rest_confidence}

        # Check for gRPC
        grpc_confidence = self._check_grpc_pattern()
        if grpc_confidence > 0:
            patterns["gRPC"] = {"confidence": grpc_confidence}

        # Check for message queues
        mq_confidence = self._check_message_queue_pattern()
        if mq_confidence > 0:
            patterns["message_queue"] = {"confidence": mq_confidence}

        # Check for GraphQL
        graphql_confidence = self._check_graphql_pattern()
        if graphql_confidence > 0:
            patterns["GraphQL"] = {"confidence": graphql_confidence}

        # Check for WebSocket
        websocket_confidence = self._check_websocket_pattern()
        if websocket_confidence > 0:
            patterns["WebSocket"] = {"confidence": websocket_confidence}

        # Check for RPC
        rpc_confidence = self._check_rpc_pattern()
        if rpc_confidence > 0:
            patterns["RPC"] = {"confidence": rpc_confidence}

        if patterns:
            self.communication = patterns

    def _check_rest_pattern(self) -> float:
        """Check for REST API communication pattern."""
        confidence = 0.0

        # Check for REST framework dependencies
        rest_indicators = {
            # Python
            "fastapi": 40,
            "flask": 30,
            "django-rest-framework": 35,
            "tornado": 25,
            "aiohttp": 25,
            # JavaScript/TypeScript
            "express": 35,
            "restify": 30,
            "koa": 25,
            "nestjs": 40,
            "fastify": 30,
            "axios": 20,
            "fetch": 15,
            # Go
            "gorilla/mux": 30,
            "gin-gonic/gin": 30,
            # Java
            "spring-boot-starter-web": 35,
            "jax-rs": 30,
            "jersey": 30,
        }

        # Check package.json files
        for package_file in self.path.rglob("package.json"):
            try:
                content = package_file.read_text()
                for indicator, weight in rest_indicators.items():
                    if indicator in content:
                        confidence = min(confidence + weight, 100)
            except OSError:
                continue

        # Check requirements.txt files
        for requirements_file in self.path.rglob("requirements.txt"):
            try:
                content = requirements_file.read_text()
                for indicator, weight in rest_indicators.items():
                    if indicator.lower() in content.lower():
                        confidence = min(confidence + weight, 100)
            except OSError:
                continue

        # Check for HTTP method patterns in source code
        http_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "@app.route", "@router"]
        source_extensions = [".py", ".js", ".ts", ".go"]
        for source_file in self.path.rglob("*"):
            if source_file.suffix not in source_extensions:
                continue

            try:
                content = source_file.read_text()
                for method in http_methods:
                    if method in content:
                        confidence = min(confidence + 5, 100)
                        break
            except OSError:
                continue

        return min(confidence, 100)

    def _check_grpc_pattern(self) -> float:
        """Check for gRPC communication pattern."""
        confidence = 0.0

        grpc_indicators = [
            "grpc",
            "protobuf",
            ".proto",
            "protoc",
            "grpcio",
            "@grpc/grpc-js",
            "grpc-go",
        ]

        # Check for .proto files
        proto_files = list(self.path.rglob("*.proto"))
        if proto_files:
            confidence = min(confidence + 50, 100)

        # Check dependencies
        for package_file in self.path.rglob("package.json"):
            try:
                content = package_file.read_text()
                for indicator in grpc_indicators:
                    if indicator in content:
                        confidence = min(confidence + 30, 100)
                        break
            except OSError:
                continue

        for requirements_file in self.path.rglob("requirements.txt"):
            try:
                content = requirements_file.read_text()
                if "grpcio" in content.lower() or "protobuf" in content.lower():
                    confidence = min(confidence + 30, 100)
            except OSError:
                continue

        # Check for grpc imports in source
        source_extensions = [".py", ".js", ".ts", ".go"]
        for source_file in self.path.rglob("*"):
            if source_file.suffix not in source_extensions:
                continue

            try:
                content = source_file.read_text()
                if "import grpc" in content or "from grpc" in content:
                    confidence = min(confidence + 20, 100)
                    break
            except OSError:
                continue

        return min(confidence, 100)

    def _check_message_queue_pattern(self) -> float:
        """Check for message queue communication pattern."""
        confidence = 0.0

        mq_indicators = {
            # RabbitMQ
            "pika": 30,
            "amqp": 30,
            "rabbitmq": 30,
            # Redis Queue
            "celery": 35,
            "rq": 25,
            # Kafka
            "kafka-python": 35,
            "confluent-kafka": 35,
            "kafkajs": 35,
            # AWS SQS
            "boto3": 25,
            "aws-sdk": 25,
            # BullMQ (Node.js)
            "bullmq": 30,
            "bull": 25,
        }

        # Check dependencies
        for package_file in self.path.rglob("package.json"):
            try:
                content = package_file.read_text()
                for indicator, weight in mq_indicators.items():
                    if indicator in content:
                        confidence = min(confidence + weight, 100)
            except OSError:
                continue

        for requirements_file in self.path.rglob("requirements.txt"):
            try:
                content = requirements_file.read_text()
                for indicator, weight in mq_indicators.items():
                    if indicator.lower() in content.lower():
                        confidence = min(confidence + weight, 100)
            except OSError:
                continue

        # Check for docker-compose services
        compose_files = ["docker-compose.yml", "docker-compose.yaml", "compose.yml"]
        for compose_file in compose_files:
            compose_path = self.path / compose_file
            if compose_path.exists():
                try:
                    content = compose_path.read_text()
                    mq_services = ["rabbitmq", "kafka", "redis", "celery"]
                    for service in mq_services:
                        if service in content.lower():
                            confidence = min(confidence + 25, 100)
                            break
                except OSError:
                    continue

        return min(confidence, 100)

    def _check_graphql_pattern(self) -> float:
        """Check for GraphQL communication pattern."""
        confidence = 0.0

        graphql_indicators = [
            "graphql",
            "apollo-server",
            "apollo-client",
            "gql",
            "graphql-tools",
            "graphql-yoga",
            "strapi",  # Uses GraphQL
        ]

        # Check for .graphql files
        graphql_files = list(self.path.rglob("*.graphql")) + list(self.path.rglob("*.gql"))
        if graphql_files:
            confidence = min(confidence + 40, 100)

        # Check dependencies
        for package_file in self.path.rglob("package.json"):
            try:
                content = package_file.read_text()
                for indicator in graphql_indicators:
                    if indicator in content:
                        confidence = min(confidence + 30, 100)
                        break
            except OSError:
                continue

        # Check for GraphQL schema/resolver patterns
        source_extensions = [".js", ".ts", ".tsx", ".jsx", ".py"]
        for source_file in self.path.rglob("*"):
            if source_file.suffix not in source_extensions:
                continue

            try:
                content = source_file.read_text()
                if any(
                    pattern in content
                    for pattern in ["GraphQLSchema", "type Query", "type Mutation", "@Resolver"]
                ):
                    confidence = min(confidence + 20, 100)
                    break
            except OSError:
                continue

        return min(confidence, 100)

    def _check_websocket_pattern(self) -> float:
        """Check for WebSocket communication pattern."""
        confidence = 0.0

        websocket_indicators = [
            "socket.io",
            "ws",
            "websocket",
            "socket.io-client",
            "uwebsockets",
            "websockets",
            "socketcluster",
        ]

        # Check dependencies
        for package_file in self.path.rglob("package.json"):
            try:
                content = package_file.read_text()
                for indicator in websocket_indicators:
                    if indicator in content:
                        confidence = min(confidence + 30, 100)
                        break
            except OSError:
                continue

        for requirements_file in self.path.rglob("requirements.txt"):
            try:
                content = requirements_file.read_text()
                if any(
                    indicator in content.lower()
                    for indicator in ["websockets", "websocket", "socket.io"]
                ):
                    confidence = min(confidence + 30, 100)
            except OSError:
                continue

        # Check for WebSocket usage in source
        source_extensions = [".js", ".ts", ".tsx", ".jsx", ".py"]
        for source_file in self.path.rglob("*"):
            if source_file.suffix not in source_extensions:
                continue

            try:
                content = source_file.read_text()
                if any(
                    pattern in content
                    for pattern in ["WebSocket(", "socket.io", "io.connect", "@socket.io"]
                ):
                    confidence = min(confidence + 20, 100)
                    break
            except OSError:
                continue

        return min(confidence, 100)

    def _check_rpc_pattern(self) -> float:
        """Check for RPC communication pattern."""
        confidence = 0.0

        rpc_indicators = [
            "jsonrpc",
            "xmlrpc",
            "zeromq",
            "zerorpc",
            "grpc",  # Also counted in gRPC
        ]

        # Check dependencies
        for package_file in self.path.rglob("package.json"):
            try:
                content = package_file.read_text()
                for indicator in rpc_indicators:
                    if indicator in content:
                        confidence = min(confidence + 30, 100)
                        break
            except OSError:
                continue

        # Check for RPC usage in Python
        for requirements_file in self.path.rglob("requirements.txt"):
            try:
                content = requirements_file.read_text()
                if any(
                    indicator in content.lower()
                    for indicator in ["xmlrpc", "jsonrpc", "zerorpc"]
                ):
                    confidence = min(confidence + 30, 100)
            except OSError:
                continue

        # Check for RPC patterns in source
        source_extensions = [".py", ".js", ".ts"]
        for source_file in self.path.rglob("*"):
            if source_file.suffix not in source_extensions:
                continue

            try:
                content = source_file.read_text()
                if any(
                    pattern in content
                    for pattern in ["jsonrpc", "xmlrpc", "xmlrpclib", "ServerProxy"]
                ):
                    confidence = min(confidence + 20, 100)
                    break
            except OSError:
                continue

        return min(confidence, 100)
