"""Main async pipeline orchestrating the 3-phase agent system."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from loguru import logger

from agents.macro_analyst import MacroAnalyst
from agents.fundamental_screener import FundamentalScreener
from agents.technical_analyst import TechnicalAnalyst
from agents.catalyst_hunter import CatalystHunter
from agents.sentiment_analyst import SentimentAnalyst
from agents.risk_manager import RiskManager
from agents.portfolio_manager import PortfolioManager
from orchestrator.message_bus import MessageBus
from output.excel_generator import generate_report


async def run_pipeline(skip_screener: bool = False) -> Path:
    """
    Execute the full 3-phase analysis pipeline.

    Phase 0 (Sequential): Macro Analyst → Fundamental Screener
    Phase 1 (Parallel):   Technical Analyst, Catalyst Hunter, Sentiment Analyst
    Phase 2 (Sequential): Risk Manager → Portfolio Manager → Excel Report

    Returns path to generated Excel report.
    """
    bus = MessageBus()
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("TRADING COMPETITION ANALYSIS PIPELINE")
    logger.info(f"Started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # ── Phase 0: Sequential ──────────────────────────────────────────────
    logger.info("\n--- PHASE 0: Macro Analysis & Fundamental Screening ---")

    macro_agent = MacroAnalyst(bus)
    await macro_agent.run()
    logger.info("✓ Macro Analyst complete")

    fundamental_agent = FundamentalScreener(bus)
    await fundamental_agent.run()
    logger.info("✓ Fundamental Screener complete")

    # ── Phase 1: Parallel ────────────────────────────────────────────────
    logger.info("\n--- PHASE 1: Technical, Catalyst & Sentiment Analysis (parallel) ---")

    technical_agent = TechnicalAnalyst(bus)
    catalyst_agent = CatalystHunter(bus)
    sentiment_agent = SentimentAnalyst(bus)

    phase1_agents = [
        ("Technical Analyst", technical_agent),
        ("Catalyst Hunter", catalyst_agent),
        ("Sentiment Analyst", sentiment_agent),
    ]

    results = await asyncio.gather(
        *(agent.run() for _, agent in phase1_agents),
        return_exceptions=True,
    )

    for (label, _), result in zip(phase1_agents, results):
        if isinstance(result, Exception):
            logger.error(f"✗ {label} failed: {result}")
        else:
            logger.info(f"✓ {label} complete")

    # ── Phase 2: Sequential ──────────────────────────────────────────────
    logger.info("\n--- PHASE 2: Risk Management & Portfolio Construction ---")

    risk_agent = RiskManager(bus)
    await risk_agent.run()
    logger.info("✓ Risk Manager complete")

    portfolio_agent = PortfolioManager(bus)
    await portfolio_agent.run()
    logger.info("✓ Portfolio Manager complete")

    # ── Generate Report ──────────────────────────────────────────────────
    logger.info("\n--- Generating Excel Report ---")
    report_path = generate_report(bus)
    logger.info(f"✓ Report generated: {report_path}")

    # Dump bus for debugging
    debug_path = Path(__file__).parent.parent / "output" / "reports" / "bus_dump.json"
    bus.dump_json(debug_path)

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Pipeline complete in {elapsed:.1f}s")
    logger.info(f"Report: {report_path}")
    logger.info(f"{'=' * 60}")

    return report_path
