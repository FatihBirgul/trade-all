"""Local preregistration and cross-run disclosure. Hash declarations are not external attestation."""
from dataclasses import asdict
from hashlib import sha256
from threading import RLock
from datetime import datetime,timezone
import json,re
from forex.contracts import canonical

VERSION='fx-preregistration-v9-1'


def prepare(dataset,config):
    from .engine import code_digest
    from market_ai.v2.walk_forward import plan_folds
    body={'version':VERSION,'dataset_digest':dataset.digest,
        'rules_sha256':sha256(canonical([dict(dataset.rules),dataset.rule_epochs]).encode()).hexdigest(),
        'costs_sha256':sha256(canonical([config.fee_bps,config.spread_bps,config.slippage_bps]).encode()).hexdigest(),
        'configuration':asdict(config),'code_sha256':code_digest(),
        'folds':plan_folds(len(dataset.frames[dataset.execution_timeframe]),config),
        'selection_criterion':'marked_net_change_then_lower_drawdown_then_candidate_id',
        'candidate_trials_per_fold':len(config.candidates)}
    raw=canonical(body)
    return {'body':json.loads(raw),'protocol_id':sha256(raw.encode()).hexdigest(),
        'registered_at':datetime.now(timezone.utc).isoformat(),
        'status':'LOCAL_DECLARATION_NOT_EXTERNAL_PREREGISTRATION','external_attestation':False}


def verify(registration,dataset,config):
    if not isinstance(registration,dict) or len(canonical(registration))>100000:raise ValueError('Bounded preregistration required')
    expected=prepare(dataset,config)
    if registration.get('body')!=expected['body'] or registration.get('protocol_id')!=expected['protocol_id']:raise ValueError('Frozen preregistration input/rules/cost/code mismatch')
    return expected['protocol_id']


class TrialRegistry:
    def __init__(self):self.campaigns={};self.lock=RLock()
    def declare(self,campaign,budget):
        if not isinstance(campaign,str) or not re.fullmatch(r'[a-zA-Z0-9_.-]{1,64}',campaign) or type(budget) is not int or not 1<=budget<=100:raise ValueError('Bounded campaign and budget required')
        with self.lock:
            if campaign in self.campaigns:
                if self.campaigns[campaign]['budget']!=budget:raise ValueError('Campaign budget already frozen')
            else:
                if len(self.campaigns)>=16:raise ValueError('Campaign capacity exceeded')
                self.campaigns[campaign]={'budget':budget,'attempts':[]}
    def begin(self,campaign,protocol_id):
        with self.lock:
            if campaign not in self.campaigns:raise ValueError('Campaign must be declared before execution')
            row=self.campaigns[campaign]
            if len(row['attempts'])>=row['budget']:raise ValueError('Preregistered cross-run trial budget exhausted')
            token=sha256(f'{campaign}|{len(row["attempts"])}|{protocol_id}'.encode()).hexdigest()
            row['attempts'].append({'token':token,'protocol_id':protocol_id,'status':'RUNNING'})
            return token
    def finish(self,token,status):
        if status not in ('COMPLETED','CANCELLED','FAILED'):raise ValueError('Invalid research outcome status')
        with self.lock:
            for campaign,row in self.campaigns.items():
                for attempt in row['attempts']:
                    if attempt['token']==token:
                        if attempt['status'] not in ('RUNNING',status):raise ValueError('Trial outcome already frozen')
                        attempt['status']=status
                        return self.export(campaign)
            raise ValueError('Unknown trial token')
    def export(self,campaign):
        with self.lock:
            row=self.campaigns[campaign]
            return json.loads(canonical({'campaign':campaign,**row,'independent_market_evidence':False,
                'scope':'bounded_process_memory; resets_on_restart; self-declared campaigns do not prevent undeclared external trials'}))
