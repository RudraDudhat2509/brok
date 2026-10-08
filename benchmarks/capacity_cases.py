"""21 architectures with expected bottleneck + max DAU derived BY HAND, written before running brok.

Derivation, from the cited ceilings in brok/kb.py (low end, ops/s):
  peak_rps = dau * rpd * peak / 86400, so a component with ceiling C seeing share s of traffic
  saturates at  wall_dau = C * 86400 / (rpd * peak * s).
  app_server C=2000, share 1 | load_balancer C=10000, share 1
  relational_db: no cache -> C=1000 (write ceiling is lower than read), share 1
                 with cache -> C=1000, share 1/(1+rw)  (writes only; rw = reads per write)
  cache C=100000, share rw/(1+rw)
  queue/cdn/object_store are off the modeled hot path; unknown types are not estimated.
  Bottleneck = component with the smallest wall. None if nothing is estimable.
Each case: (name, [(name,type)...], traffic, expected_bottleneck_name, expected_wall_dau)
"""
def k(rpd, peak):
    return 86400 / (rpd * peak)

def T(rpd=50, peak=3.0, rw=10.0):
    return {"dau": 100000, "requests_per_user_per_day": rpd, "read_write_ratio": rw,
            "payload_kb": 50.0, "peak_factor": peak}

CASES = [
 ("app+db no cache",            [("app","app_server"),("db","relational_db")], T(), "db", 1000*k(50,3)),
 ("app+db+cache rw10",          [("app","app_server"),("db","relational_db"),("c","cache")], T(), "app", 2000*k(50,3)),
 ("lb+app+db+cache",            [("lb","load_balancer"),("app","app_server"),("db","relational_db"),("c","cache")], T(), "app", 2000*k(50,3)),
 ("app+db+cache rw2",           [("app","app_server"),("db","relational_db"),("c","cache")], T(rw=2), "app", 2000*k(50,3)),
 ("write-heavy rw0.25 cache",   [("app","app_server"),("db","relational_db"),("c","cache")], T(rw=0.25), "db", 1000/(1/1.25)*k(50,3)),
 ("no cache rpd20 peak2",       [("app","app_server"),("db","relational_db")], T(20,2.0,5.0), "db", 1000*k(20,2)),
 ("lb+db only",                 [("lb","load_balancer"),("db","relational_db")], T(100,4.0), "db", 1000*k(100,4)),
 ("cache+app no db",            [("app","app_server"),("c","cache")], T(), "app", 2000*k(50,3)),
 ("app only",                   [("app","app_server")], T(), "app", 2000*k(50,3)),
 ("cache only rw4",             [("c","cache")], T(rw=4), "c", 100000/(4/5)*k(50,3)),
 ("queue+app+db",               [("q","queue"),("app","app_server"),("db","relational_db")], T(), "db", 1000*k(50,3)),
 ("cdn+obj+app+db+cache rw20",  [("cdn","cdn"),("s3","object_store"),("app","app_server"),("db","relational_db"),("c","cache")], T(10,5.0,20.0), "app", 2000*k(10,5)),
 ("two app + db rpd30 peak2",   [("a1","app_server"),("a2","app_server"),("db","relational_db")], T(30,2.0), "db", 1000*k(30,2)),
 ("unknown ignored",            [("app","app_server"),("db","relational_db"),("x","cassandra")], T(), "db", 1000*k(50,3)),
 ("all unknown abstain",        [("x","cassandra"),("y","dynamodb")], T(), None, None),
 ("object store only abstain",  [("s3","object_store")], T(), None, None),
 ("lb+app+db rpd200 peak2",     [("lb","load_balancer"),("app","app_server"),("db","relational_db")], T(200,2.0), "db", 1000*k(200,2)),
 ("read-heavy rw100 cache",     [("app","app_server"),("db","relational_db"),("c","cache")], T(rw=100), "app", 2000*k(50,3)),
 ("write-heavy rw0.1 cache",    [("app","app_server"),("db","relational_db"),("c","cache")], T(rw=0.1), "db", 1000/(1/1.1)*k(50,3)),
 ("lb+app+db+cache rw0.5",      [("lb","load_balancer"),("app","app_server"),("db","relational_db"),("c","cache")], T(100,1.5,0.5), "db", 1000/(1/1.5)*k(100,1.5)),
 ("spiky peak10 no cache",      [("app","app_server"),("db","relational_db")], T(50,10.0), "db", 1000*k(50,10)),
]
