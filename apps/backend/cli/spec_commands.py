"""
Spec Commands
=============

CLI commands for managing specs (listing, finding, etc.)
"""

import sys
from pathlib import Path

# Ensure parent directory is in path for imports (before other imports)
_PARENT_DIR = Path(__file__).parent.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

from progress import count_subtasks
from ui import Icons, muted, icon, print_status
from workspace import get_existing_build_worktree

from security.input_screener import InputScreener, ScreeningVerdict

from .utils import get_specs_dir


def list_specs(project_dir: Path) -> list[dict]:
    """
    List all specs in the project.

    Args:
        project_dir: Project root directory

    Returns:
        List of spec info dicts with keys: number, name, path, status, progress
    """
    specs_dir = get_specs_dir(project_dir)
    specs = []

    if not specs_dir.exists():
        return specs

    for spec_folder in sorted(specs_dir.iterdir()):
        if not spec_folder.is_dir():
            continue

        # Parse folder name (e.g., "001-initial-app")
        folder_name = spec_folder.name
        parts = folder_name.split("-", 1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue

        number = parts[0]
        name = parts[1]

        # Check for spec.md
        spec_file = spec_folder / "spec.md"
        if not spec_file.exists():
            continue

        # Check for existing build in worktree
        has_build = get_existing_build_worktree(project_dir, folder_name) is not None

        # Check progress via implementation_plan.json
        plan_file = spec_folder / "implementation_plan.json"
        if plan_file.exists():
            completed, total = count_subtasks(spec_folder)
            if total > 0:
                if completed == total:
                    status = "complete"
                else:
                    status = "in_progress"
                progress = f"{completed}/{total}"
            else:
                status = "initialized"
                progress = "0/0"
        else:
            status = "pending"
            progress = "-"

        # Add build indicator
        if has_build:
            status = f"{status} (has build)"

        specs.append(
            {
                "number": number,
                "name": name,
                "folder": folder_name,
                "path": spec_folder,
                "status": status,
                "progress": progress,
                "has_build": has_build,
            }
        )

    return specs


def _screen_quickstart_input(task: str, project_dir: Path) -> str | None:
    """
    Screen quick-start task input for security threats.

    Args:
        task: The task description to screen
        project_dir: Project root directory

    Returns:
        The task if safe, None if rejected
    """
    if not task or not task.strip():
        return task

    try:
        # Initialize screener with project directory
        screener = InputScreener(project_dir=str(project_dir))

        # Screen the input
        result = screener.screen_input(task)

        # Check if input is safe
        if result.verdict == ScreeningVerdict.REJECTED:
            print()
            print_status("Input rejected by security screening", "error")
            print()
            print(f"  {muted('Reason:')} {result.reason}")
            print()

            # Show detected patterns if available
            if result.detected_patterns:
                print(f"  {muted('Detected patterns:')}")
                for pattern in result.detected_patterns[:5]:  # Show first 5
                    severity_icon = {
                        "critical": icon(Icons.ERROR),
                        "high": icon(Icons.ERROR),
                        "medium": icon(Icons.WARNING),
                        "low": icon(Icons.WARNING),
                    }.get(pattern.severity, icon(Icons.WARNING))

                    print(
                        f"    {severity_icon} {pattern.name} "
                        f"[{pattern.severity}]"
                    )

                if len(result.detected_patterns) > 5:
                    more_count = len(result.detected_patterns) - 5
                    print(
                        f"    {muted(f'... and {more_count} more')}"
                    )

            print()
            print(
                f"  {muted('If this is a false positive, please report it:')}"
            )
            print(f"  {muted('https://github.com/Andymik90/auto-claude/issues')}"
            )
            print()

            return None  # Signal rejection

        elif result.verdict == ScreeningVerdict.SUSPICIOUS:
            # Suspicious but not rejected - warn user but continue
            print()
            print_status(
                "Warning: Input contains potentially suspicious patterns",
                "warning",
            )
            print(f"  {muted('Reason:')} {result.reason}")
            print()

            # Ask user if they want to continue
            print("  Do you want to continue anyway?")
            print(f"    {icon(Icons.POINTER)} Enter 'yes' to continue, or press Enter to cancel")

            try:
                confirm = input("  > ").strip().lower()
                if confirm not in ["yes", "y"]:
                    print_status("Cancelled.", "warning")
                    return None
            except (KeyboardInterrupt, EOFError):
                print()
                print_status("Cancelled.", "warning")
                return None

        # Input is safe or user accepted suspicious input
        return task

    except Exception as e:
        # If screening fails, log error but allow input through
        # (fail-open to not block legitimate work)
        print()
        print_status(f"Security screening error: {e}", "warning")
        print(f"  {muted('Continuing with input...')}")
        print()
        return task


def print_specs_list(project_dir: Path, auto_create: bool = True) -> None:
    """Print a formatted list of all specs.

    Args:
        project_dir: Project root directory
        auto_create: If True and no specs exist, automatically launch spec creation
    """
    import subprocess

    specs = list_specs(project_dir)

    if not specs:
        print("\nNo specs found.")

        if auto_create:
            # Get the backend directory and find spec_runner.py
            backend_dir = Path(__file__).parent.parent
            spec_runner = backend_dir / "runners" / "spec_runner.py"

            # Find Python executable - use current interpreter
            python_path = sys.executable

            if spec_runner.exists() and python_path:
                # Quick prompt for task description
                print("\n" + "=" * 60)
                print("  QUICK START")
                print("=" * 60)
                print("\nWhat do you want to build?")
                print(
                    "(Enter a brief description, or press Enter for interactive mode)\n"
                )

                try:
                    task = input("> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nCancelled.")
                    return

                if task:
                    # Screen input for security before launching spec_runner
                    screened_task = _screen_quickstart_input(task, project_dir)
                    if screened_task is None:
                        # Input was rejected by screening
                        return

                    # Direct mode: create spec and start building
                    print(f"\nStarting build for: {screened_task}\n")
                    subprocess.run(
                        [
                            python_path,
                            str(spec_runner),
                            "--task",
                            screened_task,
                            "--complexity",
                            "simple",
                            "--auto-approve",
                        ],
                        cwd=project_dir,
                    )
                else:
                    # Interactive mode
                    print("\nLaunching interactive mode...\n")
                    subprocess.run(
                        [python_path, str(spec_runner), "--interactive"],
                        cwd=project_dir,
                    )
                return
            else:
                print("\nCreate your first spec:")
                print("  python runners/spec_runner.py --interactive")
        else:
            print("\nCreate your first spec:")
            print("  python runners/spec_runner.py --interactive")
        return

    print("\n" + "=" * 70)
    print("  AVAILABLE SPECS")
    print("=" * 70)
    print()

    # Status symbols
    status_symbols = {
        "complete": "[OK]",
        "in_progress": "[..]",
        "initialized": "[--]",
        "pending": "[  ]",
    }

    for spec in specs:
        # Get base status for symbol
        base_status = spec["status"].split(" ")[0]
        symbol = status_symbols.get(base_status, "[??]")

        print(f"  {symbol} {spec['folder']}")
        status_line = f"       Status: {spec['status']} | Subtasks: {spec['progress']}"
        print(status_line)
        print()

    print("-" * 70)
    print("\nTo run a spec:")
    print("  python auto-claude/run.py --spec 001")
    print("  python auto-claude/run.py --spec 001-feature-name")
    print()
