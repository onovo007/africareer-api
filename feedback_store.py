"""Idempotent, acknowledged feedback storage using the existing Supabase project."""
import httpx

def save_feedback(base_url, key, payload):
    if not base_url or not key:
        return False
    headers={'apikey':key,'Authorization':f'Bearer {key}'}
    try:
        with httpx.Client(timeout=8) as client:
            response=client.post(base_url+'/rest/v1/pilot_feedback',headers={**headers,
                'Prefer':'resolution=ignore-duplicates,return=minimal'},
                params={'on_conflict':'request_id'},json=payload)
            if response.status_code>=300:
                return False
            check=client.get(base_url+'/rest/v1/pilot_feedback',headers=headers,
                params={'request_id':'eq.'+payload['request_id'],'select':','.join(payload),'limit':'1'})
            rows=check.json() if check.status_code==200 else []
            return len(rows)==1 and all(rows[0].get(k)==v for k,v in payload.items())
    except (httpx.HTTPError,ValueError,TypeError,KeyError):
        return False
