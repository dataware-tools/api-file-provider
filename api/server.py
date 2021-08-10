#!/usr/bin/env python
# Copyright API authors
"""The API server."""

from datetime import datetime
import hashlib
import os
import threading
import time
import uvicorn

from utils import save_jwt_key


def regenerate_jwt_key(postfix: str = ''):
    """Re-generate JWT key.

    Args:
        postfix (str): String to append to the key.

    """
    key = os.environ.get('SECRET_KEY', 'api-file-provider') + postfix
    jwt_key = hashlib.sha256(
        key.encode('utf-8') if isinstance(key, str) else key
    ).hexdigest()
    save_jwt_key(jwt_key)
    print('JWT key has been regenerated')


def _key_update_daemon():
    t = threading.currentThread()
    prev_postfix = ''
    while not getattr(t, "kill", False):
        postfix = str(datetime.now().strftime('%Y-%m-%d'))
        if postfix != prev_postfix:
            regenerate_jwt_key(postfix)
            prev_postfix = postfix
        time.sleep(1)


if __name__ == '__main__':
    debug = os.environ.get('API_DEBUG', '') in ['true', 'True', 'TRUE', '1']
    print('Debug: {}'.format(debug))
    daemon = threading.Thread(target=_key_update_daemon)
    daemon.start()

    num_available_cores = len(os.sched_getaffinity(0))
    uvicorn.run(
        "main:api",
        host='0.0.0.0',
        port=8080,
        workers=int(os.environ.get('NUM_WORKERS', num_available_cores * 2))
    )
