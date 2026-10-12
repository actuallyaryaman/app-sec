"""Controlled runner for the inspected assignment files; no automatic network runs."""
import argparse
import code
import datetime as dt
import difflib
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import signal
import sys
import traceback
from urllib.parse import parse_qsl, urlsplit, urlunsplit
import uuid

import requests

ORIGINALS = Path('/originals')
WORK = Path('/work')
FILES = {'original': 'infinite-money-logic-flaw.py',
         'updated': 'infinite-money-logic-flaw__updated.py'}
PROXY_LINE = 'proxies = {"http": "http://127.0.0.1:8080", "https": "http://127.0.0.1:8080"}'
POLICY = 'transport-only copy: proxies={}, verify=True; exact-host Requests guard; output redaction'


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='milliseconds')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source(variant):
    path = ORIGINALS / FILES[variant]
    data = path.read_bytes()
    expected = dict(line.split()[::-1] for line in
                    Path('/opt/lab/sources.sha256').read_text().splitlines())
    if sha(data) != expected[path.name]:
        raise ValueError('Assignment source checksum changed; inspect changes before updating baseline.')
    return data.decode('utf-8')


def safe_copy(text):
    if text.count(PROXY_LINE) != 1 or text.count('verify=False') != 8:
        raise ValueError('Unexpected transport settings; refuse unreviewed source.')
    return text.replace(PROXY_LINE, 'proxies = {}').replace('verify=False', 'verify=True')


def validate_url(value, host=None, base=False):
    if not value or not value.isascii() or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError('URL must be an ASCII HTTPS lab URL without whitespace.')
    if '\\' in value:
        raise ValueError('Backslashes are not allowed in URLs.')
    p = urlsplit(value)
    name = p.hostname or ''
    if p.scheme != 'https' or p.username is not None or p.password is not None:
        raise ValueError('HTTPS only; URL credentials are not permitted.')
    if p.port not in (None, 443):
        raise ValueError('Only the default HTTPS port is permitted.')
    labels = name.split('.')
    if (len(labels) < 3 or labels[-2:] != ['web-security-academy', 'net']
            or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
                   for label in labels)):
        raise ValueError('Hostname must be a proper subdomain of web-security-academy.net.')
    if host is not None and name != host:
        raise ValueError('Request or redirect leaves the explicitly selected lab host.')
    if base and (p.path not in ('', '/') or p.query or p.fragment):
        raise ValueError('Supply the lab origin, without a path, query, or fragment.')
    return urlunsplit(('https', name, '/' if base else p.path or '/', p.query, ''))


def versions():
    packages = ('requests', 'urllib3', 'certifi', 'charset-normalizer', 'idna')
    return {'python': sys.version, 'packages': {p: importlib.metadata.version(p) for p in packages},
            'diff': shutil.which('diff')}


class Output:
    """Line-buffer stdout/stderr, including CR progress, to redact fragmented writes."""
    def __init__(self, terminal, stream, log=None):
        self.terminal, self.stream, self.log = terminal, stream, log
        self.pending = ''
        self.encoding = 'utf-8'

    def emit(self, text):
        # Exact updated-script output format. Never print redeemable gift-card codes.
        text = re.sub(r'(\bi:\s*\d+\s+code:\s*).*', r'\1[REDACTED]', text)
        # Defense in depth for accidental credential/cookie/token fields in messages.
        text = re.sub(r'(?i)\b(session|csrf|password|username|gift-card|authorization|cookie)'
                      r'(\s*[:=]\s*)[^\s,;]+', r'\1\2[REDACTED]', text)
        line = f'{now()} [{self.stream}] {text}\n'
        self.terminal.write(line)
        self.terminal.flush()
        if self.log:
            self.log.write(line)
            self.log.flush()

    def write(self, text):
        self.pending += text
        parts = re.split(r'[\r\n]', self.pending)
        self.pending = parts.pop()
        for part in parts:
            if part:
                self.emit(part)
        return len(text)

    def flush(self):
        self.terminal.flush()

    def finish(self):
        if self.pending:
            self.emit(self.pending)
            self.pending = ''

    def isatty(self):
        return False


class Guard:
    """Guard HTTPAdapter.send, including each redirect, before network transmission."""
    def __init__(self, host, events=None):
        self.host, self.events = host, events
        self.count = 0
        self.gift_cards = {}
        self.original = requests.adapters.HTTPAdapter.send

    def send(self, adapter, request, **kwargs):
        validate_url(request.url, host=self.host)
        kwargs['verify'] = True
        kwargs['proxies'] = {}
        # No added timeouts, loops, retries, concurrency, or response rewriting.
        self.count += 1
        number = self.count
        started = now()
        # Do not log bodies, query values, cookies, headers, response text, or gift cards.
        path = urlsplit(request.url).path
        known_paths = {'/login', '/cart', '/cart/coupon', '/cart/checkout',
                       '/cart/order-confirmation', '/gift-card', '/my-account', '/'}
        event = {'number': number, 'started': started, 'method': request.method,
                 'path': path if path in known_paths else '[other-path-redacted]'}
        if request.method == 'POST' and path == '/gift-card':
            body = request.body.decode('utf-8') if isinstance(request.body, bytes) else request.body
            fields = dict(parse_qsl(body or '', keep_blank_values=True))
            card = fields.get('gift-card')
            if card is not None:
                event['gift_card_seen_before'] = card in self.gift_cards
                event['gift_card_reference'] = self.gift_cards.setdefault(card, len(self.gift_cards) + 1)
        try:
            response = self.original(adapter, request, **kwargs)
            event['status'] = response.status_code
            return response
        except Exception as error:
            event['error_type'] = type(error).__name__
            raise
        finally:
            event['finished'] = now()
            if self.events:
                self.events.write(json.dumps(event) + '\n')
                self.events.flush()

    def install(self):
        guard = self
        def send(adapter, request, **kwargs):
            return guard.send(adapter, request, **kwargs)
        requests.adapters.HTTPAdapter.send = send

    def restore(self):
        requests.adapters.HTTPAdapter.send = self.original


def run(variant, url, logging):
    original = source(variant)
    normalized = validate_url(url, base=True)
    prepared = safe_copy(original)
    os.umask(0o077)
    run_id = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + variant + '-' + uuid.uuid4().hex[:8]
    directory = WORK / 'runs' / run_id
    directory.mkdir(parents=True)
    script = directory / FILES[variant]
    script.write_text(prepared)
    script.chmod(0o444)
    (directory / 'safety.diff').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), prepared.splitlines(True),
        fromfile='assignment/' + FILES[variant], tofile='transport-safe/' + FILES[variant])))
    metadata = {'run_id': run_id, 'started': now(), 'variant': variant, 'source': FILES[variant],
                'source_sha256': sha(original.encode()), 'copy_sha256': sha(prepared.encode()),
                'runner_sha256': sha(Path(__file__).read_bytes()), 'environment': versions(),
                'command': ['lab', variant, normalized] + (['--log'] if logging else []),
                'policy': POLICY, 'solved': 'Not assessed; check lab interface manually.'}
    (directory / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    log = (directory / 'terminal.log').open('w') if logging else None
    events = (directory / 'http.jsonl').open('w') if logging else None
    stdout, stderr, old_argv, old_cwd = sys.stdout, sys.stderr, sys.argv, Path.cwd()
    out, err = Output(stdout, 'stdout', log), Output(stderr, 'stderr', log)
    guard = Guard(urlsplit(normalized).hostname, events)
    result = 0
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    previous = {s: signal.signal(s, interrupted) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        sys.stdout, sys.stderr = out, err
        print(f'Run {run_id}; source={FILES[variant]}; SHA256={metadata["source_sha256"]}')
        print(f'Executing separate transport-safe copy. {POLICY}')
        print(f'Target={normalized}; original 500 iterations; Ctrl+C interrupts.')
        os.chdir(directory)
        sys.argv = [str(script), normalized]
        guard.install()
        runpy.run_path(str(script), run_name='__main__')
    except KeyboardInterrupt:
        result = 130
        print('Interrupted; completed purchases are not rolled back.', file=sys.stderr)
    except SystemExit as error:
        if error.code is None:
            result = 0
        elif isinstance(error.code, int):
            result = error.code
        else:
            result = 1
            print(str(error.code), file=sys.stderr)
    except Exception as error:
        result = 1
        # Stack frames without locals, response content, source text, or exception messages.
        # Messages can contain secrets or untrusted server data; raw HTML stays in volume.
        print(f'Execution failed: {type(error).__name__} (message omitted for redaction)', file=sys.stderr)
        for frame in traceback.extract_tb(error.__traceback__):
            print(f'  {frame.filename}:{frame.lineno} in {frame.name}', file=sys.stderr)
    finally:
        guard.restore()
        out.finish()
        err.finish()
        sys.stdout, sys.stderr, sys.argv = stdout, stderr, old_argv
        os.chdir(old_cwd)
        for s, handler in previous.items():
            signal.signal(s, handler)
        metadata.update(finished=now(), exit_code=result, request_attempts=guard.count)
        (directory / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
        if log:
            log.close()
        if events:
            events.close()
    print(f'Run {run_id}: exit={result}, HTTP attempts={guard.count}; evidence={directory}')
    print('Exit status is not lab success. Verify account credit and lab status in your browser.')
    return result


def export_logs(run_id):
    if not re.fullmatch(r'\d{8}T\d{6}Z-(original|updated)-[0-9a-f]{8}', run_id):
        raise ValueError('Supply the exact run ID from runs output.')
    directory = WORK / 'runs' / run_id
    metadata = json.loads((directory / 'metadata.json').read_text())
    # Export only wrapper-produced, redacted evidence; never source HTML or diff output.
    for name in ('metadata.json', 'terminal.log', 'http.jsonl', 'safety.diff'):
        path = directory / name
        if path.exists():
            destination = Path('/export') / (run_id + '-' + name)
            destination.write_bytes(path.read_bytes())
            destination.chmod(0o600)
    print(f'Exported {run_id}; exit={metadata.get("exit_code", "incomplete")}. Raw HTML excluded.')


def parser():
    p = argparse.ArgumentParser(description='SE6002 Part 2: deliberate, guarded lab runs only.')
    commands = p.add_subparsers(dest='command')
    commands.add_parser('help', help='Show commands; no requests')
    commands.add_parser('versions', help='Python/dependency versions')
    commands.add_parser('check', help='Verify source hashes, syntax, imports, and diff command')
    commands.add_parser('diff', help='Compare untouched assignment originals')
    commands.add_parser('python', help='Interactive Python console; do not run attacks here')
    commands.add_parser('shell', help='Interactive shell for private evidence inspection')
    commands.add_parser('runs', help='List actual execution metadata')
    commands.add_parser('selftest', help='Offline safeguard and CLI tests; no remote requests')
    commands.add_parser('clean-temporary-files', help='Delete only per-run HTML/diff working files')
    for variant in FILES:
        sub = commands.add_parser(variant, help='Run separate transport-safe copy against explicit lab URL')
        sub.add_argument('url')
        sub.add_argument('--log', action='store_true', help='Save timestamped redacted output and HTTP statuses')
    sub = commands.add_parser('validate-url', help='Validate/normalize without any network request')
    sub.add_argument('url')
    sub = commands.add_parser('safety-diff', help='Show transport-only copy changes without executing')
    sub.add_argument('variant', choices=FILES)
    sub = commands.add_parser('export', help='Export redacted logs/provenance, preserving raw HTML in volume')
    sub.add_argument('run_id')
    return p


def main():
    p = parser()
    args = p.parse_args()
    command = args.command
    if command in (None, 'help'):
        p.print_help()
    elif command in FILES:
        return run(command, args.url, args.log)
    elif command == 'versions':
        print(json.dumps(versions(), indent=2))
    elif command == 'check':
        for variant in FILES:
            text = source(variant)
            compile(text, FILES[variant], 'exec')
            compile(safe_copy(text), 'transport-safe/' + FILES[variant], 'exec')
            print(f'{FILES[variant]}: SHA256={sha(text.encode())}; syntax OK')
        from requests.packages.urllib3.exceptions import InsecureRequestWarning
        assert InsecureRequestWarning and shutil.which('diff'), 'diff command missing'
        print(json.dumps(versions(), indent=2))
    elif command in ('diff', 'safety-diff'):
        if command == 'diff':
            a, b = source('original'), source('updated')
            names = (FILES['original'], FILES['updated'])
        else:
            a = source(args.variant)
            b = safe_copy(a)
            names = (FILES[args.variant], 'transport-safe/' + FILES[args.variant])
        print(''.join(difflib.unified_diff(a.splitlines(True), b.splitlines(True),
                                         fromfile=names[0], tofile=names[1])), end='')
    elif command == 'validate-url':
        print(validate_url(args.url, base=True))
    elif command == 'python':
        code.interact(banner='Container Python; no automatic requests. Use guarded run commands for attacks.')
    elif command == 'shell':
        os.execv('/bin/sh', ['/bin/sh'])
    elif command == 'selftest':
        import selftest
        return selftest.main()
    elif command == 'runs':
        for path in sorted((WORK / 'runs').glob('*/metadata.json')):
            data = json.loads(path.read_text())
            print(f'{data["run_id"]}: exit={data.get("exit_code", "incomplete")}; '
                  f'attempts={data.get("request_attempts", "unknown")}; started={data["started"]}')
    elif command == 'export':
        export_logs(args.run_id)
    elif command == 'clean-temporary-files':
        count = 0
        for path in (WORK / 'runs').glob('*/*'):
            if path.name in ('req.txt', 'req2.txt', 'file3.txt') and path.is_file():
                path.unlink()
                count += 1
        print(f'Deleted {count} private HTML/diff working files; logs and metadata preserved.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        print(f'Lab runner refused/failed: {error}', file=sys.stderr)
        sys.exit(2)
