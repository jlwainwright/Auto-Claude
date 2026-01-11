"""
Debug script for usage count tracking.
"""

import tempfile
from pathlib import Path

from .overrides import (
    OverrideTokenManager,
    generate_override_token,
)
from .hook import output_validation_hook, reset_hook


def main():
    # Create temp project
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir).resolve()

        print(f"Project dir: {project_dir}")

        # Create a single-use token
        print("\n1. Creating token...")
        token = generate_override_token(
            rule_id="bash-rm-rf-root",
            project_dir=project_dir,
            scope="all",
            expiry_minutes=60,
            max_uses=1,
            reason="Testing usage count",
        )
        print(f"Token ID: {token.token_id}")
        print(f"Initial use_count: {token.use_count}")

        # Verify token was saved
        manager = OverrideTokenManager(project_dir)
        tokens = manager.list_tokens(rule_id="bash-rm-rf-root")
        print(f"\n2. Loaded tokens from storage:")
        print(f"   Count: {len(tokens)}")
        if tokens:
            print(f"   use_count: {tokens[0].use_count}")
            print(f"   max_uses: {tokens[0].max_uses}")

        # Create hook input
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
            "cwd": str(project_dir),
        }

        # Mock context with project_dir
        mock_context = type("obj", (object,), {"project_dir": project_dir})

        print("\n3. Calling hook...")
        import asyncio
        result = asyncio.run(output_validation_hook(
            input_data=input_data,
            tool_use_id=None,
            context=mock_context,
        ))
        print(f"Hook result: {result}")

        # Check usage count again
        print("\n4. Checking usage count after hook...")
        manager2 = OverrideTokenManager(project_dir)
        updated_tokens = manager2.list_tokens(rule_id="bash-rm-rf-root")
        print(f"   Loaded tokens: {len(updated_tokens)}")
        if updated_tokens:
            print(f"   use_count: {updated_tokens[0].use_count}")
            print(f"   max_uses: {updated_tokens[0].max_uses}")

            # Check token file directly
            import json
            tokens_file = project_dir / ".auto-claude" / "override-tokens.json"
            if tokens_file.exists():
                with open(tokens_file, "r") as f:
                    data = json.load(f)
                print(f"\n5. Direct file read:")
                print(f"   Tokens in file: {len(data.get('tokens', []))}")
                if data.get('tokens'):
                    print(f"   use_count from file: {data['tokens'][0]['use_count']}")


if __name__ == "__main__":
    main()
