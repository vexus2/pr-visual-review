import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'pr-visual-review/scripts/auth_config.py'
spec = importlib.util.spec_from_file_location('auth_config', SCRIPT)
auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)


def form_config():
    return {'schema_version': 1, 'auth': {
        'mode': 'form', 'login_path': '/signin', 'target_path': '/settings/site',
        'account_label': '開発用管理者', 'required_role': 'site-admin',
        'steps': ['メールアドレス欄とパスワード欄へ参照値を入力しログイン'],
        'success_checks': ['管理者表示と対象fixtureを確認'],
        'credentials': {'source': 'env', 'username': 'REVIEW_USER', 'password': 'REVIEW_PASSWORD'},
    }}


class AuthConfigTest(unittest.TestCase):
    def test_form_env_references_are_accepted_without_reading_secrets(self):
        config = form_config()
        summary = auth.validate(config)
        self.assertEqual(summary['mode'], 'form')
        self.assertEqual(summary['credentials_source'], 'env')
        self.assertNotIn('REVIEW_PASSWORD', json.dumps(summary))

    def test_local_file_reference_is_not_opened(self):
        config = form_config()
        config['auth']['credentials'] = {'source': 'local-file', 'path': '/not-opened/private.json',
                                         'username_key': 'email', 'password_key': 'password'}
        self.assertEqual(auth.validate(config)['credentials_source'], 'local-file')

    def test_existing_manual_fixture_and_public_modes(self):
        for mode in ['existing-session', 'manual', 'fixture', 'none']:
            config = form_config()
            config['auth']['mode'] = mode
            del config['auth']['credentials']
            if mode == 'fixture': config['auth']['guide'] = 'docs/local-fixture.md'
            with self.subTest(mode=mode):
                self.assertEqual(auth.validate(config)['mode'], mode)

    def test_plaintext_and_unknown_fields_rejected_without_echo(self):
        for key in ['password', 'token', 'cookie', 'storage_state', 'allow_send', 'unrecognized']:
            config = form_config()
            config['auth'][key] = 'DO-NOT-ECHO-SECRET'
            with self.subTest(key=key), self.assertRaises(ValueError) as caught:
                auth.validate(config)
            self.assertNotIn('DO-NOT-ECHO-SECRET', str(caught.exception))

    def test_modes_do_not_retain_form_credentials_when_overridden(self):
        for mode in ['manual', 'existing-session', 'fixture', 'none']:
            config = form_config()
            config['auth']['mode'] = mode
            with self.subTest(mode=mode), self.assertRaises(ValueError): auth.validate(config)

    def test_form_requires_credentials_and_success_checks(self):
        for key in ['credentials', 'success_checks', 'login_path', 'required_role']:
            config = form_config()
            del config['auth'][key]
            with self.subTest(key=key), self.assertRaises(ValueError): auth.validate(config)

    def test_no_remote_or_executable_login_paths(self):
        for path in ['https://example.com/signin', '//example.com', 'javascript:alert(1)', '/signin?token=secret', '/signin#token', '/\\evil', '/sign\nin']:
            config = form_config()
            config['auth']['login_path'] = path
            with self.subTest(path=path), self.assertRaises(ValueError): auth.validate(config)

    def test_only_variable_names_can_be_env_references(self):
        for value in ['actual-password!', '${PASSWORD}', '', 'a b', 12]:
            config = form_config()
            config['auth']['credentials']['password'] = value
            with self.subTest(value=value), self.assertRaises(ValueError): auth.validate(config)

    def test_fixture_requires_guide_and_does_not_execute_it(self):
        config = form_config()
        config['auth'].update(mode='fixture')
        del config['auth']['credentials']
        with self.assertRaises(ValueError): auth.validate(config)
        config['auth']['guide'] = 'docs/nonexistent.md'
        self.assertEqual(auth.validate(config)['mode'], 'fixture')

    def test_cli_emits_only_safe_summary_and_never_free_text(self):
        config = form_config()
        config['auth']['steps'] = ['DONT_ECHO_UNTRUSTED_TEXT']
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            path.write_text(json.dumps(config))
            result = subprocess.run([sys.executable, str(SCRIPT), str(path)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('DONT_ECHO_UNTRUSTED_TEXT', result.stdout)
        self.assertEqual(json.loads(result.stdout)['mode'], 'form')

    def test_cli_invalid_json_does_not_echo_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            path.write_text('SECRET{"bad json')
            result = subprocess.run([sys.executable, str(SCRIPT), str(path)], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('SECRET', result.stdout + result.stderr)


if __name__ == '__main__': unittest.main()
