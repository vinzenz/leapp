import contextlib
import logging
import os
import pkgutil
import sys
from io import UnsupportedOperation
from multiprocessing import Process, Queue

import leapp.libraries.actor
from leapp.actors import get_actors, get_actor_metadata
from leapp.exceptions import ActorInspectionFailedError, MultipleActorsError, UnsupportedDefinitionKindError, \
    LeappRuntimeError
from leapp.repository import DefinitionKind
from leapp.repository.loader import library_loader


def inspect_actor(definition, result_queue):
    """
    Retrieves the actor information in a child process and returns the results back through `result_queue`.

    :param definition: the actor definition to load
    :type definition: :py:class:`ActorDefinition`
    :param result_queue: queue to pass results back to the calling process
    :type result_queue: :py:class:`multiprocessing.Queue`
    """
    definition.load()
    result = [get_actor_metadata(actor) for actor in get_actors()]
    result = [entry for entry in result if entry['path'] in definition.full_path]
    result_queue.put(result)


class ActorCallContext(object):
    """
    Wraps the actor execution into child process.
    """
    def __init__(self, definition, logger, messaging, config_model):
        """
        :param definition: Actor definition
        :type definition: :py:class:`leapp.repository.actor_definition.ActorDefinition`
        :param logger: Logger
        :type logger: :py:class:`logging.Logger`
        :param messaging: Leapp Messaging
        :type messaging: :py:class:`leapp.messaging.BaseMessaging`
        :param config_model: Workflow provided configuration model
        :type config_model: :py:class:`leapp.models.Model` derived class
        """
        self.definition = definition
        self.logger = logger
        self.messaging = messaging
        self.config_model = config_model

    @staticmethod
    def _do_run(stdin, logger, messaging, definition, config_model, args, kwargs):
        if stdin is not None:
            try:
                sys.stdin = os.fdopen(stdin)
            except OSError:
                pass
        definition.load()
        with definition.injected_context():
            target_actor = [actor for actor in get_actors() if actor.name == definition.name][0]
            target_actor(logger=logger, messaging=messaging, config_model=config_model).run(*args, **kwargs)

    def run(self, *args, **kwargs):
        """
        Performs the actor execution in the child process.
        """
        try:
            stdin = sys.stdin.fileno()
        except UnsupportedOperation:
            stdin = None
        p = Process(target=self._do_run,
                    args=(stdin, self.logger, self.messaging, self.definition, self.config_model, args, kwargs))
        p.start()
        p.join()
        if p.exitcode != 0:
            raise LeappRuntimeError(
                'Actor {actorname} unexpectedly terminated with exit code: {exitcode}'
                .format(actorname=self.definition.name, exitcode=p.exitcode))


class ActorDefinition(object):
    """
    Defines actor resources.

    """
    def __init__(self, directory, repo_dir, log=None):
        """
        :param log: Logger
        :type log: :py:class:`logging.Logger`
        :param directory: Actor directory
        :type directory: str
        :param repo_dir: Repository directory
        :type repo_dir: str
        """
        self.log = log or logging.getLogger('leapp.actor')
        self._directory = directory
        self._repo_dir = repo_dir
        self._definitions = {}
        self._module = None
        self._discovery = None

    @property
    def full_path(self):
        return os.path.realpath(os.path.join(self._repo_dir, self._directory))

    def add(self, kind, path):
        """
        Adds any kind of actor resource to the Definition

        :param kind: kind of resource added
        :type kind: str
        :param path: path to the added resource
        :type path: str
        """
        if kind not in DefinitionKind.ACTOR_WHITELIST:
            self.log.error("Attempt to add item type %s to actor that is not supported", kind.name)
            raise UnsupportedDefinitionKindError('Actors do not support {kind}.'.format(kind=kind.name))
        self._definitions.setdefault(kind, []).append(path)

    def dump(self):
        """
        :return: dump of actor resources (path, name, tools, files, libraries, tests)
        """
        return {
            'path': self.directory,
            'name': self.name,
            'tools': self.tools,
            'files': self.files,
            'libraries': self.libraries,
            'tests': self.tests
        }

    def load(self):
        """
        Loads the actor module to be introspectable.
        """
        if not self._module:
            with self.injected_context():
                path = os.path.abspath(os.path.join(self._repo_dir, self.directory))
                for importer, name, is_pkg in pkgutil.iter_modules((path,)):
                    if not is_pkg:
                        self._module = importer.find_module(name).load_module(name)
                        break

    def discover(self):
        """
        Performs introspection through a subprocess.

        :return: Dictionary with discovered items.
        """
        if not self._discovery:
            self.log.debug("Starting actor discovery in %s", self.directory)
            q = Queue(1)
            p = Process(target=inspect_actor, args=(self, q))
            p.start()
            p.join()
            if p.exitcode != 0:
                self.log.error("Process inspecting actor in %s failed with %d", self.directory, p.exitcode)
                raise ActorInspectionFailedError('Inspection of actor in {path} failed'.format(path=self.directory))
            result = q.get()
            if not result:
                self.log.error("Process inspecting actor in %s returned no result", self.directory)
                raise ActorInspectionFailedError(
                    'Inspection of actor in {path} produced no results'.format(path=self.directory))
            if len(result) > 1:
                self.log.error("Actor in %s returned multiple actors", self.directory)
                raise MultipleActorsError(self.directory)
            self._discovery = result[0]
            for tag in self._discovery['tags']:
                if self not in tag.actors:
                    tag.actors += (self,)
        return self._discovery

    def __call__(self, messaging=None, logger=None, config_model=None):
        return ActorCallContext(definition=self, messaging=messaging, logger=logger, config_model=config_model)

    @property
    def dialogs(self):
        """
        :return: Tuple of defined dialogs
        """
        return self.discover()['dialogs']

    @property
    def consumes(self):
        """
        :return: Tuple of consumed models
        """
        return self.discover()['consumes']

    @property
    def produces(self):
        """
        :return: Tuple of produced models
        """
        return self.discover()['produces']

    @property
    def tags(self):
        """
        :return: Tuple of tags assigned to the actor
        """
        return self.discover()['tags']

    @property
    def class_name(self):
        """
        :return: Actor class name
        """
        return self.discover()['class_name']

    @property
    def name(self):
        """
        :return: Actor internal name
        """
        return self.discover()['name']

    @property
    def description(self):
        """
        :return: Actor description
        """
        return self.discover()['description']

    @contextlib.contextmanager
    def injected_context(self):
        """
        Prepares the actor environment for running the actor.
        This includes injecting actor private libraries into :py:mod:`leapp.libraries.actor`
        and setting environment variables for private tools and files.

        :note: Use with caution.
        """
        # Backup of the path variable
        path_backup = os.environ.get('PATH', '')
        os.environ['PATH'] = ':'.join(path_backup.split(':') + list(
            os.path.join(self._repo_dir, self._directory, path) for path in self.tools))

        files_backup = os.environ.get('LEAPP_FILES', None)
        if self.files:
            os.environ['LEAPP_FILES'] = os.path.join(self._repo_dir, self._directory, self.files[0])

        tools_backup = os.environ.get('LEAPP_TOOLS', None)
        if self.tools:
            os.environ['LEAPP_TOOLS'] = os.path.join(self._repo_dir, self._directory, self.tools[0])

        # We make a snapshot of the symbols in the module
        before = leapp.libraries.actor.__dict__.keys()
        # Now we are loading all modules and packages and injecting them at the same time into the modules at hand
        to_add = library_loader(leapp.libraries.actor, 'leapp.libraries.actor',
                                map(lambda x: os.path.join(self._repo_dir, self.directory, x), self.libraries))
        backup = {}

        # Now we are injecting them into the global sys.modules dictionary and keep a backup of existing ones
        # The backup shouldn't be necessary, but just in case
        for name, mod in to_add:
            if name in sys.modules:
                backup[name] = sys.modules[name]
            sys.modules[name] = mod

        previous_path = os.getcwd()
        os.chdir(os.path.join(self._repo_dir, self._directory))
        try:
            yield
        finally:
            os.chdir(previous_path)

            # Restoration of the PATH environment variable
            os.environ['PATH'] = path_backup
            # Restoration of the LEAPP_FILES environment variable
            if files_backup is not None:
                os.environ['LEAPP_FILES'] = files_backup
            else:
                os.environ.pop('LEAPP_FILES', None)

            if tools_backup is not None:
                os.environ['LEAPP_TOOLS'] = tools_backup
            else:
                os.environ.pop('LEAPP_TOOLS', None)

            # Remove all symbols in the actor lib before the execution
            current = leapp.libraries.actor.__dict__.keys()
            added = set(current).difference(before)
            for symbol in added:
                leapp.libraries.actor.__dict__.pop(symbol)

            # Remove all modules from the sys.modules dict or restore from backup if it was there
            for name, unused in to_add:
                if name in backup:
                    sys.modules[name] = backup[name]
                else:
                    sys.modules.pop(name)

    @property
    def directory(self):
        """
        :return: The folder path of the actor
        """
        return self._directory

    @property
    def tools(self):
        """
        :return: Tuple with path to the tools folder of the actor, empty tuple if none
        """
        return tuple(self._definitions.get(DefinitionKind.TOOLS, ()))

    @property
    def libraries(self):
        """
        :return: Tuple with path to the libraries folder of the actor, empty tuple if none
        """
        return tuple(self._definitions.get(DefinitionKind.LIBRARIES, ()))

    @property
    def files(self):
        """
        :return: Tuple with path to the files folder of the actor, empty tuple if none
        """
        return tuple(self._definitions.get(DefinitionKind.FILES, ()))

    @property
    def tests(self):
        """
        :return: Tuple with path to the tests folder of the actor, empty tuple if none
        """
        return tuple(self._definitions.get(DefinitionKind.TESTS, ()))
