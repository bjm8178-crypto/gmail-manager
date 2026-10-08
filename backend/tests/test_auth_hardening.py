"""Offline security regressions; only selected module definitions are loaded.
No app startup, dotenv, model loading, OAuth or provider requests are performed.
"""
import ast
import asyncio
import hashlib
import json
import secrets
import sqlite3
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]


def definitions(filename, names, env):
    tree = ast.parse((ROOT / filename).read_text(encoding='utf-8'))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    for node in nodes:
        node.decorator_list = []
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, 'exec'), env)
    return env


class OAuthTests(unittest.TestCase):
    CLIENT_CONFIG = {
        'web': {
            'client_id': 'offline-client',
            'client_secret': 'offline-secret',
            'auth_uri': 'https://accounts.google.test/o/oauth2/auth',
            'token_uri': 'https://oauth2.google.test/token',
            'redirect_uris': ['https://test/callback'],
        }
    }
    SCOPES = [
        'openid',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.modify',
    ]

    def _token_response(self, payload):
        import requests
        response = requests.Response()
        response.status_code = 200
        response.headers['Content-Type'] = 'application/json'
        response._content = json.dumps(payload).encode('utf-8')
        response.encoding = 'utf-8'
        response.request = requests.Request(
            'POST', self.CLIENT_CONFIG['web']['token_uri']
        ).prepare()
        return response

    def _callback_env(self, calls, scopes=None):
        from google_auth_oauthlib.flow import Flow
        return dict(
            Flow=Flow,
            CLIENT_CONFIG=self.CLIENT_CONFIG,
            SCOPES=scopes or self.SCOPES,
            REDIRECT_URI='https://test/callback',
            logger=Mock(),
            save_token=lambda *args, **kwargs: calls.append('token'),
            _SCOPE_ALIASES={
                'email': 'https://www.googleapis.com/auth/userinfo.email',
                'profile': 'https://www.googleapis.com/auth/userinfo.profile',
            },
            json=json,
        )

    def _callback_definitions(self, env):
        definitions(
            'auth.py',
            [
                '_scope_response_payload',
                '_scope_values',
                '_scope_validation_hook',
                '_install_scope_validation_hook',
                'handle_callback',
            ],
            env,
        )

    def _run_callback(self, token_payload, calls=None, scopes=None, code_verifier=None):
        from unittest.mock import patch
        from requests_oauthlib import OAuth2Session

        calls = [] if calls is None else calls
        db = SimpleNamespace(
            upsert_user=lambda *args: calls.append('user') or 1,
            seed_default_labels=lambda *args: None,
        )
        userinfo = Mock(status_code=200)
        userinfo.json.return_value = {'email': 'test@example.com'}
        env = self._callback_env(calls, scopes=scopes)
        self._callback_definitions(env)
        token_response = self._token_response(token_payload)
        with patch.dict('sys.modules', database=db), \
                patch.object(OAuth2Session, 'request', return_value=token_response) as token_request, \
                patch('requests.get', return_value=userinfo) as userinfo_get:
            result = env['handle_callback']('single-use-code', code_verifier=code_verifier)
        return result, calls, env, token_request, userinfo_get

    def test_real_flow_constructs_oauth2session_with_requested_scopes(self):
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(self.CLIENT_CONFIG, scopes=self.SCOPES)

        self.assertEqual(flow.oauth2session.scope, self.SCOPES)

    def test_first_login_creates_user_before_token_update(self):
        payload = {
            'access_token': 'access',
            'refresh_token': 'refresh',
            'token_type': 'Bearer',
            'expires_in': 3600,
            'scope': ' '.join(self.SCOPES),
        }

        result, calls, _, _, _ = self._run_callback(payload)

        self.assertEqual(calls, ['user', 'token'])
        self.assertTrue(result['success'])

    def test_exact_scope_match_succeeds_with_real_oauthlib_parsing(self):
        payload = {
            'access_token': 'access',
            'refresh_token': 'refresh',
            'token_type': 'Bearer',
            'expires_in': 3600,
            'scope': ' '.join(self.SCOPES),
        }

        result, _, _, _, _ = self._run_callback(payload)

        self.assertTrue(result['success'])
        self.assertEqual(result['user_id'], 1)

    def test_scope_omitted_in_response_succeeds_per_rfc6749(self):
        payload = {
            'access_token': 'access',
            'refresh_token': 'refresh',
            'token_type': 'Bearer',
            'expires_in': 3600,
        }

        result, _, _, _, _ = self._run_callback(payload)

        self.assertTrue(result['success'])

    def test_additional_granted_scope_is_accepted_and_preserved(self):
        from unittest.mock import patch
        from requests_oauthlib import OAuth2Session

        additional_scope = 'https://www.googleapis.com/auth/calendar.readonly'
        payload = {
            'access_token': 'access',
            'refresh_token': 'refresh',
            'token_type': 'Bearer',
            'expires_in': 3600,
            'scope': ' '.join(self.SCOPES + [additional_scope]),
        }
        saved = []
        calls = []
        db = SimpleNamespace(
            upsert_user=lambda *args: calls.append('user') or 1,
            seed_default_labels=lambda *args: None,
        )
        userinfo = Mock(status_code=200)
        userinfo.json.return_value = {'email': 'test@example.com'}
        env = self._callback_env(calls)
        env['save_token'] = lambda creds, *args, **kwargs: saved.append(creds)
        self._callback_definitions(env)
        with patch.dict('sys.modules', database=db), \
                patch.object(OAuth2Session, 'request',
                             return_value=self._token_response(payload)), \
                patch('requests.get', return_value=userinfo):
            result = env['handle_callback']('single-use-code')

        self.assertTrue(result['success'])
        self.assertEqual(saved[0].granted_scopes, self.SCOPES + [additional_scope])
        self.assertEqual(
            json.loads(saved[0].to_json())["scopes"],
            self.SCOPES + [additional_scope],
        )

    def test_google_email_profile_aliases_are_equivalent_for_required_scopes(self):
        from unittest.mock import patch
        from requests_oauthlib import OAuth2Session

        granted = ['openid', 'email', 'profile', self.SCOPES[3], self.SCOPES[4]]
        payload = {
            'access_token': 'access',
            'refresh_token': 'refresh',
            'token_type': 'Bearer',
            'expires_in': 3600,
            'scope': ' '.join(granted),
        }
        saved = []
        calls = []
        db = SimpleNamespace(
            upsert_user=lambda *args: calls.append('user') or 1,
            seed_default_labels=lambda *args: None,
        )
        userinfo = Mock(status_code=200)
        userinfo.json.return_value = {'email': 'test@example.com'}
        env = self._callback_env(calls)
        env['save_token'] = lambda creds, *args, **kwargs: saved.append(creds)
        self._callback_definitions(env)
        with patch.dict('sys.modules', database=db), \
                patch.object(OAuth2Session, 'request',
                             return_value=self._token_response(payload)), \
                patch('requests.get', return_value=userinfo):
            result = env['handle_callback']('single-use-code')

        self.assertTrue(result['success'])
        self.assertEqual(saved[0].granted_scopes, granted)

    def test_missing_required_scope_fails_before_userinfo_or_persistence_even_with_relax_flag(self):
        import os
        from unittest.mock import patch
        from requests_oauthlib import OAuth2Session

        granted = self.SCOPES[:-1]
        payload = {
            'access_token': 'access',
            'refresh_token': 'refresh',
            'token_type': 'Bearer',
            'expires_in': 3600,
            'scope': ' '.join(granted),
        }
        calls = []
        db = SimpleNamespace(
            upsert_user=lambda *args: calls.append('user') or 1,
            seed_default_labels=lambda *args: None,
        )
        userinfo = Mock(status_code=200)
        env = self._callback_env(calls)
        self._callback_definitions(env)
        with patch.dict('sys.modules', database=db), \
                patch.dict(os.environ, {'OAUTHLIB_RELAX_TOKEN_SCOPE': '1'}), \
                patch.object(OAuth2Session, 'request',
                             return_value=self._token_response(payload)) as token_request, \
                patch('requests.get', return_value=userinfo) as userinfo_get:
            with self.assertRaisesRegex(ValueError, 'required'):
                env['handle_callback']('single-use-code')

        self.assertEqual(token_request.call_count, 1)
        userinfo_get.assert_not_called()
        self.assertEqual(calls, [])

    def test_malformed_scope_response_fails_before_userinfo_or_persistence(self):
        from unittest.mock import patch
        from requests_oauthlib import OAuth2Session

        payload = {
            'access_token': 'access',
            'refresh_token': 'refresh',
            'token_type': 'Bearer',
            'expires_in': 3600,
            'scope': ['openid', self.SCOPES[1]],
        }
        calls = []
        db = SimpleNamespace(
            upsert_user=lambda *args: calls.append('user') or 1,
            seed_default_labels=lambda *args: None,
        )
        userinfo = Mock(status_code=200)
        env = self._callback_env(calls)
        self._callback_definitions(env)
        with patch.dict('sys.modules', database=db), \
                patch.object(OAuth2Session, 'request',
                             return_value=self._token_response(payload)) as token_request, \
                patch('requests.get', return_value=userinfo) as userinfo_get:
            with self.assertRaisesRegex(ValueError, 'scope'):
                env['handle_callback']('single-use-code')

        self.assertEqual(token_request.call_count, 1)
        userinfo_get.assert_not_called()
        self.assertEqual(calls, [])

    def test_rfc_invalid_scope_tokens_fail_before_userinfo_or_persistence(self):
        from unittest.mock import patch
        from requests_oauthlib import OAuth2Session

        invalid_tokens = ['bad"scope', r'bad\\scope', 'bad\nscope', 'scópе']
        for invalid_token in invalid_tokens:
            with self.subTest(invalid_token=repr(invalid_token)):
                payload = {
                    'access_token': 'access',
                    'refresh_token': 'refresh',
                    'token_type': 'Bearer',
                    'expires_in': 3600,
                    'scope': ' '.join([self.SCOPES[0], invalid_token] + self.SCOPES[1:]),
                }
                calls = []
                db = SimpleNamespace(
                    upsert_user=lambda *args: calls.append('user') or 1,
                    seed_default_labels=lambda *args: None,
                )
                userinfo = Mock(status_code=200)
                env = self._callback_env(calls)
                self._callback_definitions(env)
                with patch.dict('sys.modules', database=db), \
                        patch.object(OAuth2Session, 'request',
                                     return_value=self._token_response(payload)), \
                        patch('requests.get', return_value=userinfo) as userinfo_get:
                    with self.assertRaisesRegex(ValueError, 'scope'):
                        env['handle_callback']('single-use-code')
                userinfo_get.assert_not_called()
                self.assertEqual(calls, [])

    def test_duplicate_scope_tokens_are_deduplicated_and_accepted(self):
        from unittest.mock import patch
        from requests_oauthlib import OAuth2Session

        payload = {
            'access_token': 'access',
            'refresh_token': 'refresh',
            'token_type': 'Bearer',
            'expires_in': 3600,
            'scope': ' '.join([self.SCOPES[0], self.SCOPES[1], self.SCOPES[1], *self.SCOPES[2:]]),
        }
        saved = []
        calls = []
        db = SimpleNamespace(
            upsert_user=lambda *args: calls.append('user') or 1,
            seed_default_labels=lambda *args: None,
        )
        userinfo = Mock(status_code=200)
        userinfo.json.return_value = {'email': 'test@example.com'}
        env = self._callback_env(calls)
        env['save_token'] = lambda creds, *args, **kwargs: saved.append(creds)
        self._callback_definitions(env)
        with patch.dict('sys.modules', database=db), \
                patch.object(OAuth2Session, 'request',
                             return_value=self._token_response(payload)), \
                patch('requests.get', return_value=userinfo):
            result = env['handle_callback']('single-use-code')

        self.assertTrue(result['success'])
        self.assertEqual(saved[0].granted_scopes, self.SCOPES)

    def test_include_client_id_and_pkce_are_forwarded_to_real_token_request(self):
        payload = {
            'access_token': 'access',
            'refresh_token': 'refresh',
            'token_type': 'Bearer',
            'expires_in': 3600,
            'scope': ' '.join(self.SCOPES),
        }

        _, _, _, token_request, _ = self._run_callback(
            payload, code_verifier='verifier-123'
        )

        request_kwargs = token_request.call_args.kwargs
        self.assertTrue(request_kwargs['data']['client_id'])
        self.assertEqual(request_kwargs['data']['code_verifier'], 'verifier-123')


class StateTests(unittest.TestCase):
    def test_state_is_browser_bound_expiring_and_single_use(self):
        import sys
        from unittest.mock import patch
        conn = sqlite3.connect(':memory:')
        db = SimpleNamespace(_get_connection=lambda: conn, _release_connection=lambda c: None,
                             _execute=lambda c, sql, args=(): c.execute(sql.replace('%s', '?'), args))
        flow = SimpleNamespace(code_verifier='pkce-secret', authorization_url=lambda **kw: ('https://google.test', 'random-state'))
        env = dict(hashlib=hashlib, secrets=secrets, time=time, Flow=SimpleNamespace(from_client_config=lambda *a, **kw: flow),
                   CLIENT_CONFIG={}, SCOPES=[], REDIRECT_URI='https://test/callback', logger=Mock())
        definitions('auth.py', ['_oauth_state_connection', 'get_auth_url', 'consume_oauth_state'], env)
        session = {}
        with patch.dict(sys.modules, database=db):
            env['get_auth_url'](session)
            self.assertIsNone(env['consume_oauth_state']('random-state', {}))
            self.assertEqual(env['consume_oauth_state']('random-state', session.copy()), 'pkce-secret')
            self.assertIsNone(env['consume_oauth_state']('random-state', session))
            env['get_auth_url'](session)
            conn.execute('UPDATE oauth_login_states SET expires_at = 0')
            conn.commit()
            self.assertIsNone(env['consume_oauth_state']('random-state', session))
        conn.close()


class EndpointTests(unittest.TestCase):
    def env(self):
        from fastapi import Request, Depends, HTTPException, UploadFile, File, Form
        from fastapi.responses import JSONResponse, HTMLResponse
        import sys
        sys.path.insert(0, str(ROOT))
        from schemas import AIRewriteRequest
        return dict(Request=Request, Depends=Depends, HTTPException=HTTPException,
                    UploadFile=UploadFile, File=File, Form=Form, JSONResponse=JSONResponse,
                    HTMLResponse=HTMLResponse, json=json, logger=Mock(),
                    require_auth=lambda: None, get_user_email_by_id=lambda uid: 'a@example.com',
                    MAX_REWRITE_BYTES=262144, MAX_ATTACHMENTS_BYTES=18*1024*1024,
                    AIRewriteRequest=AIRewriteRequest)

    def test_rewrite_route_requires_auth(self):
        from fastapi.params import Depends
        env = self.env()
        definitions('main.py', ['ai_rewrite'], env)
        import inspect
        signature = inspect.signature(env['ai_rewrite'])
        self.assertIn('user', signature.parameters)
        self.assertIsInstance(signature.parameters['user'].default, Depends)

    def test_rewrite_rejects_oversize_stream_before_provider(self):
        env = self.env()
        async def stream():
            yield b'x' * 262145
        env['ai_router'] = Mock()
        definitions('main.py', ['_bounded_json', 'ai_rewrite'], env)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(env['_bounded_json'](SimpleNamespace(stream=stream), 262144))
        self.assertEqual(caught.exception.status_code, 413)
        env['ai_router'].analyze.assert_not_called()

    def test_attachment_declared_aggregate_rejected_before_read(self):
        env = self.env()
        uploads = [SimpleNamespace(size=10*1024*1024, read=Mock()) for _ in range(2)]
        definitions('main.py', ['send_reply_endpoint'], env)
        result = asyncio.run(env['send_reply_endpoint']('email', 'body', uploads, {'user_id': 1}))
        self.assertEqual(result.status_code, 413)
        for upload in uploads:
            upload.read.assert_not_called()

    def test_callback_rejects_missing_state_before_exchange(self):
        env = self.env()
        env.update(consume_oauth_state=lambda state, session: None, handle_callback=Mock())
        definitions('main.py', ['auth_callback'], env)
        result = asyncio.run(env['auth_callback'](SimpleNamespace(query_params={'code': 'x'}, session={})))
        self.assertEqual(result.status_code, 400)
        env['handle_callback'].assert_not_called()


if __name__ == '__main__':
    unittest.main()
