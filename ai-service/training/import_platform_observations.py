"""Import verified, patient-free PostgreSQL observations via the authenticated backend.

Run explicitly or before the controlled learning worker. Import never trains,
promotes, or overwrites a conflicting observation.
"""
import json
import os
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from corecare import storage
from corecare.schemas import DailySubmission, ReferralFeatures, OutcomeSubmission
from corecare.inference import validate_record_outcome


def import_records(kind, records):
    imported=0
    for item in records:
        if not item.get('verified_by') or not item.get('verified_at'):
            raise ValueError('Verified provenance is required.')
        if datetime.fromisoformat(item['verified_at'])>datetime.now(timezone.utc):
            raise ValueError('Future verification is invalid.')
        payload=item['payload']
        if kind=='daily':
            parsed=DailySubmission.model_validate({**payload,'record_type':'real','observed_at':item['verified_at'],'source_reference':'platform:'+item['id']}).model_dump(mode='json')
            with storage.connection() as db:
                prior=db.execute("SELECT record_id,payload,status FROM daily_operations WHERE hospital_id=? AND record_date=? AND record_type='real'",(parsed['hospital_id'],parsed['record_date'])).fetchone()
            if prior:
                if json.loads(prior['payload'])!=parsed:
                    raise ValueError('Conflicting daily record; resolve evidence before importing.')
                if prior['status']=='pending':
                    storage.verify_daily(prior['record_id'],item['verified_by'],'Verified platform observation '+item['id'])
                continue
            identifier=storage.save_daily(parsed)
            storage.verify_daily(identifier,item['verified_by'],'Verified platform observation '+item['id'])
        else:
            from corecare.config import DELAY_FEATURES
            ReferralFeatures.model_validate({k:payload[k] for k in DELAY_FEATURES})
            submitted=datetime.fromisoformat(payload['submitted_at'])
            observed=datetime.fromisoformat(payload['feature_observed_at'])
            if observed>submitted or (submitted-observed).total_seconds()>7200:
                raise ValueError('Referral feature timestamp is invalid.')
            parsed={**payload,'record_type':'real','source_reference':'platform:'+payload['source_reference']}
            acknowledged=datetime.fromisoformat(item['acknowledged_at'])
            outcome=OutcomeSubmission(actual_result=int((acknowledged-submitted).total_seconds()>7200),acknowledged_at=acknowledged,source_reference='platform:'+item['id'])
            validated=validate_record_outcome({'component':'delay','record_type':'real','inputs':parsed},outcome)
            with storage.connection() as db:
                prior=db.execute("SELECT * FROM referral_observations WHERE hospital_id=? AND source_reference=? AND record_type='real'",(parsed['hospital_id'],parsed['source_reference'])).fetchone()
            if prior:
                if json.loads(prior['inputs'])!=parsed:
                    raise ValueError('Conflicting referral observation.')
                if prior['outcome'] and json.loads(prior['outcome'])!=validated:
                    raise ValueError('Conflicting referral outcome.')
                if prior['status']=='awaiting_outcome':
                    storage.submit_referral_outcome(prior['observation_id'],validated)
                if prior['status']!='verified':
                    storage.verify_referral_observation(prior['observation_id'],item['verified_by'],'Verified platform referral '+item['id'])
                continue
            identifier=storage.save_referral_observation(parsed)
            storage.submit_referral_outcome(identifier,validated)
            storage.verify_referral_observation(identifier,item['verified_by'],'Verified platform referral '+item['id'])
        imported+=1
    return imported


def run_import():
    base=os.environ['PLATFORM_BACKEND_URL'].rstrip('/')
    key=os.environ['CORECARE_API_KEY']
    if not key:
        raise ValueError('Service key required.')
    storage.initialize()
    result={}
    for kind in ('daily','referrals'):
        cursor=None
        result[kind]=0
        while True:
            from urllib.parse import urlencode
            params={'kind':kind}
            if cursor:
                params['cursor']=cursor
            request=Request(base+'/internal/learning-export?'+urlencode(params),headers={'X-API-Key':key})
            with urlopen(request,timeout=20) as response:
                data=json.loads(response.read(4*1024*1024))
            result[kind]+=import_records(kind,data['records'])
            cursor=data['nextCursor']
            if not cursor:
                break
    return result


if __name__=='__main__':
    print(json.dumps(run_import()))
