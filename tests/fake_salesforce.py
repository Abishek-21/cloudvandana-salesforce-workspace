"""Mock Salesforce responses for backend tests."""
import json
import re
from urllib.parse import parse_qs
import httpx
from backend.main import OBJECT_FIELDS

PREFIX = {'Account': '001', 'Opportunity': '006', 'Lead': '00Q', 'Contact': '003', 'Case': '500'}
REQUIRED = {'Account': ['Name'], 'Opportunity': ['Name', 'StageName', 'CloseDate'],
            'Lead': ['LastName', 'Company'], 'Contact': ['LastName'], 'Case': []}


def metadata(name):
    fields = []
    for fname in OBJECT_FIELDS[name]:
        kind = ('id' if fname == 'Id' else 'reference' if fname.endswith('Id') else
                'date' if fname == 'CloseDate' else 'currency' if fname == 'Amount' else
                'percent' if fname == 'Probability' else 'email' if 'Email' in fname else
                'textarea' if fname == 'Description' else 'picklist' if fname in ('Type', 'Status', 'StageName', 'Priority', 'Origin', 'Industry') else 'string')
        editable = fname not in ('Id', 'CaseNumber')
        options = ([{'value': 'Prospecting', 'label': 'Prospecting', 'active': True}] if fname == 'StageName' else
                   [{'value': 'New', 'label': 'New', 'active': True}, {'value': 'Working', 'label': 'Working', 'active': True}] if fname == 'Status' else
                   [{'value': 'Example', 'label': 'Example', 'active': True}] if kind == 'picklist' else [])
        fields.append({'name': fname, 'label': re.sub(r'(?<!^)([A-Z])', r' \1', fname), 'type': kind,
                       'createable': editable, 'updateable': editable,
                       'nillable': fname not in REQUIRED[name], 'defaultedOnCreate': fname in ('Id', 'CaseNumber'),
                       'length': 255, 'scale': 2, 'referenceTo': ['Account'] if fname == 'AccountId' else ['Contact'] if fname == 'ContactId' else [],
                       'picklistValues': options})
    return {'name': name, 'label': name, 'labelPlural': name + 's', 'keyPrefix': PREFIX[name],
            'queryable': True, 'createable': True, 'updateable': True, 'deletable': True, 'fields': fields}


class FakeSalesforce:
    def __init__(self, count=45):
        self.requests = []
        self.refreshes = 0
        self.denied = set()
        self.fail_refresh = False
        self.rows = {name: [self.make_row(name, n) for n in range(1, count + 1)] for name in PREFIX}

    def make_row(self, name, n):
        row = {field: None for field in OBJECT_FIELDS[name]}
        row['Id'] = PREFIX[name] + f'{n:012d}' + 'AAA'
        if 'Name' in row: row['Name'] = f'Mock {name} {n:02d}'
        if 'LastName' in row: row['LastName'] = f'Mock person {n:02d}'
        if name == 'Lead': row['Company'] = 'Mock company'
        if name == 'Case': row.update(Subject=f'Mock support request {n:02d}', CaseNumber=f'{n:08d}', Status='New')
        if name == 'Opportunity': row.update(StageName='Prospecting', CloseDate='2026-12-01', Amount=n * 100)
        return row

    def __call__(self, request):
        self.requests.append(request)
        path = request.url.path
        if path.endswith('/token'):
            values = parse_qs(request.content.decode())
            if values.get('grant_type') == ['refresh_token']:
                self.refreshes += 1
                if self.fail_refresh: return httpx.Response(400, json={'error': 'invalid_grant'})
            return httpx.Response(200, json={'access_token': 'test-access', 'refresh_token': 'test-refresh',
                                              'instance_url': 'https://mock-only.my.salesforce.com'})
        if path.endswith('/revoke'): return httpx.Response(200, json={})
        if request.headers.get('authorization') == 'Bearer expired':
            return httpx.Response(401, json=[{'errorCode': 'INVALID_SESSION_ID', 'message': 'Expired'}])
        if path == '/services/data/': return httpx.Response(200, json=[{'version': '66.0'}, {'version': '67.0'}])
        if path.endswith('/describe'):
            name = path.split('/')[-2]
            meta = metadata(name)
            if name in self.denied: meta.update(createable=False, updateable=False, deletable=False)
            return httpx.Response(200, json=meta)
        if path.endswith('/query'):
            query = request.url.params['q']
            name = re.search(r' FROM (\w+)', query)[1]
            after = re.search(r"Id > '([A-Za-z0-9]+)'", query)
            rows = [r for r in self.rows[name] if not after or r['Id'] > after[1]][:20]
            return httpx.Response(200, json={'records': rows, 'done': True, 'totalSize': len(rows)})
        parts = path.split('/sobjects/')[-1].split('/')
        name = parts[0]
        if name not in PREFIX: raise AssertionError(f'Unexpected mock Salesforce request: {path}')
        if request.method == 'POST':
            values = json.loads(request.content)
            if values.get('Name') == 'reject': return httpx.Response(400, json=[{'message': 'Mock validation rule rejected the name.'}])
            row = self.make_row(name, len(self.rows[name]) + 100)
            row.update(values); self.rows[name].append(row)
            return httpx.Response(201, json={'id': row['Id'], 'success': True, 'errors': []})
        rid = parts[1]
        row = next((r for r in self.rows[name] if r['Id'] == rid), None)
        if row is None: return httpx.Response(404, json=[{'message': 'Record not found.'}])
        if request.method == 'GET': return httpx.Response(200, json=row)
        if request.method == 'PATCH': row.update(json.loads(request.content)); return httpx.Response(204)
        if request.method == 'DELETE': self.rows[name].remove(row); return httpx.Response(204)
        raise AssertionError('Unexpected method')
