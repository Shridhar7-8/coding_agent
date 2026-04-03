"""Entry point for running as module: python -m coding_agent"""

import asyncio
import sys

from coding_agent.cli.main import main

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
