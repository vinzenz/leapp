from __future__ import print_function

import os
import platform
from subprocess import call

from leapp.logger import configure_logger
from leapp.snactor.commands.dashboard.backend import app
from leapp.snactor.context import with_snactor_context
from leapp.utils.clicmd import command, command_opt
from leapp.utils.repository import requires_repository

_BROWSER_OPEN_COMMAND = {
    'windows': 'start',
    'linux': 'xdg-open',
    'darwin': 'open'
}


def launch_browser(url):
    command = _BROWSER_OPEN_COMMAND.get(platform.system().lower())
    if not command:
        print('Could not automatically determine how to open your browser.\n'
              'Please open {URL} in the browser of your choice.'.format(URL=url))
    else:
        print("Opening {URL}: {cmd}".format(URL=url, cmd=[command, url]))
        call("{} {}".format(command, url), shell=True)


@command('dashboard', help='Starts a internal')
@command_opt('port', value_type=int, help='Allows to specify another port than the default port 3000')
@requires_repository
@with_snactor_context
def dashboard(args):
    configure_logger()
    launch_browser('http://localhost:3000')
    app.run(host='localhost', port=args.port or 3000, debug=os.getenv('LEAPP_DASHBOARD_DEBUG', '0') == '1')
