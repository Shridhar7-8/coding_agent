"""Main entry point for the CLI."""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import List, Optional

from coding_agent.application.dto.requests import CodingRequest
from coding_agent.application.services.coding_service import CodingService
from coding_agent.config.container import Container, get_container


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser.

    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        prog="coding-agent",
        description="AI-powered code editing assistant",
    )

    parser.add_argument(
        "files",
        nargs="*",
        help="Files to analyze/edit",
        type=Path,
    )

    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o",
        help="LLM model to use (default: gpt-4o)",
    )

    parser.add_argument(
        "--message",
        "-m",
        type=str,
        help="Single message mode (non-interactive)",
    )

    parser.add_argument(
        "--edit-format",
        type=str,
        default="search_replace",
        choices=["search_replace", "diff", "udiff"],
        help="Edit format for changes",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )

    return parser


async def run_single(
    coding_service: CodingService,
    message: str,
    files: List[Path],
    edit_format: str,
) -> None:
    """Run a single coding request.

    Args:
        coding_service: Service to use
        message: User message
        files: Files to analyze
        edit_format: Edit format
    """
    request = CodingRequest(
        message=message,
        files=files,
        edit_format=edit_format,
    )

    response = await coding_service.process_request(request)

    print(f"\nAssistant: {response.message}\n")

    if response.has_edits:
        print(f"Applied {len(response.successful_edits)} edits:")
        for edit in response.successful_edits:
            print(f"  ✓ {edit.file_path}")

        if response.failed_edits:
            print(f"\nFailed {len(response.failed_edits)} edits:")
            for edit in response.failed_edits:
                print(f"  ✗ {edit.file_path}: {edit.error_message}")


async def run_chat_loop(
    coding_service: CodingService,
    files: List[Path],
    edit_format: str,
) -> None:
    """Run interactive chat loop.

    Args:
        coding_service: Service to use
        files: Files to analyze
        edit_format: Edit format
    """
    print("\n🤖 Coding Agent - Interactive Mode")
    print("Type 'exit' or 'quit' to exit\n")

    chat_history = []

    while True:
        try:
            user_input = input("> ").strip()

            if user_input.lower() in ("exit", "quit"):
                print("Goodbye!")
                break

            if not user_input:
                continue

            request = CodingRequest(
                message=user_input,
                files=files,
                edit_format=edit_format,
                chat_history=chat_history,
            )

            response = await coding_service.process_request(request)

            print(f"\nAssistant: {response.message}\n")

            if response.has_edits:
                for edit in response.successful_edits:
                    print(f"  ✓ Applied edit to {edit.file_path}")

                for edit in response.failed_edits:
                    print(f"  ✗ Failed: {edit.file_path} - {edit.error_message}")

                print()

            # Update chat history
            chat_history.append({"role": "user", "content": user_input})
            chat_history.append({"role": "assistant", "content": response.message})

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}\n")


async def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point.

    Args:
        argv: Command line arguments

    Returns:
        Exit code
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # Get container and coding service
    container = get_container()
    coding_service = container.coding_service

    try:
        if args.message:
            await run_single(
                coding_service,
                args.message,
                args.files,
                args.edit_format,
            )
        else:
            await run_chat_loop(
                coding_service,
                args.files,
                args.edit_format,
            )

        return 0

    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
