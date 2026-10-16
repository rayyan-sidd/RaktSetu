import sys

from backend.app.services.eraktkosh.ingestion import run_ingestion_cli

if __name__ == "__main__":
    sys.exit(run_ingestion_cli())
