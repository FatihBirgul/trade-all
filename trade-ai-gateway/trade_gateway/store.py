import hashlib
import json
import secrets
import sqlite3
import time
import uuid
from pathlib import Path


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class AuthStore:
    def __init__(self, path: Path, clock=time.time):
        self.path, self.clock = Path(path), clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS pairings(hash TEXT PRIMARY KEY, expires REAL, scopes TEXT, accounts TEXT);
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, hash TEXT UNIQUE, device_id TEXT,
              name TEXT, expires REAL, revoked INTEGER DEFAULT 0, scopes TEXT, accounts TEXT);
            CREATE TABLE IF NOT EXISTS limits(key TEXT PRIMARY KEY, bucket INTEGER, count INTEGER);
            CREATE TABLE IF NOT EXISTS renewal_families(id TEXT PRIMARY KEY, device_id TEXT, name TEXT,
              expires REAL, scopes TEXT, accounts TEXT, active_hash TEXT, revoked INTEGER);
            CREATE TABLE IF NOT EXISTS renewal_tokens(hash TEXT PRIMARY KEY, family_id TEXT, used INTEGER,
              request_hash TEXT, next_hash TEXT, access_sid TEXT);
            CREATE TABLE IF NOT EXISTS renewal_sessions(family_id TEXT, sid TEXT PRIMARY KEY);
            ''')
        self.path.chmod(0o600)

    def connect(self):
        c = sqlite3.connect(self.path, timeout=5)
        c.row_factory = sqlite3.Row
        return c

    def pairing(self, *, accounts=("AUTO", "MANUAL"), scanner_write=False, paper_write=False, profiles_write=False, notifications_write=False, discovery_write=False):
        if not accounts or not set(accounts) <= {"AUTO", "MANUAL"}:
            raise ValueError("Invalid accounts")
        code = secrets.token_urlsafe(24)
        scopes = ["read", "analyze"] + (["scanner:write"] if scanner_write else []) + (["paper:write"] if paper_write else []) + (["profiles:write"] if profiles_write else []) + (["notifications:write"] if notifications_write else []) + (["discovery:write"] if discovery_write else [])
        with self.connect() as c:
            c.execute("DELETE FROM pairings WHERE expires<=?", (self.clock(),))
            if c.execute("SELECT count(*) FROM pairings").fetchone()[0] >= 5:
                raise ValueError("At most five active pairing codes")
            c.execute("INSERT INTO pairings VALUES(?,?,?,?)", (digest(code), self.clock()+120, json.dumps(scopes), json.dumps(accounts)))
        return code

    def exchange(self, code, device_id, name):
        now = self.clock()
        token = "tg_" + secrets.token_urlsafe(32)
        sid = str(uuid.uuid4())
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM pairings WHERE hash=? AND expires>?", (digest(code), now)).fetchone()
            if row is None:
                return None
            c.execute("DELETE FROM pairings WHERE hash=?", (digest(code),))
            c.execute("UPDATE sessions SET revoked=1 WHERE device_id=?", (device_id,))
            c.execute("UPDATE renewal_families SET revoked=1 WHERE device_id=?", (device_id,))
            c.execute("INSERT INTO sessions VALUES(?,?,?,?,?,0,?,?)", (sid, digest(token), device_id, name, now+86400, row["scopes"], row["accounts"]))
            c.execute("DELETE FROM sessions WHERE expires<?", (now-7*86400,))
        return {"session": token, **self.session(token)}

    def session(self, token):
        with self.connect() as c:
            row = c.execute("SELECT * FROM sessions WHERE hash=? AND revoked=0 AND expires>?", (digest(token), self.clock())).fetchone()
        if row is None:
            return None
        with self.connect() as c:
            family=c.execute('SELECT f.* FROM renewal_families f JOIN renewal_sessions s ON f.id=s.family_id WHERE s.sid=?',(row['id'],)).fetchone()
        if family and (family['revoked'] or family['expires']<=self.clock()): return None
        return self._metadata(row,family)

    def revoke(self, sid):
        with self.connect() as c:
            c.execute("UPDATE sessions SET revoked=1 WHERE id=?", (sid,))
            family=c.execute('SELECT family_id FROM renewal_sessions WHERE sid=?',(sid,)).fetchone()
            if family: self._revoke_family(c,family['family_id'])

    def sessions(self):
        with self.connect() as c:
            return [dict(r) for r in c.execute("SELECT id,device_id,name,expires,revoked FROM sessions ORDER BY expires DESC")]

    def permit(self, key, maximum, period=60):
        bucket = int(self.clock())//period
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("DELETE FROM limits WHERE bucket<?", (bucket-2,))
            row = c.execute("SELECT bucket,count FROM limits WHERE key=?", (key,)).fetchone()
            count = row["count"] if row and row["bucket"] == bucket else 0
            if count >= maximum:
                return False
            c.execute("INSERT OR REPLACE INTO limits VALUES(?,?,?)", (key, bucket, count+1))
        return True

    def _revoke_family(self, c, fid):
        c.execute('UPDATE renewal_families SET revoked=1 WHERE id=?', (fid,))
        c.execute('UPDATE sessions SET revoked=1 WHERE id IN (SELECT sid FROM renewal_sessions WHERE family_id=?)', (fid,))

    def grant_renewal(self, session_token):
        """Only called inside initial one-use pairing, never from a bearer-only endpoint."""
        refresh = 'tr_' + secrets.token_urlsafe(32)
        fid = str(uuid.uuid4())
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT * FROM sessions WHERE hash=? AND revoked=0 AND expires>?', (digest(session_token), self.clock())).fetchone()
            if row is None: raise ValueError('Pairing session missing')
            expires = self.clock()+30*86400
            c.execute('INSERT INTO renewal_families VALUES(?,?,?,?,?,?,?,0)', (fid,row['device_id'],row['name'],expires,row['scopes'],row['accounts'],digest(refresh)))
            c.execute('INSERT INTO renewal_tokens(hash,family_id,used) VALUES(?,?,0)', (digest(refresh),fid))
            c.execute('INSERT INTO renewal_sessions VALUES(?,?)', (fid,row['id']))
        return refresh

    def rotate(self, body):
        """Client persists proposed successors BEFORE request. Exact replay returns
        only metadata, issues nothing new, and never extends absolute expiry."""
        old_hash=digest(body['refresh_token'])
        request_hash=digest(json.dumps(body,sort_keys=True,separators=(',',':')))
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            token=c.execute('SELECT * FROM renewal_tokens WHERE hash=?',(old_hash,)).fetchone()
            if token is None: return None
            family=c.execute('SELECT * FROM renewal_families WHERE id=?',(token['family_id'],)).fetchone()
            if family['revoked'] or family['expires']<=self.clock(): return None
            if token['used']:
                if token['request_hash']==request_hash and family['active_hash']==token['next_hash']:
                    row=c.execute('SELECT * FROM sessions WHERE id=? AND revoked=0',(token['access_sid'],)).fetchone()
                    if row: return self._metadata(row, family)
                    return None
                self._revoke_family(c,family['id'])
                return None
            if body['device_id']!=family['device_id'] or old_hash!=family['active_hash']: return None
            next_hash=digest(body['next_refresh_token'])
            access_hash=digest(body['next_session'])
            if next_hash==old_hash or c.execute('SELECT 1 FROM renewal_tokens WHERE hash=?',(next_hash,)).fetchone() or c.execute('SELECT 1 FROM sessions WHERE hash=?',(access_hash,)).fetchone(): return None
            sid=str(uuid.uuid4())
            c.execute('UPDATE sessions SET revoked=1 WHERE id IN (SELECT sid FROM renewal_sessions WHERE family_id=?)',(family['id'],))
            c.execute('INSERT INTO sessions VALUES(?,?,?,?,?,0,?,?)',(sid,access_hash,family['device_id'],family['name'],min(self.clock()+86400,family['expires']),family['scopes'],family['accounts']))
            c.execute('INSERT INTO renewal_sessions VALUES(?,?)',(family['id'],sid))
            c.execute('INSERT INTO renewal_tokens(hash,family_id,used) VALUES(?,?,0)',(next_hash,family['id']))
            c.execute('UPDATE renewal_tokens SET used=1,request_hash=?,next_hash=?,access_sid=? WHERE hash=?',(request_hash,next_hash,sid,old_hash))
            c.execute('UPDATE renewal_families SET active_hash=? WHERE id=?',(next_hash,family['id']))
            row=c.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()
            return self._metadata(row,family)

    def _metadata(self, row, family=None):
        result={'session_id':row['id'],'device_id':row['device_id'],'device_name':row['name'],
            'expires_at_ms':int(row['expires']*1000),'scopes':json.loads(row['scopes']),
            'accounts':json.loads(row['accounts']),'protocol_version':1,
            'capabilities':['session-renewal-v1','market-quotes-v1','analysis-follow-v1','scanner-reconcile-v1','strategy-profiles-v1','profile-scanner-v1','equity-history-v1','equity-history-window-v1','follow-source-events-v1','notification-controls-v1','snapshot-research-v1','dual-scanner-v1','scanner-activation-v1']}
        if family: result.update(renewal_id=family['id'],renewal_expires_at_ms=int(family['expires']*1000))
        return result
