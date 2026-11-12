"""Remote Judge0 execution. Never runs user code on the application host."""
import asyncio
import base64
import os
import re
import time
from urllib.parse import urlparse
import httpx


class ExecutionUnavailable(Exception):
    pass


def encoded(value):
    return base64.b64encode(value.encode('utf-8')).decode('ascii')


def decoded(value):
    if not value:
        return ''
    try:
        return base64.b64decode(value, validate=True).decode('utf-8', errors='replace')
    except (ValueError, TypeError) as error:
        raise ExecutionUnavailable('Execution service returned an invalid response.') from error


class PythonRunner:
    def __init__(self):
        self.url = os.getenv('JUDGE0_URL', 'https://ce.judge0.com').rstrip('/')
        parsed = urlparse(self.url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ExecutionUnavailable('Execution service URL is not configured correctly.')
        if parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
            raise ExecutionUnavailable('Remote execution service must use HTTPS.')
        self.headers = {}
        if os.getenv('JUDGE0_AUTH_TOKEN'):
            self.headers['X-Auth-Token'] = os.environ['JUDGE0_AUTH_TOKEN']
        if os.getenv('JUDGE0_RAPIDAPI_KEY'):
            self.headers['X-RapidAPI-Key'] = os.environ['JUDGE0_RAPIDAPI_KEY']
            self.headers['X-RapidAPI-Host'] = parsed.netloc
        try:
            self.language_id = int(os.getenv('JUDGE0_PYTHON_LANGUAGE_ID', '100'))
        except ValueError as error:
            raise ExecutionUnavailable('Python runtime ID is not configured correctly.') from error

    async def _request(self, client, method, path, **kwargs):
        try:
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError('Expected an object')
            return result
        except (httpx.HTTPError, ValueError) as error:
            raise ExecutionUnavailable('Python execution service is unavailable or rate limited. Try again shortly.') from error

    async def _case(self, client, code, case, index, semaphore):
        async with semaphore:
            created = await self._request(client, 'POST', '/submissions', params={'base64_encoded':'true','wait':'false'}, json={
                'language_id':self.language_id,'source_code':encoded(code),'stdin':encoded(case['input']),
                'cpu_time_limit':3,'wall_time_limit':8,'memory_limit':131072,'max_file_size':64,'enable_network':False,
            })
            token = created.get('token')
            if not isinstance(token,str) or not token or any(c not in '0123456789abcdef-' for c in token.lower()):
                raise ExecutionUnavailable('Execution service did not return a valid submission token.')
            deadline = time.monotonic() + 45
            while True:
                result = await self._request(client,'GET',f'/submissions/{token}',params={
                    'base64_encoded':'true','fields':'stdout,stderr,compile_output,status,time,memory,exit_code'})
                status_data = result.get('status')
                if not isinstance(status_data,dict):
                    raise ExecutionUnavailable('Execution service returned an invalid status.')
                status = status_data.get('id')
                if status in (1,2):
                    if time.monotonic() >= deadline:
                        raise ExecutionUnavailable('Execution service queue timed out. Try again shortly.')
                    await asyncio.sleep(0.5)
                    continue
                if status == 13 or not isinstance(status,int) or status < 3 or status > 14:
                    raise ExecutionUnavailable('Execution service could not evaluate this run. Try again shortly.')
                break
            output = decoded(result.get('stdout'))
            error = decoded(result.get('stderr')) or decoded(result.get('compile_output'))
            verdict = {4:'Wrong answer',5:'Time limit exceeded',6:'Syntax error',8:'Output limit exceeded'}.get(status,'Runtime error')
            if status == 11 and re.search(r'(?:^|\n)(?:SyntaxError|IndentationError|TabError):',error):
                verdict = 'Syntax error'
            passed = None
            if status == 3:
                if 'expected_output' in case:
                    passed = output.split() == str(case['expected_output']).split()
                    verdict = 'Accepted' if passed else 'Wrong answer'
                else:
                    verdict = 'Executed'
            elif 'expected_output' in case:
                passed = False
            row = {'case':index,'verdict':verdict,'passed':passed,'time_seconds':result.get('time'),
                   'memory_kb':result.get('memory'),'hidden':case.get('hidden',False)}
            if not row['hidden']:
                row.update({'input':case['input'],'stdout':output[:8000],'error':error[:8000],
                            'expected_output':case.get('expected_output'),'output_truncated':len(output)>8000})
            return row

    async def evaluate(self,code,cases):
        semaphore = asyncio.Semaphore(3)
        async with httpx.AsyncClient(base_url=self.url,headers=self.headers,timeout=15,follow_redirects=False) as client:
            tasks = [asyncio.create_task(self._case(client,code,case,i,semaphore)) for i,case in enumerate(cases,1)]
            try:
                return await asyncio.wait_for(asyncio.gather(*tasks),timeout=90)
            except (Exception,asyncio.CancelledError) as error:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
                if isinstance(error,asyncio.TimeoutError):
                    raise ExecutionUnavailable('Execution took too long. Try again later.') from error
                raise
