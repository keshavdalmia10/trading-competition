"""Entry point for the Trading Competition Multi-Agent Analysis System."""

import asyncio
import sys
from pathlib import Path

from loguru import logger

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add(
    "output/reports/pipeline.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name} - {message}",
    level="DEBUG",
    rotation="10 MB",
)


async def main():
    from orchestrator.pipeline import run_pipeline

    logger.info("Starting Trading Competition Analysis System")
    logger.info("=" * 50)

    try:
        report_path = await run_pipeline()
        logger.info(f"\nReport generated successfully: {report_path}")
        print(f"\n{'='*50}")
        print(f"Analysis complete!")
        print(f"Report: {report_path}")
        print(f"{'='*50}")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
