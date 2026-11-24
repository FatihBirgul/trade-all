"""Independent historical scope/security oracles; all schedules are synthetic."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from forex.contracts import _bars, capture
from forex.core import DataError
from forex.historical_sessions import (MAX_BYTES, MAX_INTERVALS, HistoricalEvidenceStore,
                                       SourceReview, load_historical_evidence,
                                       local_to_utc, main, parse_historical_evidence, utc,
                                       configured_historical_store)
from forex.providers import MT5Provider
from forex.sessions import broker_status
from historical_fixture import (NOW, ORIGINAL, document, evaluate, trusted_store,
                                 window, write_candidate)
from test_exness_session_gap import rows_after_break, stamp
from test_real_readonly import RealTerminal


class HistoricalImport(unittest.TestCase):
    def parse(self, doc):
        return parse_historical_evidence(json.dumps(doc).encode(), now=NOW)

    def test_format_and_self_asserted_approval_never_authorize(self):
        with TemporaryDirectory() as folder:
            for status in ('FORMAT_VALIDATED', 'HISTORICAL_SOURCE_VERIFIED', 'OPERATOR_DECLARED'):
                doc = document(); doc.update(verification_status=status, operator_review='APPROVED')
                candidate = write_candidate(folder, doc)
                policy = evaluate(HistoricalEvidenceStore([candidate]))
                self.assertFalse(policy.summary()['historical_gap_authorized'])
                self.assertEqual(policy.summary()['status'], 'OPERATOR_DECLARED' if
                                 status == 'OPERATOR_DECLARED' else 'FORMAT_VALIDATED')

    def test_missing_source(self):
        doc = document(); del doc['source']
        with self.assertRaises(DataError): self.parse(doc)

    def test_exact_cent_symbols(self):
        for canonical in ('XAUUSD', 'EURUSD'):
            doc = document(canonical); doc['broker_symbol'] = canonical
            with self.subTest(canonical=canonical), self.assertRaisesRegex(DataError, 'symbol'):
                self.parse(doc)

    def test_unknown_fields_and_verified_switch(self):
        for key in ('verified', 'historical_gap_authorized', 'login', 'approval_token'):
            doc = document(); doc[key] = True
            with self.subTest(key=key), self.assertRaises(DataError): self.parse(doc)

    def test_duplicate_json_keys(self):
        with self.assertRaises(DataError):
            parse_historical_evidence(b'{"source":1,"source":2}', now=NOW)

    def test_bad_json_encoding_constants_and_recursion(self):
        for raw in (b'\xff', b'{', b'{"source":NaN}', b'['*1100+b']'*1100):
            with self.subTest(raw=raw[:20]), self.assertRaises(DataError):
                parse_historical_evidence(raw, now=NOW)

    def test_size_limit(self):
        with self.assertRaises(DataError): parse_historical_evidence(b' '* (MAX_BYTES+1))

    def test_interval_budget(self):
        doc=document(); doc['quote_open'] *= MAX_INTERVALS
        with self.assertRaises(DataError): self.parse(doc)

    def test_malformed_dates_and_naive_time(self):
        for value in ('2026-11-31T00:00:00Z', '2026-11-09T00:00:00',
                      '2026-11-09T00:00:00+03:00', True):
            doc=document(); doc['effective_start_utc']=value
            with self.subTest(value=value), self.assertRaises(DataError): self.parse(doc)

    def test_empty_and_reversed_intervals(self):
        for end in ('2026-11-09T22:00:00Z', '2026-11-09T21:00:00Z'):
            doc=document(); doc['maintenance']=[window('2026-11-09T22:00:00Z', end)]
            with self.assertRaises(DataError): self.parse(doc)

    def test_duplicate_and_overlapping_intervals(self):
        for extra in (window('2026-11-09T22:00:00Z', '2026-11-09T23:00:30Z'),
                      window('2026-11-09T22:30:00Z', '2026-11-09T23:00:30Z')):
            doc=document(); doc['maintenance'].append(extra)
            with self.assertRaises(DataError): self.parse(doc)

    def test_quote_closed_claim_conflicts_with_quotes(self):
        doc=document(); doc['holidays']=[window('2026-11-09T12:00:00Z', '2026-11-09T13:00:00Z')]
        with self.assertRaises(DataError): self.parse(doc)

    def test_trade_and_close_only_overlap(self):
        doc=document(); doc['trade_open'].append(window('2026-11-09T23:01:00Z', '2026-11-09T23:02:00Z'))
        with self.assertRaises(DataError): self.parse(doc)

    def test_trade_open_cannot_overlap_proven_quote_closed(self):
        doc=document()
        doc['trade_open'].append(window('2026-11-09T22:30:00Z','2026-11-09T22:45:00Z'))
        with self.assertRaisesRegex(DataError,'quote availability'): self.parse(doc)

    def test_unknown_timezone(self):
        doc=document(); doc['source_timezone']='Not/A_Zone'
        with self.assertRaises(DataError): self.parse(doc)

    def test_dst_offset_mismatch(self):
        doc=document(); doc['dst_regime'][0]['offset_seconds']=3600
        with self.assertRaisesRegex(DataError, 'DST'): self.parse(doc)

    def test_dst_effective_scope_missing(self):
        doc=document(); doc['dst_regime'][0]['end_utc']='2026-11-11T00:00:00Z'
        with self.assertRaisesRegex(DataError, 'DST'): self.parse(doc)

    def test_dst_fall_conversion_and_explicit_fold(self):
        with self.assertRaisesRegex(DataError, 'ambiguous'):
            local_to_utc('2026-11-01T01:30:00', 'America/New_York')
        first=local_to_utc('2026-11-01T01:30:00', 'America/New_York', fold=0)
        second=local_to_utc('2026-11-01T01:30:00', 'America/New_York', fold=1)
        self.assertEqual(first.isoformat(), '2026-11-01T05:30:00+00:00')
        self.assertEqual((second-first).total_seconds(), 3600)

    def test_dst_spring_nonexistent(self):
        with self.assertRaisesRegex(DataError, 'nonexistent'):
            local_to_utc('2026-03-08T02:30:00', 'America/New_York')

    def test_utc_normalization_overnight(self):
        result=local_to_utc('2026-11-10T01:00:00', 'Europe/Istanbul')
        self.assertEqual(result.isoformat(), '2026-11-09T22:00:00+00:00')

    def test_correct_dated_dst_regimes_across_fall_transition(self):
        doc=document()
        doc.update(effective_start_utc='2026-11-01T00:00:00Z',effective_end_utc='2026-11-02T00:00:00Z',
                   source_timezone='America/New_York')
        doc['coverage']=[window(doc['effective_start_utc'],doc['effective_end_utc'])]
        for key in ('quote_open','trade_open','close_only','maintenance','weekend_closed','holidays','exceptional_closures'):
            doc[key]=[]
        doc['dst_regime']=[{**window('2026-11-01T00:00:00Z','2026-11-01T06:00:00Z'),'offset_seconds':-14400},
                           {**window('2026-11-01T06:00:00Z','2026-11-02T00:00:00Z'),'offset_seconds':-18000}]
        self.parse(doc)
        doc['dst_regime'][0]['end_utc']='2026-11-01T07:00:00Z'
        with self.assertRaisesRegex(DataError,'DST'): self.parse(doc)

    def test_original_hash_is_computed(self):
        with TemporaryDirectory() as folder:
            candidate=write_candidate(folder)
            self.assertTrue(candidate.original_checked)
            (Path(folder)/'original.txt').write_bytes(b'changed')
            with self.assertRaisesRegex(DataError, 'hash mismatch'):
                load_historical_evidence(folder, 'evidence.json', now=NOW)

    def test_committed_synthetic_fixture_is_hash_valid_and_never_approved(self):
        root=Path(__file__).resolve().parent/'fixtures'/'historical'
        candidate=load_historical_evidence(root,'synthetic.json',now=NOW)
        self.assertTrue(candidate.original_checked)
        self.assertFalse(evaluate(HistoricalEvidenceStore([candidate])).records)

    def test_invalid_hash_format(self):
        doc=document(); doc['source']['original_sha256']='not-a-hash'
        with self.assertRaises(DataError): self.parse(doc)

    def test_future_acquisition_and_publication_order(self):
        for key,value in (('acquired_at_utc','2026-11-12T00:00:00Z'),
                          ('published_at_utc','2026-11-06T00:00:00Z')):
            doc=document(); doc[key]=value
            with self.assertRaises(DataError): self.parse(doc)

    def test_path_traversal_absolute_ads_and_missing(self):
        with TemporaryDirectory() as folder:
            write_candidate(folder)
            for name in ('../evidence.json', str(Path(folder)/'evidence.json'),
                         'original.txt:stream', 'absent.json'):
                with self.subTest(name=name), self.assertRaises(DataError) as error:
                    load_historical_evidence(folder, name, now=NOW)
                self.assertNotIn(folder, str(error.exception))

    def test_original_path_escape(self):
        with TemporaryDirectory() as folder:
            doc=document(); doc['source']['original_file']='../secret.txt'
            with self.assertRaises(DataError): write_candidate(folder, doc)

    def test_hardlink_input_refused(self):
        import os
        with TemporaryDirectory() as folder:
            write_candidate(folder)
            os.link(Path(folder)/'original.txt',Path(folder)/'linked.txt')
            with self.assertRaises(DataError): load_historical_evidence(folder,'evidence.json',now=NOW)

    def test_config_file_selection_cannot_inject_approvals(self):
        with TemporaryDirectory() as folder:
            write_candidate(folder)
            with patch.dict('os.environ',{'MT5_HISTORICAL_EVIDENCE_ROOT':folder,
                                         'MT5_HISTORICAL_EVIDENCE_FILES':'["evidence.json"]'}):
                self.assertFalse(evaluate(configured_historical_store()).records)
            for raw in ('{}','["evidence.json","evidence.json"]','[true]','['):
                with patch.dict('os.environ',{'MT5_HISTORICAL_EVIDENCE_ROOT':folder,
                                             'MT5_HISTORICAL_EVIDENCE_FILES':raw}), self.assertRaises(DataError):
                    configured_historical_store()

    def test_symlink_escape_refused(self):
        # Real symlink creation may require Windows privilege. The same native
        # lstat reparse-bit result is injected independently on all platforms.
        with TemporaryDirectory() as folder:
            write_candidate(folder)
            real_lstat=Path.lstat
            def reparse(path, *args, **kwargs):
                result=real_lstat(path, *args, **kwargs)
                if path.name == 'original.txt':
                    from types import SimpleNamespace
                    return SimpleNamespace(st_mode=result.st_mode, st_file_attributes=0x400,
                                           st_size=result.st_size)
                return result
            with patch.object(Path, 'lstat', reparse), self.assertRaises(DataError):
                load_historical_evidence(folder, 'evidence.json', now=NOW)


class HistoricalAuthorization(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store=trusted_store(self.temp.name)
        self.policy=evaluate(self.store)

    def test_trusted_dependency_injection(self):
        self.assertTrue(self.policy.summary()['historical_gap_authorized'])
        self.assertEqual(self.policy.summary()['status'], 'HISTORICAL_SOURCE_VERIFIED')

    def test_wrong_broker_server_product_currency_and_symbol(self):
        for change in ({'broker':'Other'}, {'server':'Other'}, {'product':'Standard'},
                       {'currency':'USD'}, {'broker_symbol':'XAUUSD'},
                       {'broker_symbol':'EURUSDc','canonical_symbol':'EURUSD'}):
            with self.subTest(change=change):
                self.assertFalse(evaluate(self.store, **change).summary()['historical_gap_authorized'])

    def test_four_exact_symbols_supported_independently(self):
        for symbol in ('XAUUSD','EURUSD','GBPUSD','USDJPY'):
            store=trusted_store(self.temp.name, document(symbol))
            self.assertTrue(evaluate(store, canonical_symbol=symbol, broker_symbol=symbol+'c').records)

    def test_current_weekly_and_operator_never_authorize(self):
        for kind in ('CURRENT_WEEKLY_ONLY', 'OPERATOR_DECLARED'):
            doc=document(); doc['source']['kind']=kind
            store=trusted_store(self.temp.name,doc)
            self.assertFalse(evaluate(store).records)
            self.assertEqual(evaluate(store).summary()['status'],kind)

    def test_rejected_or_conflicting_declaration_blocks(self):
        for state in ('REJECTED', 'CONFLICTING_EVIDENCE'):
            doc=document(); doc['verification_status']=state
            self.assertFalse(evaluate(trusted_store(self.temp.name,doc)).records)

    def test_missing_calendar_quote_timezone_fails_closed(self):
        for key in ('quote','calendar','timezone'):
            doc=document(); doc['completeness'][key]='INCOMPLETE'
            self.assertFalse(evaluate(trusted_store(self.temp.name,doc)).records)

    def test_missing_trade_scope_cannot_allow_new_position(self):
        doc=document(); doc['completeness']['trade']='INCOMPLETE'
        policy=evaluate(trusted_store(self.temp.name,doc))
        self.assertTrue(policy.records)
        self.assertEqual(broker_status(datetime(2026,11,10,1,tzinfo=timezone.utc),
                                      'XAUUSD',True,policy.trade_hours())['status'],'UNKNOWN')

    def test_trade_only_cannot_invent_quote_closure(self):
        doc=document(); doc['quote_open']=[]; doc['completeness']['quote']='INCOMPLETE'
        self.assertFalse(evaluate(trusted_store(self.temp.name,doc)).records)

    def test_coverage_boundary_and_weekend(self):
        self.assertTrue(self.policy.quote_closed(stamp(7,0),stamp(8,23)))
        self.assertFalse(self.policy.quote_closed(stamp(5,23),stamp(6,0)))
        self.assertFalse(self.policy.quote_closed(stamp(11,22),stamp(12,1)))
        self.assertFalse(self.policy.quote_closed(stamp(9,21,59),stamp(9,23)))

    def test_future_closed_interval_is_not_historical_market_data(self):
        self.assertFalse(self.policy.quote_closed(stamp(11,22),stamp(11,23)))

    def test_close_only_is_quote_open_new_position_disabled(self):
        start=utc('2026-11-09T23:00:30Z'); end=utc('2026-11-09T23:02:00Z')
        self.assertFalse(self.policy.quote_closed(start,end))
        self.assertTrue(self.policy.quote_present(start,end))
        at=datetime(2026,11,9,23,1,tzinfo=timezone.utc)
        self.assertEqual(broker_status(at,'XAUUSD',True,self.policy.trade_hours())['status'],'DISABLED')
        at=at.replace(minute=2)
        self.assertEqual(broker_status(at,'XAUUSD',True,self.policy.trade_hours())['status'],'OPEN')

    def test_changed_file_invalidates_review_pin(self):
        doc=document(); doc['source']['reference']='SYNTHETIC_TEST_EVIDENCE: modified reference'
        altered=write_candidate(self.temp.name,doc)
        self.assertFalse(evaluate(HistoricalEvidenceStore([altered],reviews=self.store.reviews)).records)

    def test_hash_without_original_check_does_not_authorize(self):
        candidate=self.store.candidates[0]
        raw=json.dumps(candidate.document(),sort_keys=True).encode()
        untrusted=parse_historical_evidence(raw,now=NOW)
        pin=SourceReview(untrusted.sha256,untrusted.document()['source']['original_sha256'],
                         '2026-11-05T02:00:00Z','synthetic')
        self.assertFalse(evaluate(HistoricalEvidenceStore([untrusted],reviews=[pin])).records)

    def test_overlapping_sources_require_reconciliation(self):
        store=HistoricalEvidenceStore(self.store.candidates*2,reviews=self.store.reviews)
        self.assertEqual(evaluate(store).summary()['status'],'CONFLICTING_EVIDENCE')
        self.assertFalse(evaluate(store).records)

    def test_disagreeing_unreviewed_source_also_blocks(self):
        doc=document(); doc['evidence_id']='SYNTHETIC_TEST_EVIDENCE-disagreement'
        doc['quote_open'][0]['end_utc']='2026-11-06T21:00:00Z'
        doc['trade_open'][0]['end_utc']='2026-11-06T21:00:00Z'
        other=write_candidate(self.temp.name,doc,name='other.json')
        store=HistoricalEvidenceStore((*self.store.candidates,other),reviews=self.store.reviews)
        self.assertEqual(evaluate(store).summary()['status'],'CONFLICTING_EVIDENCE')

    def test_disjoint_date_sources_do_not_extend_over_unknown_days(self):
        candidates, reviews = [], []
        for day in (9,11):
            doc=document(); a=f'2026-11-{day:02d}T00:00:00Z'; b=f'2026-11-{day+1:02d}T00:00:00Z'
            doc['coverage']=[window(a,b)]
            for kind in ('quote_open','trade_open','close_only','maintenance','weekend_closed','holidays','exceptional_closures'):
                doc[kind]=[w for w in doc[kind] if a<=w['start_utc']<w['end_utc']<=b]
            store=trusted_store(self.temp.name,doc)
            candidates.extend(store.candidates); reviews.extend(store.reviews)
        policy=evaluate(HistoricalEvidenceStore(candidates,reviews=reviews))
        self.assertTrue(policy.quote_closed(stamp(9,22),stamp(9,23)))
        self.assertFalse(policy.quote_closed(stamp(10,22),stamp(10,23)))

    def test_synthetic_cannot_be_enabled_by_production_registry(self):
        with patch('forex.historical_sessions.PRODUCTION_REVIEWS',self.store.reviews):
            self.assertFalse(evaluate(HistoricalEvidenceStore(self.store.candidates)).records)

    def test_holiday_and_exceptional_full_closures_are_dated(self):
        for kind in ('holidays','exceptional_closures'):
            doc=document(); a='2026-11-09T00:00:00Z'; b='2026-11-10T00:00:00Z'
            for field in ('quote_open','trade_open','close_only','maintenance'):
                doc[field]=[w for w in doc[field] if w['end_utc']<=a or w['start_utc']>=b]
            doc[kind]=[window(a,b)]
            policy=evaluate(trusted_store(self.temp.name,doc))
            self.assertTrue(policy.quote_closed(stamp(9,0),stamp(10,0)))
            self.assertFalse(policy.quote_closed(stamp(10,0),stamp(10,1)))

    def test_later_document_only_retrospective_not_old_live_decision(self):
        doc=document(); doc['published_at_utc']='2026-11-11T00:00:00Z'
        doc['acquired_at_utc']='2026-11-11T01:00:00Z'
        store=trusted_store(self.temp.name,doc)
        self.assertFalse(evaluate(store).records)
        self.assertTrue(evaluate(store,knowledge_as_of=NOW.timestamp(),retrospective=True).records)
        with self.assertRaisesRegex(DataError,'look-ahead'):
            evaluate(store,knowledge_as_of=NOW.timestamp())

    def test_review_itself_must_be_known_at_decision(self):
        old=self.store.reviews[0]
        review=SourceReview(old.evidence_sha256,old.original_sha256,'2026-11-11T01:00:00Z','synthetic')
        self.assertFalse(evaluate(HistoricalEvidenceStore(self.store.candidates,reviews=[review])).records)

    def test_no_evidence_status(self):
        self.assertEqual(evaluate(HistoricalEvidenceStore()).summary()['status'],'SOURCE_NOT_SUPPLIED')

    def test_cli_is_readonly_and_does_not_approve(self):
        before={p.name:p.read_bytes() for p in Path(self.temp.name).iterdir()}
        from io import StringIO
        with patch('sys.stdout',new_callable=StringIO) as output:
            code=main(['--root',self.temp.name,'--file','evidence.json','--symbol','XAUUSD',
                       '--as-of','2026-11-10T04:00:00Z','--gap-start','2026-11-09T22:00:00Z',
                       '--gap-end','2026-11-09T23:00:00Z'])
        self.assertEqual(code,3)
        result=json.loads(output.getvalue())
        self.assertEqual(result['external_status'],'BLOCKED_BY_EXTERNAL_EVIDENCE')
        self.assertFalse(result['gap']['quote_closed'])
        self.assertEqual(before,{p.name:p.read_bytes() for p in Path(self.temp.name).iterdir()})


class HistoricalBuckets(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.policy=evaluate(trusted_store(self.temp.name))

    def rows(self, tf):
        seconds={'M5':300,'M15':900}[tf]
        previous=stamp(9,22)-seconds
        times=[previous-(199-i)*seconds for i in range(200)]
        times += [stamp(9,23)+i*seconds for i in range(20)]
        return [dict(time=t,open=100,high=101,low=99,close=100,tick_volume=1) for t in times]

    def check(self,rows,tf='M15',as_of=None,policy=None):
        seconds={'M5':300,'M15':900}[tf]
        return _bars(rows,tf,as_of or rows[-1]['time']+seconds,
                     {'source':'fixture','broker_contract_required':True},'XAUUSD','fixture',
                     historical=policy or self.policy)

    def test_fully_closed_missing_m5(self):
        rows=self.rows('M5'); self.assertEqual(len(self.check(rows,'M5')),220)

    def test_fully_closed_missing_m15_and_positive_tick_bucket(self):
        rows=self.rows('M15'); parsed=self.check(rows)
        self.assertEqual(len(parsed),220)
        self.assertEqual(parsed[200]['open_time_utc'],stamp(9,23))
        self.assertEqual(parsed[200]['close_time_utc'],stamp(9,23,15))
        self.assertEqual(parsed[200]['volume_kind'],'tick')

    def test_partial_quote_open_missing_m5_or_m15(self):
        for tf in ('M5','M15'):
            rows=self.rows(tf); rows.pop(200)
            with self.subTest(tf=tf), self.assertRaisesRegex(DataError,'missing candle'):
                self.check(rows,tf)

    def test_open_session_gap(self):
        rows=self.rows('M15'); rows.pop(210)
        with self.assertRaisesRegex(DataError,'missing candle'): self.check(rows)

    def test_unfinished_m15_at_real_observation_times(self):
        rows=self.rows('M15')[:201]
        for value in ('2026-11-09T23:00:30Z','2026-11-09T23:01:00Z','2026-11-09T23:02:00Z'):
            with self.subTest(value=value), self.assertRaisesRegex(DataError,'closed'):
                self.check(rows,as_of=utc(value))
        self.assertEqual(len(self.check(rows,as_of=stamp(9,23,15))),201)

    def test_positive_tick_is_required_for_delayed_quote_open(self):
        rows=self.rows('M15'); rows[200]['tick_volume']=0
        with self.assertRaisesRegex(DataError,'outside verified'): self.check(rows)

    def test_real_volume_still_rejected(self):
        rows=self.rows('M15'); rows[200]['volume_kind']='real'
        with self.assertRaisesRegex(DataError,'real volume'): self.check(rows)

    def test_stale_and_future_candles_still_rejected(self):
        rows=self.rows('M15')
        with self.assertRaisesRegex(DataError,'stale'): self.check(rows,as_of=rows[-1]['time']+3600)
        with self.assertRaisesRegex(DataError,'closed'): self.check(rows,as_of=rows[-1]['time'])

    def test_real_metadata_cannot_self_authorize(self):
        rows=self.rows('M15')
        meta={'source':'fixture','broker_contract_required':True,'historical_gap_authorized':True,
              'quote_hours':{'timezone':'UTC','weekly':{str(i):[] for i in range(7)}}}
        with self.assertRaisesRegex(DataError,'without verified'):
            _bars(rows,'M15',rows[-1]['time']+900,meta,'XAUUSD','fixture')

    def test_partial_date_scope_explains_only_covered_gap(self):
        doc=document()
        # Keep explicit coverage through Nov 10, then remove all intervals
        # outside it. The original effective period remains deliberately wider.
        cutoff='2026-11-10T00:00:00Z'
        doc['coverage']=[window('2026-11-06T00:00:00Z',cutoff)]
        for kind in ('quote_open','trade_open','close_only','maintenance','weekend_closed','holidays','exceptional_closures'):
            doc[kind]=[w for w in doc[kind] if w['end_utc']<=cutoff]
        policy=evaluate(trusted_store(self.temp.name,doc))
        self.assertEqual(len(self.check(self.rows('M15'),policy=policy)),220)
        later=[{**r,'time':r['time']+86400} for r in self.rows('M15')]
        with self.assertRaisesRegex(DataError,'missing candle'): self.check(later,policy=policy)

    def test_provider_binds_only_exact_reviewed_scope_and_preserves_real_metadata(self):
        store=trusted_store(self.temp.name)
        provider=MT5Provider(RealTerminal(),{'XAUUSD':'XAUUSDc'},historical_evidence=store)
        provider.account_preflight('REAL_READONLY_DATA','Real-Server','USC')
        policy=provider.historical_session_policy('XAUUSD',stamp(10,4))
        self.assertFalse(policy.records)  # Real-Server is not Exness-MT5Real50.
        meta=provider.metadata('XAUUSD')
        self.assertIsNone(meta['broker_hours'])
        self.assertIsNone(meta['max_spread'])
        self.assertEqual(meta['account_currency'],'USC')
        self.assertEqual(provider.mt5.mutations,[])


if __name__=='__main__':
    unittest.main()
