import base64
import hashlib
from urllib.parse import parse_qs, urlsplit
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app, Settings, Session, SESSION_COOKIE, OBJECT_FIELDS
from tests.fake_salesforce import FakeSalesforce, PREFIX, REQUIRED


@pytest.fixture
def setup():
    fake = FakeSalesforce()
    cfg = Settings(login_url='https://example.my.salesforce.com', client_id='test-client', client_secret='test-secret')
    app = create_app(cfg, transport=httpx.MockTransport(fake))
    s = Session('test-access', 'test-refresh', 'https://mock-only.my.salesforce.com')
    app.state.store.sessions['test-session'] = s
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE, 'test-session')
        yield client, fake, app, s


def headers(session): return {'X-CSRF-Token': session.csrf, 'Origin': 'http://localhost:8008'}


def test_login_required_and_no_secrets_in_session(setup):
    client, fake, app, s = setup
    body = client.get('/api/session').json()
    assert body['authenticated'] and body['csrfToken'] == s.csrf
    assert 'test-access' not in str(body) and 'test-refresh' not in str(body) and 'test-secret' not in str(body)
    client.cookies.clear()
    assert client.get('/api/objects').status_code == 401
    assert client.post('/api/objects/Account/records', json={'values': {'Name': 'x'}}).status_code == 401


def test_oauth_pkce_state_and_browser_binding(setup):
    client, fake, app, s = setup
    response = client.get('/auth/login', follow_redirects=False)
    query = parse_qs(urlsplit(response.headers['location']).query)
    state = query['state'][0]
    pending = app.state.store.pending[state]
    expected = base64.urlsafe_b64encode(hashlib.sha256(pending['verifier'].encode()).digest()).decode().rstrip('=')
    assert query['code_challenge'] == [expected]
    assert query['code_challenge_method'] == ['S256']
    assert query['redirect_uri'] == ['http://localhost:8008/auth/callback']
    assert 'test-secret' not in response.headers['location']
    response = client.get('/auth/callback', params={'state': state, 'code': 'test-code'}, follow_redirects=False)
    assert response.status_code == 303 and response.headers['location'] == '/'
    assert 'HttpOnly' in response.headers['set-cookie']
    assert client.get('/api/session').json()['authenticated']
    assert client.get('/auth/callback', params={'state': state, 'code': 'replay'}).status_code == 400
    assert client.get('/auth/callback', params={'state': 'forged', 'code': 'code'}).status_code == 400


def test_callback_rejects_another_browser_and_cancel_is_safe(setup):
    client, fake, app, s = setup
    response = client.get('/auth/login', follow_redirects=False)
    state = parse_qs(urlsplit(response.headers['location']).query)['state'][0]
    client.cookies.clear()
    assert client.get('/auth/callback', params={'state': state, 'code': 'code'}).status_code == 400
    response = client.get('/auth/login', follow_redirects=False)
    state = parse_qs(urlsplit(response.headers['location']).query)['state'][0]
    response = client.get('/auth/callback', params={'state': state, 'error': 'access_denied'}, follow_redirects=False)
    assert response.status_code == 303 and 'cancelled' in response.headers['location']


@pytest.mark.parametrize('name', list(OBJECT_FIELDS))
def test_schema_paging_and_complete_crud_for_each_object(setup, name):
    client, fake, app, s = setup
    meta = client.get(f'/api/objects/{name}/schema').json()
    assert 5 <= len(meta['fields']) <= 10
    all_rows = []
    cursor = ''
    while True:
        response = client.get(f'/api/objects/{name}/records', params={'after': cursor})
        assert response.status_code == 200
        page = response.json()
        assert len(page['records']) <= 20
        all_rows += page['records']
        cursor = page['nextCursor']
        if not cursor: break
    assert len(all_rows) == 45 and len({r['Id'] for r in all_rows}) == 45
    values = {field: 'CV test' for field in REQUIRED[name]}
    if name == 'Opportunity': values.update(StageName='Prospecting', CloseDate='2026-12-01')
    if name == 'Case': values = {'Subject': 'CV test'}
    response = client.post(f'/api/objects/{name}/records', json={'values': values}, headers=headers(s))
    assert response.status_code == 201, response.text
    rid = response.json()['id']
    assert rid.startswith(PREFIX[name])
    assert client.get(f'/api/objects/{name}/records/{rid}').status_code == 200
    change = {'Subject': 'Updated test'} if name == 'Case' else {'Description': 'Updated test'}
    assert client.patch(f'/api/objects/{name}/records/{rid}', json={'values': change}, headers=headers(s)).status_code == 200
    row = client.get(f'/api/objects/{name}/records/{rid}').json()
    assert all(row[k] == v for k, v in change.items())
    assert client.delete(f'/api/objects/{name}/records/{rid}', headers=headers(s)).status_code == 200
    assert client.get(f'/api/objects/{name}/records/{rid}').status_code == 404


def test_rejects_unsupported_objects_injection_wrong_prefix_and_readonly_fields(setup):
    client, fake, app, s = setup
    assert client.get('/api/objects/User/records').status_code == 404
    assert client.get('/api/objects/Account/records', params={'after': "' OR Name != ''"}).status_code == 400
    assert client.get('/api/objects/Account/records/003000000000001AAA').status_code == 400
    assert client.post('/api/objects/Account/records', json={'values': {'Name': 'x', 'Id': 'evil'}}, headers=headers(s)).status_code == 422
    assert client.post('/api/objects/Account/records', json={'values': {'Name': {'nested': 'evil'}}}, headers=headers(s)).status_code == 422


def test_csrf_origin_and_required_fields(setup):
    client, fake, app, s = setup
    url = '/api/objects/Account/records'
    assert client.post(url, json={'values': {'Name': 'x'}}).status_code == 403
    assert client.post(url, json={'values': {'Name': 'x'}}, headers={**headers(s), 'Origin': 'https://other.example'}).status_code == 403
    assert client.post(url, json={'values': {'Description': 'Missing name'}}, headers=headers(s)).status_code == 422


def test_permissions_and_salesforce_validation_messages(setup):
    client, fake, app, s = setup
    fake.denied.add('Case')
    assert client.post('/api/objects/Case/records', json={'values': {'Subject': 'x'}}, headers=headers(s)).status_code == 403
    assert client.delete('/api/objects/Case/records/500000000000001AAA', headers=headers(s)).status_code == 403
    response = client.post('/api/objects/Account/records', json={'values': {'Name': 'reject'}}, headers=headers(s))
    assert response.status_code == 400 and 'validation rule' in response.json()['detail']


def test_refresh_and_logout(setup):
    client, fake, app, s = setup
    s.access_token = 'expired'
    assert client.get('/api/objects/Account/records').status_code == 200
    assert fake.refreshes == 1 and s.access_token == 'test-access'
    response = client.post('/auth/logout', headers=headers(s))
    assert response.status_code == 200
    assert not client.get('/api/session').json()['authenticated']
    assert any(r.url.path.endswith('/revoke') for r in fake.requests)


def test_expired_refresh_requires_new_login(setup):
    client, fake, app, s = setup
    fake.fail_refresh = True
    s.access_token = 'expired'
    assert client.get('/api/objects/Account/records').status_code == 401
    assert not client.get('/api/session').json()['authenticated']


def test_missing_configuration_stays_disconnected():
    app = create_app(Settings())
    with TestClient(app) as client:
        assert not client.get('/api/session').json()['configured']
        response = client.get('/auth/login', follow_redirects=False)
        assert response.status_code == 303 and 'configuration' in response.headers['location']


def test_session_timeout(setup):
    client, fake, app, s = setup
    s.expires = 0
    assert client.get('/api/objects/Account/records').status_code == 401
    assert not client.get('/api/session').json()['authenticated']
