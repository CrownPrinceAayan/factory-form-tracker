# gunicorn.conf.py
timeout = 180  # 3 minutes
workers = 1    # Only one worker to reduce memory usage
worker_class = 'sync'
