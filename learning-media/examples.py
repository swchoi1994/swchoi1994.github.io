"""Original, reproducible teaching examples. No external infrastructure is used."""
from collections import Counter
from itertools import product
from math import ceil
import json
from pathlib import Path

def two_sum(nums, target):
    seen = {}
    for i, value in enumerate(nums):
        needed = target - value
        if needed in seen:
            return [seen[needed], i]
        seen[value] = i
    raise ValueError('No pair exists')

def two_sum_store_first_wrong(nums, target):
    """Intentional counterexample: stores current index before looking up a pair."""
    seen = {}
    for i, value in enumerate(nums):
        seen[value] = i
        if target - value in seen:
            return [seen[target - value], i]

def anagram(s, t):
    if len(s) != len(t):
        return False
    counts = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    for ch in t:
        if counts.get(ch, 0) == 0:
            return False
        counts[ch] -= 1
    return True

class CacheAside:
    """Single-threaded model, not a Redis client or a distributed transaction."""
    def __init__(self):
        self.db = {'price': 100}
        self.cache = {}
        self.db_reads = 0

    def get(self, key):
        if key in self.cache:
            return self.cache[key]
        value = self.read_db(key)
        self.fill_cache(key, value)
        return value

    def read_db(self, key):
        self.db_reads += 1
        return self.db[key]

    def fill_cache(self, key, value):
        self.cache[key] = value

    def update(self, key, value):
        self.db[key] = value
        self.cache.pop(key, None)

class TokenBucket:
    """Single-process simulation with caller-supplied monotonic timestamps."""
    def __init__(self, capacity, refill_per_second):
        if capacity < 1 or refill_per_second <= 0:
            raise ValueError('Positive capacity and refill rate required')
        self.capacity = capacity
        self.rate = refill_per_second
        self.tokens = float(capacity)
        self.last = 0.0

    def allow(self, now):
        if now < self.last:
            raise ValueError('Time must not move backwards')
        self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
        self.last = now
        if self.tokens < 1:
            return False
        self.tokens -= 1
        return True

def main():
    output = {}
    assert two_sum_store_first_wrong([5, 5], 10) == [0, 0]
    assert two_sum([5, 5], 10) == [0, 1]
    checks = 0
    for n in range(2, 6):
        for nums in product(range(-2, 3), repeat=n):
            for target in range(-4, 5):
                pairs = [(i, j) for i in range(n) for j in range(i + 1, n)
                         if nums[i] + nums[j] == target]
                if pairs:
                    i, j = two_sum(nums, target)
                    assert i != j and nums[i] + nums[j] == target
                else:
                    try:
                        two_sum(nums, target)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError('Unexpected answer')
                checks += 1
    trace = []
    seen = {}
    for i, x in enumerate([4, 9, 1, 6]):
        trace.append({'i': i, 'value': x, 'needed': 10-x, 'before': dict(seen), 'match': 10-x in seen})
        if 10-x in seen:
            break
        seen[x] = i
    output['two_sum'] = {'cases': checks, 'result': two_sum([4,9,1,6],10), 'trace': trace,
                         'duplicates': two_sum([5,5],10)}
    words = [''.join(x) for n in range(5) for x in product('abc', repeat=n)]
    for a in words:
        for b in words:
            assert anagram(a, b) == (sorted(a) == sorted(b))
    output['anagram'] = {'cases': len(words)**2, 'listen_silent': anagram('listen','silent'),
                          'aab_abb': anagram('aab','abb')}
    cache = CacheAside()
    observations = [cache.get('price'), cache.get('price')]
    cache.db['price'] = 120  # Deliberately bypass invalidation to demonstrate staleness.
    observations.append(cache.get('price'))
    cache.update('price', 130)
    observations.append(cache.get('price'))
    assert observations == [100,100,100,130] and cache.db_reads == 2
    # A racing reader can repopulate old data even with DB-first invalidation.
    race = CacheAside()
    old_read = race.read_db('price')  # Reader A pauses between read and fill.
    race.update('price', 130)        # Writer B commits and invalidates.
    race.fill_cache('price', old_read)  # Reader A resumes with its old value.
    assert race.get('price') == 100
    output['cache_aside'] = {'read_values': observations, 'database_reads': cache.db_reads,
                            'race_repopulated_value': race.get('price')}
    bucket = TokenBucket(3, 2)
    times = [0,0,0,0,0.25,0.5,1]
    results = [bucket.allow(t) for t in times]
    assert results == [True,True,True,False,False,True,True]
    for t in range(2, 100):
        bucket.allow(float(t))
        assert 0 <= bucket.tokens <= bucket.capacity
    try:
        bucket.allow(0.5)
    except ValueError:
        pass
    else:
        raise AssertionError('Backwards time was accepted')
    output['token_bucket'] = {'capacity':3,'tokens_per_second':2,'times':times,'allowed':results}
    gib = 2**30
    weights = {str(bits):70_000_000_000*bits/8/gib for bits in [16,8,4]}
    kv = 2*80*8*128*8192*4*2/gib
    assert kv == 10
    output['memory'] = {'weightGiB':weights,'kvGiB':kv,
                        'note':'Weight and KV arithmetic only; not a tested hardware configuration.'}
    fixed = 2*730 + 8*50
    api_per_request = (1500*2 + 500*8)/1_000_000
    local_variable = 0.0002
    threshold = ceil(fixed/(api_per_request-local_variable))
    output['cost'] = {'all_rates_hypothetical':True,'fixed':fixed,'api_per_request':api_per_request,
                     'local_variable':local_variable,'break_even_requests':threshold,
                     'monthly':[{'requests':n,'api':round(n*api_per_request,2),
                                  'self_host':round(fixed+n*local_variable,2)} for n in [10000,100000,300000,1000000]]}
    Path(__file__).with_name('example-results.json').write_text(json.dumps(output,indent=2))
    print(json.dumps(output,indent=2))

if __name__ == '__main__':
    main()
