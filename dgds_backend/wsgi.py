from datetime import datetime
from dgds_backend.app import app
from dgds_backend.app import scheduler
scheduler.get_job('cache_refresh').modify(next_run_time=datetime.now())
