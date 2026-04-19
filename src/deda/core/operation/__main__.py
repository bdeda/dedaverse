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

Starts the loop + HTTP server with defaults from ``_config`` and blocks
until Ctrl-C.
"""

import argparse
import logging
import signal
import sys
import threading

from . import _config
from ._server import start_server


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog='deda.core.operation')
    parser.add_argument('--host', default=_config.HOST)
    parser.add_argument('--port', type=int, default=_config.PORT)
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )

    op = start_server(host=args.host, port=args.port)

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
