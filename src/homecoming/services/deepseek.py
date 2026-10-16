import asyncio
import json
from pathlib import Path
import httpx
from pydantic import ValidationError

from homecoming.schemas import ExtractedProfile, Overview
from homecoming.settings import DEEPSEEK_BASE, MODEL

PROMPTS = Path(__file__).resolve().parents[1] / 'prompts'


class ProviderError(ValueError):
    pass


def checked(response):
    if response.status_code in (401,403):
        raise ProviderError('DeepSeek rejected this API key. Check the key in Connection settings.')
    if response.status_code == 402:
        raise ProviderError('The DeepSeek account has insufficient balance.')
    if response.status_code == 429:
        raise ProviderError('DeepSeek is busy or rate limited. Please retry shortly.')
    if response.status_code >= 400:
        raise ProviderError('DeepSeek could not process the request (HTTP {}). Try again or use manual input.'.format(response.status_code))
    try:
        return response.json()
    except ValueError:
        raise ProviderError('DeepSeek returned an unreadable response. Please retry.')


async def validate_key(key):
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            result = checked(await client.get(DEEPSEEK_BASE+'/models',headers={'Authorization':'Bearer '+key}))
    except httpx.HTTPError:
        raise ProviderError('Could not reach DeepSeek. Check your internet connection and try again.')
    models = [r.get('id') for r in result.get('data',[])]
    if MODEL not in models:
        raise ProviderError('This account does not list the configured DeepSeek vision model ({}). Check model availability before using extraction.'.format(MODEL))
    return dict(connected=True,model=MODEL)


async def chat(key,prompt,content,schema):
    messages = [dict(role='system',content=(PROMPTS/prompt).read_text()+'\nJSON schema:\n'+json.dumps(schema.model_json_schema())),
                dict(role='user',content=content)]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(150,connect=20)) as client:
            response = await client.post(DEEPSEEK_BASE+'/chat/completions',
                headers={'Authorization':'Bearer '+key},
                json=dict(model=MODEL,messages=messages,response_format={'type':'json_object'},
                          max_tokens=3500,temperature=0.1,thinking={'type':'disabled'}))
            result = checked(response)
    except httpx.HTTPError:
        raise ProviderError('The DeepSeek request timed out or lost its connection. Please retry; manual input remains available.')
    try:
        choice = result['choices'][0]
        if choice.get('finish_reason') == 'length':
            raise ProviderError('DeepSeek returned an incomplete response. Please retry with fewer pages.')
        return schema.model_validate_json(choice['message']['content'])
    except (KeyError,IndexError,TypeError,ValidationError):
        raise ProviderError('DeepSeek returned fields that could not be validated. Please retry or fill the form manually.')


def extract(key,content):
    profile = asyncio.run(chat(key,'extraction.txt',content,ExtractedProfile))
    if any(1 in member.disability_codes for member in profile.household):
        profile.wheelchair_required = True
    return profile.model_dump()


def overview(key,result,parameters):
    rows = result['estates']
    top = [r for r in rows if r['ranking_status']=='complete'][:3]
    # Identity and other personal information are deliberately absent.
    profile = parameters.model_dump(exclude={'applicant_name','household_size'})
    if parameters.hospital_id:
        from homecoming.services.data import catalog
        profile['preferred_hospital_name'] = catalog()['entities'][parameters.hospital_id]['name']
    fields = ['id','name_en','rank','ranking_status','final_cost','bus_time_s','mtr_time_s',
              'hospital_distance_m','bus_scaled_cost','mtr_scaled_cost','hospital_scaled_cost',
              'missing_components','bus_warnings','mtr_warnings','hospital_warnings']
    payload = dict(parameters=profile,policy=result['policy'],top_three_ids=[r['id'] for r in top],
                   estates=[{k:r[k] for k in fields} for r in rows])
    response = asyncio.run(chat(key,'overview.txt',json.dumps(payload),Overview))
    if [r.estate_id for r in response.top_three] != payload['top_three_ids']:
        raise ProviderError('The AI explanation did not match the computed top estates. Retry the overview; the ranking is unchanged.')
    return response.model_dump()
