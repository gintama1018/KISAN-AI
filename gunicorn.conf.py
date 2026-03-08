# gunicorn.conf.py — production settings for Render
import os

# 2 workers × 2 threads = handles 4 concurrent requests on free 512MB tier
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
timeout = 120          # Gemini + ElevenLabs can take up to 30s each
keepalive = 5
worker_class = "sync"  # sync is reliable; no need for gevent on free tier

# Logging
accesslog = "-"        # stdout → visible in Render logs
errorlog  = "-"
loglevel  = "info"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sμs'
