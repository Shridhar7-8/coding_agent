import os
import sys
import asyncio
from pathlib import Path
from models import Model
from coder import Coder

async def main(argv=None):
    """Main entry point for CLI based coding agent"""

    if argv is None:
        argv = sys.argv[1:]

    files = []
    model = "gpt-4"
    message = None

    i=0

    while(i<len(argv)):
        args = argv[i]
        if args == "--model":
            model = argv[i+1]
            i += 2
        elif args == "--message" or "-m":
            message = argv[i+1]
            i += 2
        elif not args.startswith("--"):
            files.append(args)
            i += 1
        else:
            i += 1
    
    llm_model = Model(model)
    coder = Coder(model=llm_model, files=files)

    if message:
        await coder.run_single(message)
    else:
        await coder.run_chat_loop()


if __name__ == "__main__":
    asyncio.run(main())




