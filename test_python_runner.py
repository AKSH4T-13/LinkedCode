import asyncio
import json
from unittest.mock import patch
import httpx
import pytest
from backend.services.python_runner import PythonRunner, ExecutionUnavailable, encoded


def evaluate(handler,cases=None):
    client_class=httpx.AsyncClient
    def factory(**kwargs):
        return client_class(**kwargs,transport=httpx.MockTransport(handler))
    with patch('backend.services.python_runner.httpx.AsyncClient',factory):
        return asyncio.run(PythonRunner().evaluate('print(5)',cases or [{'input':'2 3','expected_output':'5'}]))


@pytest.mark.parametrize('status,output,error,verdict',[
    (3,'5\n','','Accepted'),(3,'6','','Wrong answer'),
    (6,'','SyntaxError: invalid syntax','Syntax error'),
    (11,'','ZeroDivisionError','Runtime error'),(11,'','SyntaxError: invalid syntax','Syntax error'),(8,'','','Output limit exceeded'),(5,'','','Time limit exceeded'),
])
def test_runtime_results_and_resource_limits(status,output,error,verdict):
    requests=[]
    def handler(request):
        requests.append(request)
        if request.method=='POST':
            body=json.loads(request.content)
            assert body['enable_network'] is False
            assert body['memory_limit']==131072
            assert body['cpu_time_limit']==3
            assert body['max_file_size']==64
            assert body['source_code']==encoded('print(5)')
            assert 'Authorization' not in request.headers
            return httpx.Response(201,json={'token':'abcdef-1234'})
        return httpx.Response(200,json={'status':{'id':status},'stdout':encoded(output),'stderr':encoded(error),'time':'0.1','memory':5000})
    result=evaluate(handler)[0]
    assert result['verdict']==verdict
    assert result['passed']==(verdict=='Accepted')
    assert result['error']==error


def test_custom_input_is_executed_not_judged():
    def handler(request):
        return httpx.Response(201,json={'token':'abc123'}) if request.method=='POST' else httpx.Response(200,json={'status':{'id':3},'stdout':encoded('5')})
    result=evaluate(handler,[{'input':'2 3'}])[0]
    assert result['passed'] is None and result['verdict']=='Executed'


def test_hidden_cases_do_not_disclose_test_data():
    def handler(request):
        return httpx.Response(201,json={'token':'abc123'}) if request.method=='POST' else httpx.Response(200,json={'status':{'id':3},'stdout':encoded('secret')})
    result=evaluate(handler,[{'input':'private input','expected_output':'secret','hidden':True}])[0]
    assert result['passed'] is True
    assert not {'input','stdout','expected_output','error'}.intersection(result)


@pytest.mark.parametrize('status',[401,429,500])
def test_provider_failure_is_not_wrong_answer(status):
    with pytest.raises(ExecutionUnavailable):
        evaluate(lambda request:httpx.Response(status,json={'error':'provider detail'}))


def test_internal_execution_failure_is_not_wrong_answer():
    def handler(request):
        return httpx.Response(201,json={'token':'abc123'}) if request.method=='POST' else httpx.Response(200,json={'status':{'id':13}})
    with pytest.raises(ExecutionUnavailable):evaluate(handler)


def test_polling_waits_for_completion():
    calls=0
    def handler(request):
        nonlocal calls
        if request.method=='POST':return httpx.Response(201,json={'token':'abc123'})
        calls+=1
        return httpx.Response(200,json={'status':{'id':2 if calls==1 else 3},'stdout':encoded('5')})
    assert evaluate(handler)[0]['passed'] is True
    assert calls==2
