import json
import sys
import time
import requests

BASE = 'http://127.0.0.1:8017'
USERNAME = 'admin'

def wait_until_ready(timeout=30):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            r = requests.get(BASE + '/', timeout=5)
            if r.ok:
                return True
        except Exception as exc:
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f'service not ready: {last_error}')

def post(path, payload, timeout=180):
    url = BASE + path
    last_exc = None
    for _ in range(2):
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            break
        except requests.exceptions.ConnectionError as exc:
            last_exc = exc
            time.sleep(2)
    else:
        raise last_exc
    try:
        data = r.json()
    except Exception:
        data = {'success': False, 'message': r.text, 'status_code': r.status_code}
    return r.status_code, data

def data_success(data):
    return bool(data.get('success')) and bool((data.get('data') or {}).get('success', data.get('success')))

def main():
    wait_until_ready()
    summary = []
    bootstrap = {
        'env': 'reg',
        'journey': '500K',
        'currency': 'USD',
        'funder_resource': 'FUNDPARK',
        'offline': True,
        'sp_status': 'SUCCESS',
        'username': USERNAME,
    }
    status, resp = post('/api/register-and-run-multishop', bootstrap, timeout=240)
    summary.append({'step': '1-8 register-and-run-multishop', 'http': status, 'success': data_success(resp), 'message': resp.get('message')})
    if not data_success(resp):
        print(json.dumps({'summary': summary, 'failed_response': resp}, ensure_ascii=False, indent=2))
        return 1
    data = resp['data']
    session = data['session']
    session_id = session['session_id']
    platform_offer_id = ''
    for item in data.get('steps', []):
        result = item.get('result') or {}
        platform_offer_id = result.get('platform_offer_id') or platform_offer_id
    steps = [
        ('9 create-application-context', '/api/mock/create-application-context', {'journey': '500K'}),
        ('10 business-info', '/api/mock/fp-business-profile', {'journey': '500K'}),
        ('11 director-info', '/api/mock/fp-director-info', {'journey': '500K'}),
        ('12 offer-limit-select', '/api/mock/fp-offer-limit-select', {'journey': '500K'}),
        ('13 offer-quote-activate', '/api/mock/fp-offer-quote-activate', {'journey': '500K'}),
        ('14 link-sp-3pl-shops', '/api/mock/fp-link-sp-3pl-shops', {'journey': '500K'}),
        ('15 scheduled-submit', '/api/mock/fp-scheduled-submit', {'journey': '500K'}),
        ('16 underwritten', '/api/mock/underwritten', {'amount': 500000, 'status': 'APPROVED'}),
        ('17 approved-offer', '/api/mock/approved-offer', {'amount': 500000, 'status': 'APPROVED'}),
        ('18 psp-start', '/api/mock/psp-start', {'status': 'PROCESSING'}),
        ('19 psp-completed', '/api/mock/psp-completed', {'status': 'SUCCESS'}),
        ('20 esign', '/api/mock/esign', {'signed_amount': 500000, 'status': 'SUCCESS'}),
    ]
    last_resp = None
    for name, path, extra in steps:
        payload = {'session_id': session_id, 'username': USERNAME, **extra}
        timeout = 180
        if name == '15 scheduled-submit':
            timeout = 720
        status, resp = post(path, payload, timeout=timeout)
        ok = data_success(resp)
        payload_data = resp.get('data') or {}
        summary.append({
            'step': name,
            'http': status,
            'success': ok,
            'message': resp.get('message'),
            'data_error': payload_data.get('error'),
            'application_status': payload_data.get('application_status'),
            'credit_offer_status': payload_data.get('credit_offer_status'),
            'limit_application_unique_id': payload_data.get('limit_application_unique_id'),
            'lender_approved_offer_id': payload_data.get('lender_approved_offer_id'),
        })
        last_resp = resp
        print(json.dumps(summary[-1], ensure_ascii=False), flush=True)
        if not ok:
            print(json.dumps({'summary': summary, 'session': session, 'platform_offer_id': platform_offer_id, 'failed_response': resp}, ensure_ascii=False, indent=2))
            return 1
    print(json.dumps({'summary': summary, 'session': session, 'platform_offer_id': platform_offer_id, 'final_response': last_resp}, ensure_ascii=False, indent=2))
    return 0

raise SystemExit(main())
