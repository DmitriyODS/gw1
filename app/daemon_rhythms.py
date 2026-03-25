"""
daemon_rhythms.py — background daemon that fires rhythms at their scheduled time.

Runs as a separate process inside the Docker container.
Checks every 60 seconds whether any active rhythm is due, creates tasks for those that are.
"""

import time
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [rhythms] %(levelname)s %(message)s',
    stream=sys.stdout,
)
log = logging.getLogger('rhythms')

CHECK_INTERVAL = 60  # seconds


def run():
    from factory import create_app
    app = create_app()

    with app.app_context():
        from extensions import db
        from models import Rhythm
        from blueprints.rhythms import _create_task_from_rhythm

        log.info('Rhythm daemon started (interval=%ds)', CHECK_INTERVAL)

        while True:
            try:
                # expire_all ensures we read fresh data from DB each cycle
                db.session.expire_all()
                rhythms = Rhythm.query.filter_by(is_active=True).all()
                log.debug('Checking %d active rhythm(s)', len(rhythms))
                fired = 0
                for r in rhythms:
                    log.debug('Rhythm %d "%s": is_due=%s trigger_time=%s last_run_at=%s',
                              r.id, r.name, r.is_due, r.trigger_time, r.last_run_at)
                    if r.is_due:
                        try:
                            task = _create_task_from_rhythm(r)
                            db.session.commit()
                            log.info('Fired rhythm %d "%s" → task %d "%s"',
                                     r.id, r.name, task.id, task.title)
                            fired += 1
                        except Exception as e:
                            db.session.rollback()
                            log.error('Error firing rhythm %d: %s', r.id, e)
                if fired:
                    log.info('Fired %d rhythm(s) this cycle', fired)
            except Exception as e:
                log.error('Cycle error: %s', e)
                try:
                    db.session.rollback()
                except Exception:
                    pass
            finally:
                db.session.remove()

            time.sleep(CHECK_INTERVAL)


if __name__ == '__main__':
    run()
