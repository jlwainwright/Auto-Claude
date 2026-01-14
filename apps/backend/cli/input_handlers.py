"""
Input Handlers
==============

Reusable user input collection utilities for CLI commands.
"""

import sys
from pathlib import Path

# Ensure parent directory is in path for imports (before other imports)
_PARENT_DIR = Path(__file__).parent.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

from ui import (
    Icons,
    MenuOption,
    box,
    icon,
    muted,
    print_status,
    select_menu,
)

from security.input_screener import InputScreener, ScreeningVerdict


def collect_user_input_interactive(
    title: str,
    subtitle: str,
    prompt_text: str,
    allow_file: bool = True,
    allow_paste: bool = True,
    project_dir: Path | None = None,
    screen_input: bool = True,
) -> str | None:
    """
    Collect user input through an interactive menu.

    Provides multiple input methods:
    - Type directly
    - Paste from clipboard
    - Read from file (optional)

    Args:
        title: Menu title
        subtitle: Menu subtitle
        prompt_text: Text to display in the input box
        allow_file: Whether to allow file input (default: True)
        allow_paste: Whether to allow paste option (default: True)
        project_dir: Project directory for screening allowlist (default: None)
        screen_input: Whether to screen input for security (default: True)

    Returns:
        The collected input string, or None if cancelled or rejected
    """
    # Build options list
    options = [
        MenuOption(
            key="type",
            label="Type instructions",
            icon=Icons.EDIT,
            description="Enter text directly",
        ),
    ]

    if allow_paste:
        options.append(
            MenuOption(
                key="paste",
                label="Paste from clipboard",
                icon=Icons.CLIPBOARD,
                description="Paste text you've copied (Cmd+V / Ctrl+Shift+V)",
            )
        )

    if allow_file:
        options.append(
            MenuOption(
                key="file",
                label="Read from file",
                icon=Icons.DOCUMENT,
                description="Load text from a file",
            )
        )

    options.extend(
        [
            MenuOption(
                key="skip",
                label="Continue without input",
                icon=Icons.SKIP,
                description="Skip this step",
            ),
            MenuOption(
                key="quit",
                label="Quit",
                icon=Icons.DOOR,
                description="Exit",
            ),
        ]
    )

    choice = select_menu(
        title=title,
        options=options,
        subtitle=subtitle,
        allow_quit=False,  # We have explicit quit option
    )

    if choice == "quit" or choice is None:
        return None

    if choice == "skip":
        return ""

    user_input = ""

    if choice == "file":
        # Read from file
        user_input = read_from_file()
        if user_input is None:
            return None

    elif choice in ["type", "paste"]:
        user_input = read_multiline_input(prompt_text)
        if user_input is None:
            return None

    # Screen input for security if enabled
    if screen_input and user_input:
        screening_result = _screen_user_input(user_input, project_dir)
        if screening_result is None:
            # Input was rejected, return None to indicate cancellation
            return None

    return user_input


def _screen_user_input(user_input: str, project_dir: Path | None) -> str | None:
    """
    Screen user input for potential security threats.

    Args:
        user_input: The input to screen
        project_dir: Project directory for allowlist support

    Returns:
        The original input if safe, None if rejected
    """
    if not user_input or not user_input.strip():
        # Empty input is safe
        return user_input

    try:
        # Initialize screener with project directory
        screener = InputScreener(project_dir=str(project_dir) if project_dir else None)

        # Screen the input
        result = screener.screen_input(user_input)

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
        return user_input

    except Exception as e:
        # If screening fails, log error but allow input through
        # (fail-open to not block legitimate work)
        print()
        print_status(f"Security screening error: {e}", "warning")
        print(f"  {muted('Continuing with input...')}")
        print()
        return user_input


def read_from_file() -> str | None:
    """
    Read text content from a file path provided by the user.

    Returns:
        File contents as string, or None if cancelled/error
    """
    print()
    print(f"{icon(Icons.DOCUMENT)} Enter the path to your file:")
    try:
        file_path_input = input(f"  {icon(Icons.POINTER)} ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        print_status("Cancelled.", "warning")
        return None

    if not file_path_input:
        print_status("No file path provided.", "warning")
        return None

    try:
        # Expand ~ and resolve path
        file_path = Path(file_path_input).expanduser().resolve()
        if file_path.exists():
            content = file_path.read_text().strip()
            if content:
                print_status(
                    f"Loaded {len(content)} characters from file",
                    "success",
                )
                return content
            else:
                print_status("File is empty.", "error")
                return None
        else:
            print_status(f"File not found: {file_path}", "error")
            return None
    except PermissionError:
        print_status(f"Permission denied: cannot read {file_path_input}", "error")
        return None
    except Exception as e:
        print_status(f"Error reading file: {e}", "error")
        return None


def read_multiline_input(prompt_text: str) -> str | None:
    """
    Read multi-line input from the user.

    Args:
        prompt_text: Text to display in the prompt box

    Returns:
        User input as string, or None if cancelled
    """
    print()
    content = [
        prompt_text,
        muted("Press Enter on an empty line when done."),
    ]
    print(box(content, width=60, style="light"))
    print()

    lines = []
    empty_count = 0
    while True:
        try:
            line = input()
            if line == "":
                empty_count += 1
                if empty_count >= 1:  # Stop on first empty line
                    break
            else:
                empty_count = 0
                lines.append(line)
        except KeyboardInterrupt:
            print()
            print_status("Cancelled.", "warning")
            return None
        except EOFError:
            break

    return "\n".join(lines).strip()
