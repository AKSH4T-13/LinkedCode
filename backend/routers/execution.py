"""Authenticated Python practice using server-owned question test cases."""
import time
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy.orm import Session
from backend.core.dependencies import get_current_user
from backend.database import get_db
from backend.models import User, GeneratedQuestion, CodeSubmission
from backend.services.python_runner import PythonRunner, ExecutionUnavailable
from backend.services.performance_judge import get_performance_cases

router = APIRouter(tags=['Python practice'])
active_users = set()
recent_runs = {}


class CodeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str = Field(min_length=1,max_length=40000)
    mode: Literal['examples','custom','submit'] = 'examples'
    stdin: str = Field(default='',max_length=20000)

    @field_validator('code')
    @classmethod
    def nonempty(cls,value):
        if not value.strip():
            raise ValueError('Write some Python code first.')
        return value


@router.post('/generated-questions/{question_id}/execute')
async def execute(question_id:int,body:CodeRequest,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    question = db.query(GeneratedQuestion).filter_by(id=question_id,user_id=user.id).first()
    if question is None:
        raise HTTPException(404,'Generated question not found.')
    if not (question.validation_report or {}).get('is_valid'):
        raise HTTPException(409,'This problem has not passed validation and cannot be judged.')
    now = time.monotonic()
    for key in list(recent_runs):
        if now - recent_runs[key] > 5:
            del recent_runs[key]
    if user.id in active_users:
        raise HTTPException(409,'A Python run is already in progress for your account.')
    if user.id in recent_runs:
        raise HTTPException(429,'Please wait five seconds between runs.',headers={'Retry-After':'5'})
    data = question.question_data
    if body.mode == 'custom':
        cases = [{'input':body.stdin}]
    elif body.mode == 'examples':
        cases = [{'input':case['input'],'expected_output':case['output']} for case in data.get('examples',[])]
    else:
        if not data.get('test_cases') or not data.get('verification_test_cases'):
            raise HTTPException(409,'This question has an incomplete test suite.')
        cases = [{'input':case['input'],'expected_output':case['expected_output'],'hidden':hidden}
                 for group,hidden in (('test_cases',False),('verification_test_cases',True)) for case in data.get(group,[])]
    if not cases or len(cases)>30:
        raise HTTPException(409,'This question does not have a supported test suite.')
    active_users.add(user.id)
    recent_runs[user.id] = now
    try:
        runner = PythonRunner()
        results = await runner.evaluate(body.code,cases)
        if len(results) != len(cases):
            raise ExecutionUnavailable('Execution service returned incomplete results. Please try again.')
        correctness_total = len(results)
        performance_status = 'not_requested'
        if body.mode == 'submit':
            performance_status = 'skipped_after_incorrect_answer'
            if all(row['passed'] is True for row in results):
                performance_cases = await get_performance_cases(question,db,runner)
                if not performance_cases:
                    raise ExecutionUnavailable('Performance suite is unavailable. Full submission could not be judged.')
                performance_results = await runner.evaluate(body.code,performance_cases)
                if len(performance_results) != len(performance_cases):
                    raise ExecutionUnavailable('Execution service returned incomplete performance results.')
                for index,row in enumerate(performance_results,correctness_total+1):
                    row['case'] = index
                    row['kind'] = 'performance'
                    row['hidden'] = True
                    for field in ('input','stdout','expected_output','error'):
                        row.pop(field,None)
                results.extend(performance_results)
                performance_status = 'passed' if all(row['passed'] is True for row in performance_results) else 'failed'
        passed = sum(row['passed'] is True for row in results)
        judged = body.mode != 'custom'
        accepted = judged and passed == len(results)
        verdict = ('Accepted' if accepted else next((row['verdict'] for row in results if row['passed'] is not True),'Not accepted')) if judged else results[0]['verdict']
        report = {'mode':body.mode,'verdict':verdict,'accepted':accepted,'passed':passed if judged else None,'total':len(results),'results':results,'correctness_total':correctness_total,'performance_status':performance_status}
        if body.mode == 'submit':
            record = CodeSubmission(user_id=user.id,question_id=question.id,code=body.code,verdict=verdict,passed=passed,total=len(results),report=report)
            db.add(record)
            try:
                db.commit()
                db.refresh(record)
            except Exception:
                db.rollback()
                raise
            report['submission_id'] = record.id
        return report
    except ExecutionUnavailable as error:
        raise HTTPException(503,str(error))
    finally:
        active_users.discard(user.id)


@router.get('/generated-questions/{question_id}/submissions')
def submissions(question_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if not db.query(GeneratedQuestion).filter_by(id=question_id,user_id=user.id).first():
        raise HTTPException(404,'Generated question not found.')
    rows = db.query(CodeSubmission).filter_by(question_id=question_id,user_id=user.id).order_by(CodeSubmission.id.desc()).limit(20).all()
    return {'submissions':[{'id':row.id,'verdict':row.verdict,'passed':row.passed,'total':row.total,'created_at':row.created_at.isoformat(),'performance_status':row.report.get('performance_status','not_checked')} for row in rows]}
