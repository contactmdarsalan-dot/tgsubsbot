"""Rebuild MongoDB indexes — run after schema changes or collection migrations."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import ensure_indexes


async def main():
    print("Rebuilding all MongoDB indexes...")
    await ensure_indexes()
    print("Done! All indexes rebuilt.")


if __name__ == "__main__":
    asyncio.run(main())
