import json
import os
from multiprocessing import Process, Queue

from flask import Flask, abort, jsonify

from leapp.repository.scan import find_and_scan_repositories
from leapp.utils.audit import dict_factory, get_connection
from leapp.utils.repository import find_repository_basedir


app = Flask('leapp.snactor.commands.dashboard.backend',
            static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../../dashboard/build')),
            static_url_path='')


@app.route('/')
def root():
    return app.send_static_file('index.html')


def memoize(f):
    results = {}

    def helper(n):
        if n not in results:
            results[n] = f(n)
        return results[n]
    return helper


@memoize
def _discover(n):
    base_dir = find_repository_basedir(os.getcwd())
    repository = find_and_scan_repositories(base_dir, include_locals=True)

    try:
        repository.load()
    except StandardError:
        return None

    data = repository.serialize()
    if not isinstance(data, (list, tuple)):
        data = [data]

    return data


@app.route('/api/discover')
def discover():
    return jsonify(_discover(0))


@app.route('/api/messages')
def messages():
    with get_connection(None) as con:
        cursor = con.execute('''
        SELECT
             id, context, stamp, topic, type, actor, phase, message_hash, message_data, hostname
        FROM
             messages_data
        WHERE context = ?''', (os.environ["LEAPP_EXECUTION_ID"],))
        cursor.row_factory = dict_factory
        result = cursor.fetchall()
        for msg in result:
            msg['message_data'] = json.loads(msg['message_data'])
        return jsonify(result)
