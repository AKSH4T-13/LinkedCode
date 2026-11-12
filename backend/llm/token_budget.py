"""Bound Groq completion reservations without truncating code or correctness data."""
import math
import os
import re


class LLMBudgetExceeded(RuntimeError):
    pass


def invoke_budgeted(llm,prompt,phase,max_output_tokens=3500):
    try:
        limit=int(os.getenv('GROQ_TPM_LIMIT','8000'))
        if limit < 2048:
            raise ValueError()
    except ValueError as error:
        raise LLMBudgetExceeded('GROQ_TPM_LIMIT must be an integer of at least 2048.') from error
    # Conservative local estimate; server accounting remains authoritative.
    # Keep the entire prompt. Never cut Python source, constraints or test inputs.
    estimated_input=math.ceil(len(prompt.encode('utf-8'))/3)+128
    output=max(1024,min(max_output_tokens,limit-estimated_input-384))
    print(f'[LLM BUDGET] {phase}: estimated input {estimated_input} tokens; output reservation {output}.')
    for attempt in range(2):
        try:
            return llm.invoke(prompt,max_tokens=output)
        except Exception as error:
            status=getattr(error,'status_code',None)
            if status is None and getattr(error,'response',None) is not None:
                status=getattr(error.response,'status_code',None)
            text=str(error)
            match=re.search(r'Limit\s*:?\s*([\d,]+).*?Requested\s*:?\s*([\d,]+)',text,re.IGNORECASE|re.DOTALL)
            if status!=413 or match is None:
                raise
            server_limit,requested=(int(value.replace(',','')) for value in match.groups())
            smaller=output-max(requested-server_limit,0)-256
            if attempt or smaller<1024:
                raise LLMBudgetExceeded(
                    f'{phase}: Groq token budget could not fit this request. No result was saved. '
                    'Please retry later; this phase needs a smaller structured payload.'
                ) from error
            print(f'[LLM BUDGET] {phase}: reducing output reservation from {output} to {smaller} after 413.')
            output=smaller
