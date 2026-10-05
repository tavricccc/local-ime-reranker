"""Check native prefix coverage, without running model accuracy benchmarks."""
import shutil
from pathlib import Path

from ime_reranker.phonetics import bopomofo_keys
from ime_reranker.rime import Rime
from stage_onion_plus import stage

work = Path('runtime/candidate-pool-check')
user = work / 'user'
user.mkdir(parents=True, exist_ok=True)
shutil.copytree('runtime/rime/shared', work / 'shared', dirs_exist_ok=True)
stage(user)
rime = Rime(workspace=str(work))
cases = [
    'ㄖㄢˊ ㄏㄡˋ ㄨㄛˇ ㄈㄚˉ ㄒㄧㄢˋ',
    'ㄨㄛˇ ㄇㄣ˙ ㄒㄧㄢˉ ㄊㄠˇ ㄌㄨㄣˋ ㄧˊ ㄒㄧㄚˋ',
    'ㄓㄜˋ ㄊㄧˊ ㄐㄧㄝˉ ㄒㄧㄚˋ ㄌㄞˊ ㄎㄜˇ ㄧˇ ㄗㄨㄛˋ ㄧㄣˉ ㄕˋ ㄈㄣˉ ㄐㄧㄝˇ',
]
try:
    for reading in cases:
        session = rime.begin(schema='bopomo_onionplus')
        try:
            keys = bopomofo_keys(reading)
            rime.type(session, keys)
            snapshot = rime.snapshot(session)
            native = {candidate['end'] for candidate in snapshot['candidates']}
            pool = {candidate['end'] for candidate in snapshot['model_pool']}
            assert native == pool, (native, pool)
            assert len(pool) > 1, 'No native prefixes'
            assert len(snapshot['model_pool']) <= 16
            print(f"keys={len(keys)}, model_options={len(snapshot['model_pool'])}, native_prefix_lengths={len(native)}, all_covered=True")
        finally:
            rime.end(session)
finally:
    rime.close()
