"""Portable single-worker production entry point. No reload or debug mode."""
import os
import uvicorn
from backend.app.api.deployment import integer_env


def main():
    trusted = os.getenv('AFL_TRUSTED_PROXY_IPS', '').strip()
    if '*' in trusted:
        raise RuntimeError('AFL_TRUSTED_PROXY_IPS must identify trusted ingress addresses, not a wildcard')
    uvicorn.run('backend.app.api.main:app', host='0.0.0.0',
                port=integer_env('PORT', 8000, maximum=65535), workers=1,
                reload=False, proxy_headers=bool(trusted), forwarded_allow_ips=trusted or '127.0.0.1')


if __name__ == '__main__':
    main()
