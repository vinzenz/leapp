#
# def resolve(services):
#     lookup = {_fq(s): s.leapp_meta() for s in services}
#     for s in services:
#         m = lookup[_fq(s)]
#         for link in  m.get('address_links', []):
#             tgtm = lookup[link['target']]
#             tgtm['fixup'] = tgtm.get('fixup', []) + [(s, link)]
#             tgtm['require-links'] = tgtm.get('require-links', []) + [{'target': _fq(s)}]
#
#
# def dependency_ordered(services):
#     result = []
#     result_fq = []
#     for s in services:
#         if not s.leapp_meta().get('require-links', []):
#             result.append(s)
#             result_fq.append(_fq(s))
#
#     services = [s for s in services if s not in result]
#     count = len(services)
#     while services and count > 0:
#         count -= 1
#         for s in services:
#             if all([link['target'] in result_fq for link in s.leapp_meta().get('require-links', [])]):
#                 result.append(s)
#                 result_fq.append(_fq(s))
#         services = [s for s in services if s not in result]
#     result += services
#     return result
#
import os
import subprocess
import yaml

def load(path='/usr/share/leapp/repository'):
    repos = {}
    for root, _, files in os.walk(path):
        for name in files:
            with open(os.path.join(root, name), 'r') as f:
                ns, ext = os.path.splitext(name)
                if ext == '.yml':
                    for k, v in yaml.load(f.read()).items():
                        repos[k] = v
    return repos

def filter_by_services(repository, services):
    return {k: v for k, v in repository.items() if all([s in services for s in v['services']])}

class MissingDependencyError(Exception):
    def __init__(self, missing):
        super(MissingDependencyError, self).__init__(
            "Depedencies are missing: {}".format(', '.join(missing)))

def process_dependencies(filtered):
    for k, v in filtered.items():
        deps = [r['target'] for r in v.get('require-links', [])]
        deps += [r['target'] for r in v.get('force-host-networking-to', [])]
        deps = set(deps)
        if not all([s['target'] in filtered for s in deps):
            raise MissingDependencyError([s for s in deps if s filtered])


_ACTION_REGISTRY = {}

def action(name):
    def outer(f):
        _ACTION_REGISTRY[name] = f
        return f
    return outer


class Registry(object):
    def __init__(self):
        self._containers = {}

    def get(self, name):
        return self._containers[name]

    def add(self, name, value):
        self._containers[name] = Container(self, name, value)

    def register_alias(self, name, alias):
        self._aliases[alias] = name


class Container(object):
    def __init__(self, registry, name, config):
        self._config = config
        self._name = name
        for name, alias in self._aliases():
            registry.register_alias(name, alias)
        self._registry = registry

    def fixup_actions(self):
        for action in self._config.get('actions', {}).get('fixup', ()):
            handler = _ACTION_REGISTRY.get(action.get('action'))
            yield handler(self._registry, action)

    def _aliases(self):
        for link in self._config.get('require-links', []):
            if 'alias' in link:
                yield (link['target'], link['alias'])
        for link in self._config.get('force-host-networking-to', []):
            if 'alias' in link:
                yield (link['target'], link['alias'])

    def __index__(self, name):
        return self._config[name]


def resolve_ref(registry, item):
    if item.startswith('@'):
        return registry.get(item)['name']
    return item


@action('text-replace')
def action_text_replace(registry, action):
    what_value = resolve_ref(registry, action['what'])
    where_value = resolve_ref(registry, action['where'])
    with_value = resolve_ref(registry, action['with'])
    cmd = ['/bin/sed', '-i',
           's/{}/{}/g'.format(what_value, with_value),
           where_value]
    return ' '.join(cmd)


