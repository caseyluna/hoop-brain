import argparse
import logging
import sys
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)


def ingest(module_name: str):
    """
    Main entry point for running ingestion modules
    """
    logging.info(f"🚀 [INGESTION] Starting module: {module_name}")

    # Simulate ingestion process
    logging.info(f"⏳ [{module_name}] Ingestion STARTED")
    logging.info(f"✅ [{module_name}] Ingestion COMPLETED")

    # Add timestamp to the log
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"📅 [{module_name}] Ingestion finished at {current_time}")


def main():
    parser = argparse.ArgumentParser(description="HoopBrain Ingestion Engine")
    parser.add_argument(
        "--module", required=True, help="Name of the ingestion module to run"
    )
    args = parser.parse_args()
    ingest(args.module)


if __name__ == "__main__":
    main()
