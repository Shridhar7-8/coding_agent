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
    model = "gpt-4o"
    message = None

    i=0

    while(i<len(argv)):
        args = argv[i]
        if args == "--model":
            if i+1 < len(argv):
                model = argv[i+1]
                i += 2
            else:
                print("Error: --model requires a value")
                return
        elif args == "--message" or args == "-m":
            if i+1 < len(argv):
                message = argv[i+1]
                i += 2
            else:
                print("Error: --message requires a value")
                return
        elif not args.startswith("--"):
            files.append(args)
            i += 1
        else:
            print(f"Unknown argument: {args}")
            i += 1
    
    llm_model = Model(model)
    coder = Coder(model=llm_model, files=files)

    if message:
        await coder.run_single(message)
    else:
        await coder.run_chat_loop()


if __name__ == "__main__":
    asyncio.run(main())




