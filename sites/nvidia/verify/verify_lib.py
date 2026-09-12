#!/usr/bin/env python3
"""NVIDIA repair001: explicit, read-only stdlib grading contract.

No application import, network, model, default database, or subprocess is used.
Exit 0/1 means a valid PASS/FAIL; exit 2 is malformed/unavailable infrastructure.
"""
import argparse
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
from urllib.parse import parse_qs, unquote, urlsplit

SITE = Path(__file__).resolve().parent.parent
TABLES = {
    'users': 'id email password_hash name company country newsletter_opt_in created',
    'products': 'id slug name category series tagline description price_usd image release_year in_stock is_featured architecture cuda_cores tensor_cores rt_cores memory_gb memory_type memory_bandwidth boost_clock_ghz tdp_watts interface recommended_psu_watts',
    'articles': 'id slug title category author published excerpt body image read_minutes',
    'drivers': 'id product_series branch version os released size_mb highlights download_count',
    'newsletter': 'id email topic',
    'reviews': 'id product_id user_id rating title body created',
    'cart_items': 'id user_id product_id quantity',
    'orders': 'id user_id created status total_usd',
    'wishlist_items': 'id user_id product_id',
    'order_items': 'id order_id product_id name price_usd quantity',
}


class InfraError(Exception):
    """Inputs cannot support a task verdict."""


class TaskFailure(Exception):
    """Well-formed evidence does not meet the task."""


def require(condition, reason):
    if not condition:
        raise TaskFailure(reason)


def unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise InfraError('duplicate JSON keys')
    return result


def load_json(path):
    with Path(path).open(encoding='utf-8') as stream:
        return json.load(stream, object_pairs_hook=unique_object,
                         parse_constant=lambda value: (_ for _ in ()).throw(InfraError('nonfinite JSON')))


def snapshot(path):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise InfraError('database must be an explicit regular file')
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as con:
        con.execute('PRAGMA query_only=ON')
        if con.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise InfraError('SQLite integrity_check failed')
        if con.execute('PRAGMA foreign_key_check').fetchall():
            raise InfraError('SQLite foreign_key_check failed')
        names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if names != set(TABLES):
            raise InfraError('unexpected/missing database tables')
        schema = con.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
        con.row_factory = sqlite3.Row
        data = {}
        for name, columns in TABLES.items():
            actual = {r['name'] for r in con.execute(f'PRAGMA table_info("{name}")')}
            if actual != set(columns.split()):
                raise InfraError(f'{name}: unexpected/missing columns')
            rows = [dict(r) for r in con.execute(f'SELECT * FROM "{name}" ORDER BY id')]
            if any(type(r['id']) is not int for r in rows):
                raise InfraError(f'{name}: invalid primary key')
            data[name] = rows
        return data, schema


def canonical_task(number):
    # This remains local to the site even when the entire repository is staged.
    tasks = [json.loads(line, object_pairs_hook=unique_object) for line in
             (SITE / 'tasks.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    ids = [t.get('id') for t in tasks]
    if len(ids) != len(set(ids)):
        raise InfraError('duplicate canonical task IDs')
    matches = [t for t in tasks if t.get('id') == f'NVIDIA--{number}']
    if len(matches) != 1:
        raise InfraError('canonical task missing')
    return matches[0]


def parse_url(value):
    if not isinstance(value, str) or not value:
        raise InfraError('trajectory URL must be a nonempty string')
    try:
        url = urlsplit(value)
        port = url.port
    except ValueError as exc:
        raise InfraError('invalid trajectory URL') from exc
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
        raise InfraError('invalid absolute HTTP trajectory URL')
    return url, (url.scheme, url.hostname, port or (443 if url.scheme == 'https' else 80))


class Context:
    def __init__(self, number, args):
        self.number = number
        self.task = load_json(Path(args.run_dir) / 'task.json')
        if self.task != canonical_task(number):
            raise InfraError('task.json differs from this verifier revision/task')
        self.trajectory = load_json(Path(args.run_dir) / 'trajectory.json')
        t = self.trajectory
        if (not isinstance(t, dict) or t.get('task_id') != self.task['id'] or
                t.get('query') != self.task['ques'] or not isinstance(t.get('steps'), list) or
                not isinstance(t.get('final_answer'), str)):
            raise InfraError('trajectory task/query/steps/final_answer mismatch')
        self.answer = t['final_answer']
        self.pages = []
        self.origins = set()
        for index, step in enumerate(t['steps']):
            if not isinstance(step, dict) or type(step.get('step')) is not int or step['step'] != index:
                raise InfraError('steps must have consecutive integer step indices')
            if step.get('query', self.task['ques']) != self.task['ques']:
                raise InfraError('step query mismatch')
            if not any(k in step for k in ('url', 'url_before', 'url_after')):
                raise InfraError('step lacks a URL')
            for field in ('url_before', 'url', 'url_after'):
                if field in step:
                    self.add_page(step[field])
        self.final = None
        if t.get('final_url') is not None:
            self.final = self.add_page(t['final_url'])
        self.before, schema = snapshot(args.initial_db)
        self.after, after_schema = snapshot(args.after_db)
        if schema != after_schema:
            raise InfraError('before/after schema mismatch')

    def add_page(self, value):
        url, origin = parse_url(value)
        self.origins.add(origin)
        page = (unquote(url.path).rstrip('/') or '/', parse_qs(url.query, keep_blank_values=True))
        self.pages.append(page)
        return page

    def same_site(self):
        # Runtime maps ports, so compare the actual observed origin, not task.web's port.
        return (len(self.origins) <= 1 and
                all(host in ('localhost', '127.0.0.1', '::1') for _, host, _ in self.origins) and
                not self.trajectory.get('boundary_events'))

    def product(self, slug):
        rows = [r for r in self.before['products'] if r['slug'] == slug]
        if len(rows) != 1:
            raise InfraError(f'missing/ambiguous product: {slug}')
        return rows[0]

    def detail(self, slug):
        return any(path == '/products/' + slug for path, _ in self.pages)

    def compare(self, slugs):
        # Match app.py precedence exactly: nonempty getlist('product') wins
        # over the first legacy ids value. Both contain slugs, never DB IDs.
        for path, query in self.pages:
            if path != '/compare':
                continue
            values = query.get('product') or query.get('ids', [''])[0].split(',')
            selected = {value.strip() for value in values if value.strip()}
            if set(slugs) <= selected:
                return True
        return False

    def specs(self, slug):
        return self.detail(slug) or self.compare([slug])

    def buying(self, slug=None):
        for path, _ in self.pages:
            if path == '/where-to-buy' or (slug and path == '/where-to-buy/' + slug):
                return True
        return False

    def listing(self, category=None, series=None):
        for path, q in self.pages:
            if path == '/products':
                if q.get('q', [''])[0].strip():
                    continue  # A narrowed search is not evidence of an entire candidate set.
                if q.get('category', [''])[0] not in ('', category):
                    continue
                if q.get('series', [''])[0] not in ('', series):
                    continue
                return True
            if series and path == '/geforce/graphics-cards/' + series.split()[1] + '-series':
                return True
        return False


def row_counter(rows, ignore=()):
    return Counter(tuple((k, row[k]) for k in sorted(row) if k not in ignore) for row in rows)


def preserved(ctx, except_table=None):
    for table in TABLES:
        if table == except_table:
            continue
        if table == 'drivers':
            # A read task may harmlessly press the simulated Download button.
            require(row_counter(ctx.before[table], ('download_count',)) ==
                    row_counter(ctx.after[table], ('download_count',)), 'driver records changed')
            old = {r['id']: r['download_count'] for r in ctx.before[table]}
            require(all(type(r['download_count']) is int and r['download_count'] >= (old[r['id']] or 0)
                        for r in ctx.after[table]), 'driver download counter regressed')
        else:
            require(row_counter(ctx.before[table]) == row_counter(ctx.after[table]),
                    f'unrequested {table} mutation')


def delta(ctx, table):
    old = {r['id']: r for r in ctx.before[table]}
    new = {r['id']: r for r in ctx.after[table]}
    added = [new[i] for i in new.keys() - old.keys()]
    removed = [old[i] for i in old.keys() - new.keys()]
    modified = [i for i in old.keys() & new.keys() if old[i] != new[i]]
    return added, removed, modified


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InfraError(message)


def run(number):
    task_id = f'NVIDIA--{number}'
    code = 2
    try:
        parser = Parser(description=__doc__)
        for name in ('run_dir', 'initial_db', 'after_db'):
            parser.add_argument('--' + name, required=True)
        args = parser.parse_args()
        ctx = Context(number, args)
        require(ctx.same_site(), 'off-origin navigation or browser boundary violation')
        from predicates import grade
        evidence = grade(ctx)
        result = {'task_id': task_id, 'pass': True, 'reason': 'Required facts/state verified', 'evidence': evidence}
        code = 0
    except TaskFailure as exc:
        result = {'task_id': task_id, 'pass': False, 'reason': str(exc), 'evidence': []}
        code = 1
    except Exception as exc:
        # Input errors and unexpected verifier faults are infrastructure, never
        # a normal task FAIL. Keep stdout a single parseable JSON object.
        result = {'task_id': task_id, 'pass': False, 'reason': f'INFRA_ERROR: {exc}', 'evidence': [], 'error': 'INFRA_ERROR'}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return code
