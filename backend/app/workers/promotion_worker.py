"""Process due promotion campaigns once.

Local/production invocation from the backend directory:
    python -m app.workers.promotion_worker

Run this command periodically from cron or a platform scheduler. Campaigns are
persisted and atomically claimed, so overlapping invocations do not claim the
same scheduled campaign.
"""

from app.core.database import SessionLocal, create_db_tables
from app.services.promotion_service import process_due_campaigns


def main() -> None:
    create_db_tables()
    with SessionLocal() as db:
        results = process_due_campaigns(db)
    print(f"Processed {len(results)} due promotion campaign(s)")


if __name__ == "__main__":
    main()
