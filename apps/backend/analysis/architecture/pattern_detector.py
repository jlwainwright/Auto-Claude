"""
Architecture Pattern Detector Module
====================================

Detects software architecture patterns from project structure and configuration.
Supports detection of MVC, microservices, monorepo, and layered architectures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..analyzers.base import BaseAnalyzer


class ArchitecturePatternDetector(BaseAnalyzer):
    """Detects software architecture patterns."""

    # Patterns to detect
    PATTERN_MVC = "mvc"
    PATTERN_MICROSERVICES = "microservices"
    PATTERN_MONOREPO = "monorepo"
    PATTERN_LAYERED = "layered"

    def __init__(self, path: Path, analysis: dict[str, Any]):
        """
        Initialize pattern detector.

        Args:
            path: Project root path
            analysis: Analysis dictionary to populate with results
        """
        super().__init__(path)
        self.analysis = analysis
        self.patterns = self.analysis.setdefault("architecture_patterns", {})

    def detect_all_patterns(self) -> None:
        """Run all pattern detection methods."""
        self._detect_mvc()
        self._detect_microservices()
        self._detect_monorepo()
        self._detect_layered()

    def _detect_mvc(self) -> None:
        """
        Detect Model-View-Controller (MVC) architecture.

        Indicators:
        - models/, views/, controllers/ directories
        - routes/ or api/ directory
        - Django, Rails, Express MVC structure
        """
        confidence = 0.0
        indicators = []

        # Check for classic MVC directories
        mvc_dirs = {
            "models": 30,
            "views": 30,
            "controllers": 30,
            "viewmodels": 15,  # MVVM variant
            "controllers/api": 10,  # Nested controllers
            "controllers/web": 10,
        }

        for dir_path, weight in mvc_dirs.items():
            if self._exists(dir_path):
                confidence += weight
                indicators.append(dir_path)

        # Check for routes directory (common in MVC frameworks)
        if self._exists("routes") or self._exists("routes/"):
            confidence += 15
            indicators.append("routes")

        # Check for api directory structure
        if self._exists("api/controllers") or self._exists("api/v1"):
            confidence += 20
            indicators.append("api structure")

        # Framework-specific MVC patterns
        # Django: apps/ with models.py, views.py
        if self._exists("apps"):
            has_django_structure = False
            for app_dir in (self.path / "apps").iterdir():
                if app_dir.is_dir():
                    if (app_dir / "models.py").exists() or (app_dir / "models" / "").exists():
                        if (app_dir / "views.py").exists() or (app_dir / "views" / "").exists():
                            has_django_structure = True
                            break
            if has_django_structure:
                confidence += 40
                indicators.append("Django apps structure")

        # Rails MVC: app/models, app/views, app/controllers
        if self._exists("app/models") and self._exists("app/views"):
            confidence += 40
            indicators.append("Rails MVC structure")

        # Express MVC: models/, routes/, views/
        if self._exists("models") and self._exists("routes"):
            if self._exists("package.json"):
                confidence += 25
                indicators.append("Express MVC structure")

        # Laravel MVC: app/Models, app/Http/Controllers
        if self._exists("app/Models") and self._exists("app/Http/Controllers"):
            confidence += 40
            indicators.append("Laravel MVC structure")

        # Normalize confidence to 0-100
        confidence = min(confidence, 100)

        if confidence > 0:
            self.patterns[self.PATTERN_MVC] = {
                "confidence": confidence,
                "indicators": indicators,
            }

    def _detect_microservices(self) -> None:
        """
        Detect microservices architecture.

        Indicators:
        - Multiple independent service directories
        - Docker Compose with multiple services
        - Each service has own package.json/requirements.txt
        - API Gateway or service registry
        """
        confidence = 0.0
        indicators = []
        service_count = 0

        # Check for docker-compose with multiple services
        compose_files = [
            "docker-compose.yml",
            "docker-compose.yaml",
            "compose.yml",
            "compose.yaml",
        ]

        for compose_file in compose_files:
            if self._exists(compose_file):
                content = self._read_file(compose_file)
                if content:
                    # Count services
                    import re

                    services = re.findall(r"^\s*(\w+)\s*:", content, re.MULTILINE)
                    service_count = len(services)
                    if service_count >= 3:
                        confidence += 40
                        indicators.append(f"docker-compose with {service_count} services")
                    elif service_count >= 2:
                        confidence += 25
                        indicators.append(f"docker-compose with {service_count} services")
                break

        # Check for multiple service directories with own package files
        potential_services = [
            d for d in self.path.iterdir()
            if d.is_dir() and not d.name.startswith(".")
            and not any(skip in d.name for skip in ["node_modules", "venv", ".git", "dist", "build"])
        ]

        independent_services = []
        for service_dir in potential_services:
            # Check if directory has its own package file
            has_package = any(
                (service_dir / f).exists()
                for f in ["package.json", "requirements.txt", "pyproject.toml", "Cargo.toml", "go.mod", "pom.xml"]
            )
            if has_package:
                independent_services.append(service_dir.name)

        if len(independent_services) >= 3:
            confidence += 40
            indicators.append(f"{len(independent_services)} independent service directories")
        elif len(independent_services) >= 2:
            confidence += 25
            indicators.append(f"{len(independent_services)} independent service directories")

        # Check for services/ directory
        if self._exists("services"):
            services_content = list((self.path / "services").iterdir())
            if len(services_content) >= 2:
                confidence += 30
                indicators.append("services/ directory with multiple services")

        # Check for microservice naming patterns
        service_keywords = ["auth", "user", "payment", "order", "product", "notification", "email", "api"]
        found_keywords = []
        for service_dir in potential_services:
            for keyword in service_keywords:
                if keyword in service_dir.name.lower():
                    found_keywords.append(service_dir.name)
                    break

        if len(found_keywords) >= 2:
            confidence += 20
            indicators.append(f"Service directories: {', '.join(found_keywords[:3])}")

        # Check for API Gateway indicators
        gateway_indicators = ["gateway", "api-gateway", "gateway-service"]
        for indicator in gateway_indicators:
            if (self.path / indicator).exists():
                confidence += 15
                indicators.append(f"API Gateway ({indicator})")
                break

        # Check for service registry (Consul, Eureka, etcd)
        registry_files = ["consul", "eureka", "etcd", "nacos"]
        for registry in registry_files:
            if registry in self._read_file("docker-compose.yml").lower() or \
               registry in self._read_file("docker-compose.yaml").lower():
                confidence += 15
                indicators.append(f"Service registry ({registry})")
                break

        # Normalize confidence to 0-100
        confidence = min(confidence, 100)

        if confidence > 0:
            result = {
                "confidence": confidence,
                "indicators": indicators,
            }
            if service_count > 0:
                result["service_count"] = service_count
            if independent_services:
                result["services"] = independent_services
            self.patterns[self.PATTERN_MICROSERVICES] = result

    def _detect_monorepo(self) -> None:
        """
        Detect monorepo architecture.

        Indicators:
        - packages/ or apps/ directory with multiple sub-projects
        - Workspace configuration (npm workspaces, yarn workspaces, pnpm workspace)
        - Monorepo tools (lerna, nx, turborepo)
        """
        confidence = 0.0
        indicators = []
        package_count = 0

        # Check for workspace configuration
        workspace_configs = [
            ("package.json", "workspaces"),
            ("pnpm-workspace.yaml", "packages"),
            ("lerna.json", "packages"),
        ]

        for config_file, key in workspace_configs:
            if self._exists(config_file):
                content = self._read_file(config_file)
                if key in content:
                    confidence += 30
                    indicators.append(f"{config_file} with {key}")

                    # Try to extract package count
                    if config_file == "package.json":
                        pkg = self._read_json("package.json")
                        if pkg and "workspaces" in pkg:
                            workspaces = pkg["workspaces"]
                            if isinstance(workspaces, list):
                                package_count = len(workspaces)
                            elif isinstance(workspaces, dict) and "packages" in workspaces:
                                package_count = len(workspaces["packages"])

        # Check for nx configuration
        if self._exists("nx.json"):
            confidence += 40
            indicators.append("nx.json")

            # Try to count projects
            nx_config = self._read_json("nx.json")
            if nx_config and "projects" in nx_config:
                if isinstance(nx_config["projects"], dict):
                    package_count = len([p for p in nx_config["projects"].keys() if not p.startswith("*")])

        # Check for turborepo
        if self._exists("turbo.json"):
            confidence += 35
            indicators.append("turbo.json")

        # Check for lerna
        if self._exists("lerna.json"):
            lerna_config = self._read_json("lerna.json")
            if lerna_config and "packages" in lerna_config:
                package_count = len(lerna_config["packages"])
            confidence += 30
            indicators.append("lerna.json")

        # Check for packages/ directory
        if self._exists("packages"):
            packages_dir = self.path / "packages"
            subdirs = [d for d in packages_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
            if len(subdirs) >= 2:
                confidence += 30
                indicators.append(f"packages/ with {len(subdirs)} sub-projects")
                package_count = max(package_count, len(subdirs))

        # Check for apps/ directory (common in Nx)
        if self._exists("apps"):
            apps_dir = self.path / "apps"
            subdirs = [d for d in apps_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
            if len(subdirs) >= 2:
                confidence += 30
                indicators.append(f"apps/ with {len(subdirs)} applications")
                package_count = max(package_count, len(subdirs))

        # Check for common monorepo structure
        if self._exists("packages") and self._exists("apps"):
            confidence += 20
            indicators.append("packages/ and apps/ structure")

        # Check for libs/ directory (common in Nx/monorepos)
        if self._exists("libs"):
            libs_dir = self.path / "libs"
            subdirs = [d for d in libs_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
            if len(subdirs) >= 2:
                confidence += 15
                indicators.append(f"libs/ with {len(subdirs)} libraries")

        # Check for yarn workspaces file
        if self._exists(".yarn/cache") or self._exists(".pnp.cjs"):
            if "workspaces" not in str(indicators):
                confidence += 20
                indicators.append("Yarn workspace indicators")

        # Normalize confidence to 0-100
        confidence = min(confidence, 100)

        if confidence > 0:
            result = {
                "confidence": confidence,
                "indicators": indicators,
            }
            if package_count > 0:
                result["package_count"] = package_count
            self.patterns[self.PATTERN_MONOREPO] = result

    def _detect_layered(self) -> None:
        """
        Detect layered (n-tier) architecture.

        Indicators:
        - presentation/, ui/, web/ layers
        - business/, domain/, logic/ layers
        - data/, repository/, persistence/, dal/ layers
        - Separation of concerns structure
        """
        confidence = 0.0
        indicators = []

        # Presentation/UI layer indicators
        presentation_dirs = {
            "presentation": 25,
            "ui": 20,
            "web": 15,
            "interface": 20,
            "interfaces": 20,
            "views": 15,  # Can be MVC or layered
            "components": 10,
            "pages": 10,
            "handlers": 15,  # Common in Go layered apps
        }

        for dir_path, weight in presentation_dirs.items():
            if self._exists(dir_path):
                confidence += weight
                indicators.append(f"Presentation layer ({dir_path})")

        # Business/Domain layer indicators
        business_dirs = {
            "business": 25,
            "domain": 25,
            "logic": 20,
            "service": 15,
            "services": 15,
            "core": 15,
            "application": 20,
            "usecases": 20,
            "domainmodel": 20,
        }

        for dir_path, weight in business_dirs.items():
            if self._exists(dir_path):
                confidence += weight
                indicators.append(f"Business layer ({dir_path})")

        # Data/Infrastructure layer indicators
        data_dirs = {
            "data": 20,
            "repository": 25,
            "repositories": 25,
            "persistence": 25,
            "dal": 25,  # Data Access Layer
            "infrastructure": 20,
            "database": 15,
            "storage": 15,
            "dao": 20,  # Data Access Objects
            "datamapper": 20,
        }

        for dir_path, weight in data_dirs.items():
            if self._exists(dir_path):
                confidence += weight
                indicators.append(f"Data layer ({dir_path})")

        # Check for multi-layer combinations (stronger indicator)
        # Presentation + Business + Data
        has_presentation = any(self._exists(d) for d in presentation_dirs.keys())
        has_business = any(self._exists(d) for d in business_dirs.keys())
        has_data = any(self._exists(d) for d in data_dirs.keys())

        if has_presentation and has_business and has_data:
            confidence += 30
            indicators.append("Three-layer architecture (presentation/business/data)")
        elif has_presentation and has_business:
            confidence += 20
            indicators.append("Two-layer architecture (presentation/business)")
        elif has_business and has_data:
            confidence += 20
            indicators.append("Two-layer architecture (business/data)")

        # Check for .NET/C# layered architecture patterns
        if self._exists("src") or self._exists("Source"):
            # Look for layered projects in solution
            for layer_name in ["Presentation", "Application", "Domain", "Infrastructure", "Persistence"]:
                if self._exists(f"src/{layer_name}") or (self.path / layer_name).exists():
                    confidence += 15
                    indicators.append(f".NET layer ({layer_name})")

        # Check for Java/Enterprise layered patterns
        java_patterns = [
            "src/main/java/com/**/controller",
            "src/main/java/com/**/service",
            "src/main/java/com/**/repository",
        ]

        has_java_layered = False
        for pattern in java_patterns:
            # Use glob to match patterns
            matches = list(self.path.glob(pattern.replace("**", "*")))
            if matches:
                has_java_layered = True
                confidence += 15
                break

        if has_java_layered:
            indicators.append("Java enterprise layered structure")

        # Check for src/ layered structure
        if self._exists("src") or self._exists("Source"):
            src_path = self.path / "src" if (self.path / "src").exists() else self.path / "Source"
            if src_path.is_dir():
                # Check for common layered source organization
                src_subdirs = [d.name for d in src_path.iterdir() if d.is_dir()]
                layered_subdirs = {"presentation", "domain", "application", "infrastructure", "data"}
                found_layers = layered_subdirs.intersection(set(src_subdirs))
                if len(found_layers) >= 2:
                    confidence += 20
                    indicators.append(f"src/ with layered structure: {', '.join(found_layers)}")

        # Normalize confidence to 0-100
        confidence = min(confidence, 100)

        if confidence > 0:
            self.patterns[self.PATTERN_LAYERED] = {
                "confidence": confidence,
                "indicators": indicators,
            }
