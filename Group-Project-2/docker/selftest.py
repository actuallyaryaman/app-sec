"""Offline tests of safeguards and invocation; never remote-run evidence."""
import io
from pathlib import Path
import runpy
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import requests

import entrypoint as lab

URL = 'https://test.web-security-academy.net'


class SafeguardTests(unittest.TestCase):
    def test_url_normalization_and_rejection(self):
        self.assertEqual(lab.validate_url(URL, base=True), URL + '/')
        self.assertEqual(lab.validate_url(URL + ':443/', base=True), URL + '/')
        for value in ('http://test.web-security-academy.net/', 'https://web-security-academy.net/',
                      'https://evilweb-security-academy.net/',
                      'https://test.web-security-academy.net.example.org/',
                      'https://test.web-security-academy.net@evil.example/',
                      'https://user:pass@test.web-security-academy.net/',
                      'https://test.web-security-academy.net:8443/', URL + '/login',
                      URL + '/?token=secret', URL + '/#fragment', URL + '\\evil',
                      URL + '/\n', 'https://.web-security-academy.net/'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                lab.validate_url(value, base=True)

    def test_transport_and_cross_host_redirect(self):
        def response(adapter, request, **kwargs):
            self.assertIs(kwargs['verify'], True)
            self.assertEqual(kwargs['proxies'], {})
            result = requests.Response()
            result.status_code = 302
            result.url = request.url
            result.request = request
            result.headers['Location'] = 'https://unrelated.example/blocked'
            result._content = b''
            return result
        events = io.StringIO()
        with mock.patch.object(requests.adapters.HTTPAdapter, 'send', response):
            guard = lab.Guard('test.web-security-academy.net', events)
            guard.install()
            try:
                # First fake response redirects; actual Requests redirect code hits guard again.
                with self.assertRaises(ValueError):
                    requests.get(URL + '/login', verify=False,
                                 proxies={'https': 'http://127.0.0.1:8080'})
                self.assertEqual(guard.count, 1)
            finally:
                guard.restore()
        self.assertIn('302', events.getvalue())
        self.assertNotIn('Cookie', events.getvalue())

    def test_redaction_of_fragmented_prints(self):
        terminal, logfile = io.StringIO(), io.StringIO()
        output = lab.Output(terminal, 'stdout', logfile)
        output.write('i: 1 co')
        output.write('de: PRIVATE-GIFT-CODE\n')
        output.write('session=PRIVATE-SESSION\rtry 2\r')
        output.finish()
        for stream in (terminal, logfile):
            self.assertNotIn('PRIVATE-', stream.getvalue())
            self.assertIn('[REDACTED]', stream.getvalue())
            self.assertIn('try 2', stream.getvalue())

    def test_gift_card_correlation_does_not_expose_values(self):
        def response(adapter, request, **kwargs):
            result = requests.Response()
            result.status_code = 302
            result._content = b''
            return result
        events = io.StringIO()
        with mock.patch.object(requests.adapters.HTTPAdapter, 'send', response):
            guard = lab.Guard('test.web-security-academy.net', events)
            guard.install()
            try:
                for card in ('PRIVATE-A', 'PRIVATE-A', 'PRIVATE-B'):
                    requests.post(URL + '/gift-card', data={'gift-card': card}, allow_redirects=False)
            finally:
                guard.restore()
        self.assertNotIn('PRIVATE-', events.getvalue())
        import json
        rows = [json.loads(row) for row in events.getvalue().splitlines()]
        self.assertEqual([r['gift_card_reference'] for r in rows], [1, 1, 2])
        self.assertEqual([r['gift_card_seen_before'] for r in rows], [False, True, False])

    def test_sources_syntax_and_usage_without_requests(self):
        for variant in lab.FILES:
            text = lab.source(variant)
            compile(text, lab.FILES[variant], 'exec')
            safe = lab.safe_copy(text)
            self.assertNotIn('verify=False', safe)
            self.assertNotIn('127.0.0.1:8080', safe)
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / lab.FILES[variant]
                path.write_text(safe)
                with mock.patch.object(sys, 'argv', [str(path)]), \
                     mock.patch.object(sys, 'stdout', io.StringIO()), \
                     mock.patch.object(requests.adapters.HTTPAdapter, 'send') as send:
                    with self.assertRaises(SystemExit) as error:
                        runpy.run_path(str(path), run_name='__main__')
                    self.assertEqual(error.exception.code, 1)
                    send.assert_not_called()
        self.assertIsNotNone(lab.shutil.which('diff'))

    def test_exit_code_and_interrupt_recorded(self):
        # Execute a local sleeping synthetic script in a separate process, no HTTP or lab target.
        # It substitutes runner input for this test only; never exported as actual evidence.
        harness = '''
import entrypoint as lab
from pathlib import Path
import sys
lab.WORK = Path(sys.argv[1])
lab.source = lambda variant: "import time\\nprint('ready', flush=True)\\ntime.sleep(60)\\n"
lab.safe_copy = lambda text: text
sys.exit(lab.run('original', 'https://test.web-security-academy.net/', False))
'''
        with tempfile.TemporaryDirectory() as temporary:
            process = subprocess.Popen([sys.executable, '-u', '-c', harness, temporary],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                for _ in range(5):
                    line = process.stdout.readline()
                    if '[stdout] ready' in line:
                        break
                else:
                    self.fail('Synthetic child did not signal readiness')
                process.send_signal(signal.SIGINT)
                stdout, stderr = process.communicate(timeout=10)
                self.assertEqual(process.returncode, 130)
                metadata = next(Path(temporary).glob('runs/*/metadata.json'))
                self.assertIn('"exit_code": 130', metadata.read_text())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()


def main():
    print('Offline synthetic safeguard tests; not evidence about any remote lab.', flush=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SafeguardTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1
