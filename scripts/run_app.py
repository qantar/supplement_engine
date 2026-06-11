#!/usr/bin/env python3
"""
Supplement Engine — unified stack orchestrator.

One entry point for Docker setup, conditional seeding, backend/frontend
containers, health checks, and smoke tests.

Examples:
    python scripts/run_app.py              # full stack + seed + verify
    python scripts/run_app.py up --open
    python scripts/run_app.py up --backend-only
    python scripts/run_app.py up --prod --no-seed
    python scripts/run_app.py seed --patients
    python scripts/run_app.py seed --neo4j --force
    python scripts/run_app.py status
    python scripts/run_app.py smoke
    python scripts/run_app.py down
    python scripts/run_app.py restart
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = ROOT / ".env.example"
ENV_FILE = ROOT / ".env"

NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "supplement_engine_dev"
PILOT_PATIENT_ID = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
PILOT_COHORT_SIZE = 16

DOCKER_DESKTOP_PATHS = (
    Path(r"C:\Program Files\Docker\Docker\Docker Desktop.exe"),
    Path(os.path.expandvars(r"%ProgramFiles%\Docker\Docker\Docker Desktop.exe")),
    Path(r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe"),
)

SERVICE_BACKEND = ("api", "neo4j", "postgres", "redis", "nginx")
SERVICE_FRONTEND = ("frontend",)
SERVICE_FULL = (*SERVICE_BACKEND, *SERVICE_FRONTEND)
SERVICE_SEED_DEPS = ("api", "neo4j", "postgres", "redis")


class StackProfile(str, Enum):
    DEV = "dev"
    PROD = "prod"


class StartupError(RuntimeError):
    pass


@dataclass
class RunConfig:
    profile: StackProfile = StackProfile.DEV
    services: tuple[str, ...] = SERVICE_FULL
    build: bool = True
    seed_neo4j: bool = False
    seed_patients: bool = False
    force_seed: bool = False
    smoke_api: bool = False
    smoke_frontend: bool = False
    wait_timeout: int = 300
    open_browser: bool = False


def log(msg: str, *, level: str = "info") -> None:
    prefix = {"info": "→", "ok": "✓", "warn": "!", "err": "✗", "step": "•"}.get(
        level, "→"
    )
    print(f"{prefix} {msg}", flush=True)


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    display = " ".join(cmd)
    log(f"$ {display}", level="step")
    result = subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        check=False,
        capture_output=capture,
        text=True,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise StartupError(f"Command failed ({result.returncode}): {display}\n{detail}")
    return result


def compose_cmd(*args: str, profile: StackProfile = StackProfile.DEV) -> list[str]:
    cmd = ["docker", "compose"]
    if profile is StackProfile.PROD:
        cmd.extend(["-f", "docker-compose.yml", "-f", "docker-compose.prod.yml"])
    cmd.extend(args)
    return cmd


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        log(".env present")
        return
    if not ENV_EXAMPLE.exists():
        raise StartupError("Missing .env.example — cannot create .env")
    shutil.copy(ENV_EXAMPLE, ENV_FILE)
    log("Created .env from .env.example")


def docker_info_ok() -> bool:
    try:
        run(["docker", "info"], capture=True)
        return True
    except StartupError:
        return False


def find_docker_desktop() -> Path | None:
    for path in DOCKER_DESKTOP_PATHS:
        if path.is_file():
            return path
    return None


def start_docker_desktop() -> bool:
    if platform.system() != "Windows":
        return False
    exe = find_docker_desktop()
    if exe is None:
        log("Docker Desktop executable not found — start it manually", level="warn")
        return False
    log(f"Launching Docker Desktop ({exe})")
    subprocess.Popen(
        [str(exe)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    return True


def wait_for_docker(timeout_sec: int = 180) -> None:
    if docker_info_ok():
        log("Docker daemon is running", level="ok")
        return
    log("Docker daemon not reachable", level="warn")
    start_docker_desktop()
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if docker_info_ok():
            log("Docker daemon is ready", level="ok")
            return
        remaining = int(deadline - time.time())
        log(f"Waiting for Docker… ({remaining}s left)")
        time.sleep(5)
    raise StartupError(
        f"Docker did not become ready within {timeout_sec}s. "
        "Open Docker Desktop and wait until it shows Running."
    )


def load_env_var(name: str, default: str = "") -> str:
    if not ENV_FILE.exists():
        return default
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == name:
            return value.strip().strip('"').strip("'")
    return default


def http_get(url: str, timeout: float = 10.0) -> tuple[int, str]:
    req = Request(url, headers={"User-Agent": "supplement-engine-run-app/2.0"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def http_post_json(
    url: str,
    payload: dict[str, Any],
    timeout: float = 60.0,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    req_headers = {
        "Content-Type": "application/json",
        "User-Agent": "supplement-engine-run-app/2.0",
    }
    if headers:
        req_headers.update(headers)
    req = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=req_headers,
    )
    with urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = body
        return resp.status, parsed


def wait_for(
    label: str,
    probe: Callable[[], bool],
    timeout_sec: int = 300,
    interval_sec: float = 5.0,
) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            if probe():
                log(f"{label} ready", level="ok")
                return
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
            pass
        remaining = int(deadline - time.time())
        log(f"Waiting for {label}… ({remaining}s left)")
        time.sleep(interval_sec)
    raise StartupError(f"Timed out waiting for {label} ({timeout_sec}s)")


def api_health_ok() -> bool:
    status, body = http_get("http://localhost:8000/health")
    if status != 200:
        return False
    data = json.loads(body)
    return bool(data.get("neo4j")) and bool(data.get("postgres"))


def frontend_ok() -> bool:
    status, _ = http_get("http://localhost:3000")
    return status == 200


def nginx_ok() -> bool:
    status, _ = http_get("http://localhost/health")
    return status == 200


def container_running(container_name: str, profile: StackProfile) -> bool:
    result = run(
        ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
        capture=True,
        check=False,
    )
    return container_name in result.stdout


def ensure_docker(*, timeout: int) -> None:
    if shutil.which("docker") is None:
        raise StartupError(
            "Docker CLI not found. Install Docker Desktop: "
            "https://www.docker.com/products/docker-desktop/"
        )
    ensure_env_file()
    wait_for_docker(timeout_sec=min(timeout, 300))


def bring_up(cfg: RunConfig) -> None:
    args = ["up", "-d"]
    if cfg.build:
        args.append("--build")
    args.extend(cfg.services)
    log(f"Starting containers: {', '.join(cfg.services)}")
    run(compose_cmd(*args, profile=cfg.profile))


def bring_down(cfg: RunConfig) -> None:
    log("Stopping containers…")
    run(compose_cmd("down", profile=cfg.profile))


def show_status(cfg: RunConfig) -> None:
    run(compose_cmd("ps", profile=cfg.profile))


def wait_for_services(cfg: RunConfig) -> None:
    needs_api = "api" in cfg.services
    needs_frontend = "frontend" in cfg.services
    needs_nginx = "nginx" in cfg.services

    if needs_api:
        wait_for(
            "API health (neo4j + postgres)",
            api_health_ok,
            timeout_sec=cfg.wait_timeout,
        )
    if needs_frontend:
        wait_for("Frontend console", frontend_ok, timeout_sec=min(cfg.wait_timeout, 180))
    if needs_nginx:
        wait_for("Nginx proxy", nginx_ok, timeout_sec=60)


def seed_neo4j_graph(cfg: RunConfig) -> None:
    log("Seeding Neo4j knowledge graph…")
    run(
        compose_cmd(
            "exec", "-T", "neo4j",
            "cypher-shell", "-u", NEO4J_USER, "-p", NEO4J_PASSWORD,
            "-f", "/var/lib/neo4j/import/seed.cypher",
            profile=cfg.profile,
        ),
        capture=True,
    )
    log("Neo4j seed complete", level="ok")


def seed_patient_cohort(cfg: RunConfig) -> None:
    log(f"Seeding {PILOT_COHORT_SIZE} pilot patients into Postgres…")
    run(
        compose_cmd(
            "exec", "-T", "api",
            "python", "scripts/seed_patient_realm.py",
            profile=cfg.profile,
        ),
        capture=True,
    )
    log("Patient realm seed complete", level="ok")


def ensure_seed_dependencies(cfg: RunConfig) -> None:
    """Start minimal stack if seed targets are not already running."""
    name_map = {
        "api": "supplement_api",
        "neo4j": "supplement_neo4j",
        "postgres": "supplement_postgres",
        "redis": "supplement_redis",
    }
    missing = [
        svc for svc, cname in name_map.items()
        if not container_running(cname, cfg.profile)
    ]

    if not missing:
        log("Seed dependencies already running", level="ok")
        wait_for("API health", api_health_ok, timeout_sec=cfg.wait_timeout)
        return

    log(f"Starting seed dependencies: {', '.join(missing)}")
    seed_cfg = RunConfig(
        profile=cfg.profile,
        services=tuple(dict.fromkeys(missing)),
        build=cfg.build,
        wait_timeout=cfg.wait_timeout,
    )
    bring_up(seed_cfg)
    wait_for_services(seed_cfg)


def run_seeding(cfg: RunConfig) -> None:
    if not cfg.seed_neo4j and not cfg.seed_patients:
        log("No seed steps selected — skipping", level="warn")
        return

    ensure_seed_dependencies(cfg)

    if cfg.seed_neo4j:
        seed_neo4j_graph(cfg)
    if cfg.seed_patients:
        seed_patient_cohort(cfg)

    if cfg.seed_neo4j or cfg.seed_patients:
        wait_for("API post-seed", api_health_ok, timeout_sec=60)


def api_key_for_requests(cfg: RunConfig) -> str | None:
    if cfg.profile is not StackProfile.PROD:
        return None
    keys = load_env_var("API_KEYS", "pilot-dev-key-change-me")
    return keys.split(",")[0].strip() or None


def smoke_test_api(cfg: RunConfig) -> None:
    example = ROOT / "examples" / "patient_t2dm_riyadh.json"
    if not example.exists():
        log("API smoke skipped — example payload missing", level="warn")
        return

    payload: dict[str, Any] = json.loads(example.read_text(encoding="utf-8"))
    if cfg.profile is StackProfile.PROD:
        payload = {
            "patient_id": PILOT_PATIENT_ID,
            "options": payload.get("options", {}),
        }

    headers: dict[str, str] = {}
    key = api_key_for_requests(cfg)
    if key:
        headers["X-API-Key"] = key

    log("Smoke test — POST /v1/recommendations (nginx)…")
    status, data = http_post_json(
        "http://localhost/v1/recommendations",
        payload,
        timeout=120.0,
        headers=headers,
    )
    if status != 200:
        raise StartupError(f"API smoke test failed (HTTP {status}): {data}")

    recs = data.get("recommendations", []) if isinstance(data, dict) else []
    session_id = data.get("session_id") if isinstance(data, dict) else None
    log(
        f"API smoke OK — session {session_id}, {len(recs)} recommendation(s)",
        level="ok",
    )


def smoke_test_frontend_proxy() -> None:
    log("Smoke test — frontend proxy /api/recommendations…")
    payload = {
        "patient_id": PILOT_PATIENT_ID,
        "options": {"max_recommendations": 3},
    }
    status, data = http_post_json(
        "http://localhost:3000/api/recommendations",
        payload,
        timeout=120.0,
    )
    if status != 200:
        raise StartupError(f"Frontend smoke test failed (HTTP {status}): {data}")
    recs = data.get("recommendations", []) if isinstance(data, dict) else []
    log(f"Frontend smoke OK — {len(recs)} recommendation(s)", level="ok")


def run_smoke_tests(cfg: RunConfig) -> None:
    if cfg.smoke_api:
        smoke_test_api(cfg)
    if cfg.smoke_frontend:
        smoke_test_frontend_proxy()


def print_summary(cfg: RunConfig) -> None:
    print()
    log("=== Supplement Engine ===", level="ok")
    print()
    if "frontend" in cfg.services:
        print("  Clinician console   http://localhost:3000")
    if "api" in cfg.services or "nginx" in cfg.services:
        print("  Swagger UI          http://localhost/docs")
        print("  API health          http://localhost:8000/health")
        print("  API via nginx       http://localhost/v1/recommendations")
    if "neo4j" in cfg.services:
        print("  Neo4j browser       http://localhost:7474")
        print(f"                      login: {NEO4J_USER} / {NEO4J_PASSWORD}")
    print()
    if cfg.profile is StackProfile.PROD:
        print("  Profile: PRODUCTION PILOT (patient_id only, API key required)")
    else:
        print("  Profile: DEVELOPMENT")
    print()
    print("  Commands:")
    print("    python scripts/run_app.py status")
    print("    python scripts/run_app.py seed --all")
    print("    python scripts/run_app.py down")
    print()


def cmd_up(cfg: RunConfig) -> None:
    ensure_docker(timeout=cfg.wait_timeout)
    bring_up(cfg)
    wait_for_services(cfg)
    show_status(cfg)
    run_seeding(cfg)
    run_smoke_tests(cfg)
    print_summary(cfg)
    if cfg.open_browser:
        if "frontend" in cfg.services:
            webbrowser.open("http://localhost:3000")
        webbrowser.open("http://localhost/docs")


def cmd_down(cfg: RunConfig) -> None:
    ensure_docker(timeout=60)
    bring_down(cfg)
    log("Stack stopped", level="ok")


def cmd_seed(cfg: RunConfig) -> None:
    ensure_docker(timeout=cfg.wait_timeout)
    run_seeding(cfg)
    log("Seeding finished", level="ok")


def cmd_status(cfg: RunConfig) -> None:
    ensure_docker(timeout=60)
    show_status(cfg)
    print()
    checks: list[tuple[str, Callable[[], bool]]] = []
    if container_running("supplement_api", cfg.profile):
        checks.append(("API health", api_health_ok))
    if container_running("supplement_frontend", cfg.profile):
        checks.append(("Frontend", frontend_ok))
    if container_running("supplement_nginx", cfg.profile):
        checks.append(("Nginx", nginx_ok))

    for label, probe in checks:
        try:
            ok = probe()
            log(f"{label}: {'OK' if ok else 'NOT READY'}", level="ok" if ok else "warn")
        except Exception as exc:
            log(f"{label}: FAILED ({exc})", level="err")


def cmd_smoke(cfg: RunConfig) -> None:
    ensure_docker(timeout=60)
    if not api_health_ok():
        raise StartupError("API not healthy — run: python scripts/run_app.py up")
    run_smoke_tests(cfg)
    log("Smoke tests passed", level="ok")


def cmd_restart(cfg: RunConfig) -> None:
    cmd_down(cfg)
    cmd_up(cfg)


def resolve_services(args: argparse.Namespace) -> tuple[str, ...]:
    if args.backend_only:
        return SERVICE_BACKEND
    if args.frontend_only:
        # Frontend container depends on healthy API
        return ("api", "neo4j", "postgres", "redis", *SERVICE_FRONTEND)
    return SERVICE_FULL


def resolve_seed_flags(args: argparse.Namespace, command: str) -> tuple[bool, bool]:
    if command == "seed":
        if args.all or (not args.neo4j and not args.patients):
            return True, True
        return args.neo4j, args.patients
    # up command
    if args.no_seed:
        return False, False
    if args.seed_neo4j and not args.seed_patients:
        return True, False
    if args.seed_patients and not args.seed_neo4j:
        return False, True
    return True, True  # default: both


def resolve_smoke_flags(
    args: argparse.Namespace,
    command: str,
    services: tuple[str, ...],
    profile: StackProfile,
) -> tuple[bool, bool]:
    if args.no_smoke or command in ("seed", "down", "status"):
        return False, False
    if command == "smoke":
        fe = "frontend" in services or container_running("supplement_frontend", profile)
        return True, fe
    smoke_api = "api" in services or "nginx" in services
    smoke_fe = "frontend" in services
    return smoke_api, smoke_fe


def build_config(args: argparse.Namespace, command: str) -> RunConfig:
    profile = StackProfile.PROD if args.prod else StackProfile.DEV
    services = resolve_services(args)
    seed_neo4j, seed_patients = resolve_seed_flags(args, command)
    smoke_api, smoke_frontend = resolve_smoke_flags(args, command, services, profile)

    return RunConfig(
        profile=profile,
        services=services,
        build=not args.no_build,
        seed_neo4j=seed_neo4j,
        seed_patients=seed_patients,
        force_seed=args.force,
        smoke_api=smoke_api,
        smoke_frontend=smoke_frontend,
        wait_timeout=args.timeout,
        open_browser=args.open,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Supplement Engine — unified Docker, seed, and verify orchestrator.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_app.py                    Full stack (default: up)
  python scripts/run_app.py up --open          Start + open browser
  python scripts/run_app.py up --backend-only  API stack, no frontend container
  python scripts/run_app.py up --no-seed       Skip all seeding
  python scripts/run_app.py seed --all         Seed Neo4j + 16 pilot patients
  python scripts/run_app.py seed --patients    Postgres patient realm only
  python scripts/run_app.py status             Container + health status
  python scripts/run_app.py smoke              Run recommendation smoke tests
  python scripts/run_app.py down               Stop containers
  python scripts/run_app.py restart            down then up
""",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="up",
        choices=("up", "down", "seed", "status", "smoke", "restart"),
        help="Action to run (default: up)",
    )

    # Profile & stack scope
    parser.add_argument("--prod", action="store_true", help="Use docker-compose.prod.yml overlay")
    stack = parser.add_mutually_exclusive_group()
    stack.add_argument("--backend-only", action="store_true", help="API + DB + nginx (no frontend)")
    stack.add_argument("--frontend-only", action="store_true", help="Frontend + required API deps")

    # Build & wait
    parser.add_argument("--no-build", action="store_true", help="Skip docker compose --build")
    parser.add_argument("--timeout", type=int, default=300, help="Health wait timeout seconds")

    # Seeding (conditional)
    seed = parser.add_mutually_exclusive_group()
    seed.add_argument("--no-seed", action="store_true", help="[up] Skip all seeding")
    seed.add_argument("--seed-neo4j", action="store_true", help="[up] Seed Neo4j only")
    seed.add_argument("--seed-patients", action="store_true", help="[up] Seed Postgres patients only")
    parser.add_argument("--all", action="store_true", help="[seed] Seed Neo4j + patients (default)")
    parser.add_argument("--neo4j", action="store_true", help="[seed] Seed Neo4j knowledge graph")
    parser.add_argument("--patients", action="store_true", help="[seed] Seed pilot patient cohort")
    parser.add_argument("--force", action="store_true", help="Re-run seed scripts even if already seeded")

    # Verification
    parser.add_argument("--no-smoke", action="store_true", help="Skip smoke tests")
    parser.add_argument("--open", action="store_true", help="Open console + Swagger in browser")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    os.chdir(ROOT)

    cfg = build_config(args, args.command)
    handlers = {
        "up": cmd_up,
        "down": cmd_down,
        "seed": cmd_seed,
        "status": cmd_status,
        "smoke": cmd_smoke,
        "restart": cmd_restart,
    }

    print()
    log(f"Supplement Engine — {args.command}")
    if args.command == "up":
        log(
            f"Stack: {', '.join(cfg.services)} | "
            f"seed neo4j={cfg.seed_neo4j} patients={cfg.seed_patients} | "
            f"profile={cfg.profile.value}",
        )
    print()

    try:
        handlers[args.command](cfg)
        return 0
    except StartupError as exc:
        print()
        log(str(exc), level="err")
        print()
        print("  Troubleshooting:")
        print("    python scripts/run_app.py status")
        print("    docker compose logs api --tail 50")
        print("    docker compose logs frontend --tail 50")
        return 1
    except KeyboardInterrupt:
        print()
        log("Interrupted", level="warn")
        return 130


if __name__ == "__main__":
    sys.exit(main())
