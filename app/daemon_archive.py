"""
daemon_archive.py — weekly archive daemon.

Runs as a separate process inside the Docker container.
Every Sunday evening (checks at 22:00 МСК) archives all DONE tasks.
Checks every 30 minutes; actually archives only once per week.
"""

import time
import logging
import sys
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [archive] %(levelname)s %(message)s',
    stream=sys.stdout,
)
log = logging.getLogger('archive')

CHECK_INTERVAL = 30 * 60   # 30 minutes
ARCHIVE_WEEKDAY = 6        # Sunday (0=Mon … 6=Sun)
ARCHIVE_HOUR = 22          # 22:00 МСК
TZ_OFFSET = 3              # МСК = UTC+3

_last_archive_date = None  # tracks the last date we ran the archive


def _should_archive(now_local: datetime) -> bool:
    global _last_archive_date
    if now_local.weekday() != ARCHIVE_WEEKDAY:
        return False
    if now_local.hour < ARCHIVE_HOUR:
        return False
    today = now_local.date()
    if _last_archive_date == today:
        return False
    return True


def run():
    from factory import create_app
    app = create_app()

    with app.app_context():
        from extensions import db
        from models import Task, TaskStatus

        log.info('Archive daemon started (runs Sundays at %02d:00 МСК)', ARCHIVE_HOUR)

        global _last_archive_date

        while True:
            try:
                now_utc = datetime.utcnow()
                now_local = now_utc + timedelta(hours=TZ_OFFSET)

                if _should_archive(now_local):
                    now_stamp = datetime.utcnow()
                    count = Task.query.filter_by(
                        status=TaskStatus.DONE,
                        is_archived=False,
                    ).update(
                        {'is_archived': True, 'archived_at': now_stamp},
                        synchronize_session=False,
                    )
                    db.session.commit()
                    _last_archive_date = now_local.date()
                    log.info('Weekly archive complete: archived %d tasks', count)

            except Exception as e:
                log.error('Archive error: %s', e)
                try:
                    db.session.rollback()
                except Exception:
                    pass
            finally:
                db.session.remove()

            time.sleep(CHECK_INTERVAL)


if __name__ == '__main__':
    run()
