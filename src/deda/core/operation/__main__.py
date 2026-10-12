# ###################################################################################
#
# Copyright 2025 Ben Deda
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ###################################################################################
"""Module entry point: ``py -3.13 -m deda.core.operation``.

Starts the loop + HTTP server using :mod:`_config` values (which are
sourced from :data:`os.environ` and the optional ``.env`` file) and
blocks until Ctrl-C.
"""

import argparse
import logging
import signal
import sys
import threading
from pathlib import Path

from . import _config
from ._server import start_server


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog='deda.core.operation')
    parser.add_argument(
        '--env-file',
        type=Path,
        default=None,
        help='Path to a .env file. Overrides OPERATION_ENV_FILE / the default '
        '~/.dedaverse/operation/.env. Values in this file take precedence '
        'over existing environment variables.',
    )
    parser.add_argument('--host', default=None)
    parser.add_argument('--port', type=int, default=None)
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.env_file is not None:
        _config.load_env(env_file=args.env_file, override=True)
        _config.reload_config()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )

    host = args.host if args.host is not None else _config.HOST
    port = args.port if args.port is not None else _config.PORT

    op = start_server(host=host, port=port)

    stop_event = threading.Event()

    def _handle_signal(signum: int, _frame: object) -> None:
        logging.getLogger(__name__).info('operation: received signal %d, shutting down', signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    # SIGTERM is POSIX; on Windows this is a no-op but harmless.
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, _handle_signal)

    try:
        stop_event.wait()
    finally:
        op.stop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
