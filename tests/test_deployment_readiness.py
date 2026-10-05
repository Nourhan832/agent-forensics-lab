"""Deployment controls exercised without provider calls or working storage."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json
import sqlite3
import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from openai import APITimeoutError
from backend.app.api import main
from backend.app.api.deployment import (Settings, PublicAdmissionMiddleware, DailyAllowance,
    PublicLimitExceeded, public_workflow_budget, reserve_model_request, cors_origins, budget_path)
from backend.app.integrations import nemotron


def limited_app(settings):
    app=FastAPI()
    app.add_middleware(PublicAdmissionMiddleware, settings=settings)
    @app.post('/api/action')
    def action():return {'ok':True}
    @app.get('/health')
    def health():return {'ok':True}
    return app


def test_rate_limit_cannot_be_bypassed_by_forged_forwarded_headers():
    with TestClient(limited_app(Settings(rate_requests=2))) as client:
        assert client.post('/api/action',headers={'X-Forwarded-For':'192.0.2.1'}).status_code==200
        assert client.post('/api/action',headers={'X-Forwarded-For':'192.0.2.2'}).status_code==200
        rejection=client.post('/api/action',headers={'X-Forwarded-For':'192.0.2.3'})
        assert rejection.status_code==429 and rejection.headers['retry-after']=='60'
        assert client.get('/health').status_code==200


def test_large_streaming_request_rejected_before_application():
    with TestClient(limited_app(Settings(max_request_bytes=1024))) as client:
        response=client.post('/api/action',content=iter([b'x'*600,b'y'*600]))
        assert response.status_code==413
        assert 'xxxx' not in response.text


def test_request_concurrency_returns_429_and_recovers():
    async def exercise():
        entered,release=asyncio.Event(),asyncio.Event()
        async def endpoint(scope,receive,send):
            entered.set();await release.wait()
            await send({'type':'http.response.start','status':200,'headers':[]})
            await send({'type':'http.response.body','body':b'ok'})
        middleware=PublicAdmissionMiddleware(endpoint,Settings(concurrent_requests=1))
        scope={'type':'http','method':'GET','path':'/health','client':('peer',0)}
        async def receive():return {'type':'http.request','body':b''}
        first,second=[],[]
        async def send_first(m):first.append(m)
        async def send_second(m):second.append(m)
        task=asyncio.create_task(middleware(scope,receive,send_first));await entered.wait()
        await middleware(scope,receive,send_second)
        assert second[0]['status']==429
        release.set();await task
        assert middleware.active==0 and first[0]['status']==200
    asyncio.run(exercise())


def test_daily_allowance_atomic_durable_and_idempotent(tmp_path):
    budget=DailyAllowance(tmp_path/'budget.sqlite3');budget.initialize()
    def reserve(_):
        try:budget.reserve(10,2);return True
        except PublicLimitExceeded:return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve,range(20)))==5
    budget.initialize()
    with pytest.raises(PublicLimitExceeded):budget.reserve(10,2)
    with sqlite3.connect(budget.path) as db:
        assert db.execute('SELECT reserved_requests FROM public_budget').fetchone()[0]==10


def test_public_workflow_limit_rejects_before_provider(client):
    with public_workflow_budget(Settings(max_calls_per_workflow=1),1) as budget:
        reserve_model_request()
        with pytest.raises(PublicLimitExceeded):reserve_model_request()
        assert budget.calls==1 and budget.rejection is not None


def test_native_adapter_cannot_swallow_budget_rejection(client,monkeypatch):
    monkeypatch.setattr(main,'deployment_settings',replace(main.deployment_settings,daily_request_allowance=2))
    with pytest.raises(HTTPException) as caught:
        with main.model_workflow():
            reserve_model_request()
            try:reserve_model_request()
            except PublicLimitExceeded:pass
    assert caught.value.status_code==429 and 'Retry-After' in caught.value.headers


def test_non_http_model_execution_does_not_apply_public_budget(monkeypatch,tmp_path):
    path=tmp_path/'not-created.sqlite3';monkeypatch.setenv('AFL_BUDGET_DATABASE_PATH',str(path))
    reserve_model_request()
    assert not path.exists()


def test_output_cap_is_optional_and_api_context_only(client,monkeypatch):
    requests=[]
    def create(**kwargs):
        requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{}'),finish_reason='stop')],id='fake-response')
    monkeypatch.setattr(nemotron,'get_client',lambda:SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    nemotron.generate_response('policy','task')
    assert 'max_tokens' not in requests[-1]
    with public_workflow_budget(Settings(public_output_tokens=1024),1):
        nemotron.generate_response('policy','task')
    assert requests[-1]['max_tokens']==1024
    with sqlite3.connect(budget_path()) as db:
        assert db.execute('SELECT reserved_requests FROM public_budget').fetchone()[0]==2


@pytest.mark.parametrize('name,value',[('AFL_MAX_CONCURRENT_WORKFLOWS','0'),('AFL_DAILY_MODEL_REQUEST_LIMIT','-1'),('AFL_RATE_LIMIT_REQUESTS','not-a-number')])
def test_invalid_limit_configuration_fails_closed(monkeypatch,name,value):
    monkeypatch.setenv(name,value)
    with pytest.raises(RuntimeError,match=name):Settings.from_environment()


@pytest.mark.parametrize('origins',['*','https://user:password@example.com','https://example.com/path'])
def test_cors_rejects_wildcard_credentials_and_non_origin(monkeypatch,origins):
    monkeypatch.setenv('AFL_CORS_ORIGINS',origins)
    with pytest.raises(RuntimeError):cors_origins()


def test_same_origin_cors_default_and_explicit_origin(monkeypatch):
    monkeypatch.delenv('AFL_CORS_ORIGINS',raising=False);assert cors_origins()==[]
    monkeypatch.setenv('AFL_CORS_ORIGINS','https://demo.example.com')
    assert cors_origins()==['https://demo.example.com']


def test_validation_errors_never_echo_request_content(client):
    response=client.post('/api/replay/cross_customer_data_access',json={'message':['sensitive-example-token']})
    assert response.status_code==422 and 'sensitive-example-token' not in response.text
    assert all('input' not in detail and 'ctx' not in detail for detail in response.json()['detail'])


def test_provider_timeout_safe_502(client,monkeypatch):
    def timeout(*args,**kwargs):raise APITimeoutError(request=httpx.Request('POST','https://private.example.invalid/private-path'))
    monkeypatch.setattr(main,'run_forensics',timeout)
    response=client.post('/api/investigate/cross_customer_data_access')
    assert response.status_code==502
    assert 'private' not in response.text and 'Traceback' not in response.text


def test_database_reinitialization_preserves_existing_case(client):
    from backend.app.storage import regressions
    case=regressions.save_regression_case('cross_customer_data_access','CROSS_CUSTOMER_ACCESS','Original','Exact','access_control','verified',True,['CROSS_CUSTOMER_ACCESS'],[])
    before=regressions.get_regression_case(case['id'])
    regressions.initialize_regression_storage();regressions.initialize_regression_storage()
    assert regressions.get_regression_case(case['id'])==before


def test_docker_packages_required_frozen_dependencies_and_nonroot_startup():
    docker=Path('Dockerfile').read_text(encoding='utf-8')
    assert 'USER appuser' in docker and 'VOLUME ["/data"]' in docker
    assert 'COPY data/emergency_response/usgs_events_v1.json' in docker
    assert 'COPY experiments/corpora/emergency_response_v2.json' in docker
    assert 'backend.app.api.serve' in docker and '--reload' not in docker
    assert 'COPY . ' not in docker and 'COPY .env' not in docker
    ignore=Path('.dockerignore').read_text();assert 'artifacts' in ignore and '*.sqlite*' in ignore


def test_packaged_emergency_adapter_constructs_from_frozen_fixture():
    from backend.app.api.emergency import frozen_case
    from backend.app.domains.emergency_response.adapter import EmergencyResponseReplayAdapter
    case=frozen_case('emergency_dispatch')
    assert EmergencyResponseReplayAdapter(case['scenario']).scenario==case['scenario']


def test_cors_wraps_capacity_and_rate_rejections():
    from fastapi.middleware.cors import CORSMiddleware
    assert main.app.user_middleware[0].cls is CORSMiddleware
    app=limited_app(Settings(rate_requests=1))
    app.add_middleware(CORSMiddleware,allow_origins=['https://demo.example.com'],allow_methods=['POST'])
    with TestClient(app) as client:
        headers={'Origin':'https://demo.example.com'}
        assert client.post('/api/action',headers=headers).status_code==200
        response=client.post('/api/action',headers=headers)
        assert response.status_code==429
        assert response.headers['access-control-allow-origin']=='https://demo.example.com'
