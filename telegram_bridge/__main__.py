"""Entry point: python -m telegram_bridge [--wait-for-token]."""

import argparse
import signal
import sys
import threading
from pathlib import Path

from backend.logging_setup import configure_logging
from backend.settings import get_settings
from telegram_bridge.bridge import TelegramBridge

HEALTH_FILE = Path('/tmp/telegram-bridge-health')


def wait_without_token(stop: threading.Event) -> int:
    """Keep the optional Docker service idle without contacting Telegram or n8n."""
    print('LIVE_CONNECTIVITY_PENDING: TELEGRAM_BOT_TOKEN is not set. '
          'Configure it privately in .env and recreate only the telegram-bridge service.', flush=True)
    while not stop.is_set():
        if HEALTH_FILE.parent.exists():
            HEALTH_FILE.touch()
        stop.wait(30)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Telegram polling bridge to the existing n8n assistant')
    parser.add_argument('--wait-for-token', action='store_true', help='Stay idle when credentials are absent')
    args = parser.parse_args([] if argv is None else argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    if not settings.telegram_bot_token or not settings.telegram_bot_token.strip():
        if args.wait_for_token:
            return wait_without_token(stop)
        print('LIVE_CONNECTIVITY_PENDING: TELEGRAM_BOT_TOKEN is not set; '
              'see docs/TELEGRAM_ACTIVATION.md. Backend and n8n are unaffected.', file=sys.stderr)
        return 2
    bridge = TelegramBridge(settings.telegram_bot_token.strip(), settings.assistant_webhook_url, settings.max_upload_bytes, dialogue_enabled=True)
    bridge.stop = stop
    try:
        bridge.run_forever()
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        # Exception messages may contain token-bearing URLs; print only the type.
        print(f'Telegram bridge stopped: {type(exc).__name__}. '
              'Check configuration and Telegram network access.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
