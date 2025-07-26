import asyncio
import sys

import dagger
from ingestion_engine import run_main_py


async def main():
    service = sys.argv[1] if len(sys.argv) > 1 else "ingestion-engine"

    async with dagger.Connection() as client:
        await run_main_py(client, service)


if __name__ == "__main__":
    asyncio.run(main())
