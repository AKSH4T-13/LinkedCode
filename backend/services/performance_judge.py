"""Build and cache maximum-constraint judge cases, calibrated on Judge0 itself."""
import hashlib
import json
import re
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from backend.models import QuestionPerformanceSuite
from backend.services.python_runner import ExecutionUnavailable
from backend.services.stress_test_generator import generate_stress_tests

SUITE_VERSION = 'maximum-inputs-v1'


def build_performance_inputs(question):
    spec=question.get('stress_test_spec')
    if not isinstance(spec,dict):
        raise ExecutionUnavailable('This problem has no performance specification. Run examples is available, but full submission needs a regenerated validated problem.')
    maximum=spec.get('parameters',{}).get('n_max')
    if isinstance(maximum,bool) or not isinstance(maximum,int) or not 1 <= maximum <= 200000:
        raise ExecutionUnavailable('This problem exceeds the configured performance-judge input size. Run examples is still available.')
    try:
        generated=generate_stress_tests(spec,count=9,seed=42)
    except (ValueError,KeyError,TypeError) as error:
        raise ExecutionUnavailable('This problem has an unsupported performance specification.') from error
    # Preserve ordering requirements declared in the input contract. A sorted
    # linked-list problem must not be judged using an unsorted random array.
    contract = str(question.get('input_format','')) + ' ' + ' '.join(question.get('constraints',[]))
    contract = re.sub(r'[\u2010-\u2015]', '-', contract.lower()).replace('*','')
    descending = bool(re.search(r'non[- ]?increasing|descending order|sorted in descending',contract))
    ascending = bool(re.search(r'non[- ]?decreasing|ascending order|sorted in ascending|sorted array|sorted list',contract))
    selected=[];seen=set()
    for category in ('reverse_sorted_array','duplicate_heavy','maximum_random'):
        case=next((case for case in generated if case.get('category')==category),None)
        if case is None:
            raise ExecutionUnavailable('Could not build the required performance cases.')
        if ascending or descending:
            tokens=case['input'].split()
            header=2 if spec['generator_type']=='array_n_k' else 1
            values=sorted(map(int,tokens[header:]),reverse=descending)
            case=dict(case,input=' '.join(tokens[:header])+'\n'+' '.join(map(str,values)))
        if case['input'] not in seen:
            seen.add(case['input'])
            selected.append({'input':case['input'],'hidden':False,'kind':'performance'})
    return selected


async def get_performance_cases(question,db,runner):
    data=question.question_data
    signature=hashlib.sha256(json.dumps({
        'version':SUITE_VERSION,'spec':data.get('stress_test_spec'),
        'reference':data.get('reference_solution'),'input_contract':data.get('input_format'),
        'constraints':data.get('constraints'),'provider':runner.url,
        'language':runner.language_id,'cpu':3,'wall':8,'memory':131072,
    },sort_keys=True,separators=(',',':')).encode()).hexdigest()
    cached=db.get(QuestionPerformanceSuite,question.id)
    if cached and cached.signature==signature:
        return cached.cases
    reference=data.get('reference_solution')
    if not isinstance(reference,str) or not reference.strip():
        raise ExecutionUnavailable('This problem has no reference solution for performance calibration.')
    inputs=build_performance_inputs(data)
    # Calibrate on the same runtime, memory and CPU limits as the learner.
    # A slow/broken reference must never cause a learner to be marked wrong.
    results=await runner.evaluate(reference,inputs)
    if len(results)!=len(inputs) or any(row.get('verdict')!='Executed' or row.get('output_truncated') for row in results):
        raise ExecutionUnavailable('The reference solution could not pass the performance judge. This problem needs review; your submission has not been marked wrong.')
    cases=[{'input':case['input'],'expected_output':row['stdout'],'hidden':True,'kind':'performance'}
           for case,row in zip(inputs,results)]
    if cached is None:
        cached=QuestionPerformanceSuite(question_id=question.id,signature=signature,cases=cases)
        db.add(cached)
    else:
        cached.signature=signature;cached.cases=cases;cached.created_at=datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing=db.get(QuestionPerformanceSuite,question.id)
        if not existing or existing.signature!=signature:
            raise ExecutionUnavailable('Performance suite changed. Please try again.')
        return existing.cases
    return cases
