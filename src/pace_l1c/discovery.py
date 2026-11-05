"""Bounded public-catalog discovery and portable, user-owned scene records.

Catalog timestamp overlap ranks candidates only. Scene verifies full native-grid
correspondence after transfer; no discovery result is called an aligned pair.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256 as digest
import json
import math
import os
from pathlib import Path
import re
import sys
from .acquisition import boxes, catalog_record, save

COLLECTIONS = {
    'oci_l1c': {'short_name': 'PACE_OCI_L1C_SCI', 'version': '3'},
    'harp2_l1c': {'short_name': 'PACE_HARP2_L1C_SCI', 'version': '4'},
    'harp2_gpc': {'short_name': 'PACE_HARP2_L2_CLOUD_GPC', 'version': '4.0'},
}
NAME = re.compile(r'PACE_(OCI|HARP2)\.(\d{8}T\d{6})\.(L1C\.V[\d_]+\.5km|L2\.CLOUD_GPC\.V[\d_]+)\.nc')
CONCEPT = re.compile(r'G\d+-[A-Z0-9_]+')


def cache_directory(value=None):
    if value:
        return Path(value).expanduser().resolve()
    if os.environ.get('PACE_L1C_CACHE'):
        return Path(os.environ['PACE_L1C_CACHE']).expanduser().resolve()
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library/Caches'
    else:
        base = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
    return base / 'pace-l1c-vis'


def role_and_stamp(name):
    match = NAME.fullmatch(name)
    if not match:
        raise ValueError('Unsupported product filename; use an OCI/HARP2 5 km L1C or HARP2 CLOUD_GPC producer filename')
    instrument, stamp, level = match.groups()
    if level.startswith('L2') and instrument != 'HARP2':
        raise ValueError('Only HARP2 GPC is a supported L2 anchor')
    datetime.strptime(stamp, '%Y%m%dT%H%M%S')
    role='harp2_gpc' if level.startswith('L2') else instrument.lower()+'_l1c'
    expected={'oci_l1c':'L1C.V3.5km','harp2_l1c':'L1C.V4.5km','harp2_gpc':'L2.CLOUD_GPC.V4_0'}[role]
    if level!=expected:raise ValueError('Unsupported processing version; use OCI L1C V3, HARP2 L1C V4 or GPC V4.0')
    return role, stamp


def catalog_entry(g, role=None):
    entry = catalog_record(g, role)
    actual_role, stamp = role_and_stamp(entry['name'])
    if role and role != actual_role:
        raise ValueError('Catalog collection/product role mismatch')
    ref = g['umm'].get('CollectionReference', {})
    temporal = g['umm'].get('TemporalExtent', {})
    entry.update(role=actual_role, timestamp=stamp, producer_id=g['umm'].get('DataGranule', {}).get('ProducerGranuleId', g['umm'].get('GranuleUR')),
                 collection=ref, temporal=temporal, revision_id=g['meta'].get('revision-id'))
    if not CONCEPT.fullmatch(entry['id']):
        raise ValueError('Unsupported CMR granule concept identity')
    expected = COLLECTIONS[actual_role]['short_name']
    if ref.get('Version') and str(ref['Version']) != COLLECTIONS[actual_role]['version']:
        raise ValueError('Catalog collection version does not match the supported product')
    if ref.get('ShortName') and ref['ShortName'] != expected:
        raise ValueError('Unsupported CMR collection for product')
    return entry


def public_entry(entry):
    return {k: v for k, v in entry.items() if k not in ('catalog', 'links', 'path')}


def search(*, identifier='', start=None, end=None, bbox=None, limit=12, query=None):
    """No authentication, URL input or wildcard input. Maximum seven UTC days."""
    if not 1 <= limit <= 20:
        raise ValueError('Candidate limit must be 1–20')
    if query is None:
        import earthaccess
        query = earthaccess.search_data
    records, warnings, failures = {}, [], []
    identifier = identifier.strip()
    anchor = None
    if identifier:
        if NAME.fullmatch(identifier):
            role_and_stamp(identifier)
            results = query(granule_name=identifier, short_name=COLLECTIONS[role_and_stamp(identifier)[0]]['short_name'], count=limit + 1)
        elif CONCEPT.fullmatch(identifier):
            results = query(concept_id=identifier, count=limit + 1)
        else:
            raise ValueError('Enter a complete producer filename or G…-PROVIDER granule concept ID; paths, URLs, wildcards and bare timestamps are not accepted')
        if not results:
            return {'files': {}, 'candidates': [], 'warnings': ['Requested granule was not found'], 'search': {'identifier': identifier}}
        if len(results) > limit:
            raise ValueError('Identifier resolved to too many records; use a specific CMR concept ID')
        anchors = [catalog_entry(g) for g in results]
        for item in anchors:
            if NAME.fullmatch(identifier) and item['name'] != identifier:
                raise ValueError('Catalog returned a different producer filename')
            if CONCEPT.fullmatch(identifier) and item['id'] != identifier:
                raise ValueError('Catalog returned a different concept ID')
            records[item['id']] = item
        stamps = {a['timestamp'] for a in anchors}
        if len(stamps) != 1:
            raise ValueError('Identifier resolves to multiple scene times; use a CMR granule concept ID')
        anchor = {'role': anchors[0]['role'], 'ids': {a['id'] for a in anchors}}
        when = datetime.strptime(next(iter(stamps)), '%Y%m%dT%H%M%S').replace(tzinfo=timezone.utc)
        start, end = when - timedelta(minutes=10), when + timedelta(minutes=10)
    else:
        try:
            start = datetime.fromisoformat(str(start).replace('Z', '+00:00'))
            end = datetime.fromisoformat(str(end).replace('Z', '+00:00'))
        except (TypeError, ValueError):
            raise ValueError('Choose a valid start/end date in UTC') from None
        start = start.replace(tzinfo=start.tzinfo or timezone.utc)
        end = end.replace(tzinfo=end.tzinfo or timezone.utc)
        if not timedelta(0) <= end - start <= timedelta(days=7):
            raise ValueError('Search must span zero to seven days')
        if bbox is None:
            raise ValueError('Date search requires a geographic bounding box')
    if bbox is not None:
        if len(bbox) != 4 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in bbox):
            raise ValueError('Bounding box must contain four finite numbers')
        w, s, e, n = bbox
        if not (-180 <= w <= 180 and -180 <= e <= 180 and -90 <= s < n <= 90):
            raise ValueError('Invalid longitude/latitude bounds')
    for role, collection in COLLECTIONS.items():
        if anchor and role == anchor['role']:
            continue
        for box in boxes(bbox) if bbox is not None else [None]:
            try:
                kwargs = dict(collection, temporal=(start.isoformat(), end.isoformat()), count=limit + 1)
                if box is not None:
                    kwargs['bounding_box'] = tuple(box)
                found = query(**kwargs)
                if len(found) > limit:
                    warnings.append(f'{role}: results truncated; narrow the search to see other candidates')
                for g in found[:limit]:
                    item = catalog_entry(g, role)
                    records[item['id']] = item
            except Exception as error:
                failures.append({'role': role, 'error': type(error).__name__})
    if failures:
        warnings.append('Some catalog queries failed. Missing companions may reflect a service failure; retry the search.')
    candidates = []
    for o in sorted((f for f in records.values() if f['role'] == 'oci_l1c'), key=lambda f: (f['timestamp'], f['id'])):
        for h in sorted((f for f in records.values() if f['role'] == 'harp2_l1c'), key=lambda f: f['id']):
            if o['timestamp'] != h['timestamp']:
                continue
            if anchor and anchor['role'] in ('oci_l1c', 'harp2_l1c') and not (o['id'] in anchor['ids'] or h['id'] in anchor['ids']):
                continue
            gpcs = [f['id'] for f in records.values() if f['role'] == 'harp2_gpc' and f['timestamp'] == h['timestamp']]
            if anchor and anchor['role'] == 'harp2_gpc':
                gpcs = [i for i in gpcs if i in anchor['ids']]
                if not gpcs:
                    continue
            key = digest((o['id'] + '|' + str(o.get('revision_id')) + '|' + h['id'] + '|' + str(h.get('revision_id'))).encode()).hexdigest()[:20]
            candidates.append({'id': key, 'oci': o['id'], 'harp2': h['id'], 'gpc_candidates': gpcs, 'timestamp': o['timestamp'],
                               'status': 'candidate', 'evidence': 'Common filename time only; full native-grid alignment must still be verified'})
    if len(candidates) > 50:
        warnings.append('Pair list limited to 50; narrow your search')
    return {'files': records, 'candidates': candidates[:50], 'warnings': list(dict.fromkeys(warnings)), 'failures': failures,
            'search': {'identifier': identifier, 'start': start.isoformat(), 'end': end.isoformat(), 'bbox': bbox, 'collections': COLLECTIONS}}


def make_manifest(result, candidate_id, directory, *, gpc_id=None, budget_gib=4):
    """Persist one explicitly selected pair, preserving failed-attempt accounting."""
    if not math.isfinite(budget_gib) or not 0 < budget_gib <= 100:
        raise ValueError('Transfer budget must be positive and at most 100 GiB')
    candidate = next((c for c in result['candidates'] if c['id'] == candidate_id), None)
    if candidate is None:
        raise ValueError('Search expired or unknown candidate; search again')
    if gpc_id and gpc_id not in candidate['gpc_candidates']:
        raise ValueError('GPC is not a candidate companion of this scene')
    directory = Path(directory)
    path = directory / 'acquisitions' / (candidate_id + '.json')
    previous = json.loads(path.read_text()) if path.exists() else {}
    pair = {k: candidate[k] for k in ('oci', 'harp2')}
    if gpc_id:
        pair['gpc'] = gpc_id
    files = {i: dict(result['files'][i]) for i in pair.values()}
    for i, f in files.items():
        old = previous.get('files', {}).get(i, {})
        # A catalog revision change must not inherit a verified older product.
        if old.get('revision_id') == f.get('revision_id'):
            f.update({k: old[k] for k in ('path', 'sha256', 'status', 'actual_bytes', 'reason') if k in old})
    m = {'schema_version': 1, 'search': result['search'], 'attempted_bytes': previous.get('attempted_bytes', 0),
         'files': files, 'cases': [{'id': 'selected_scene', 'status': 'candidate', 'pairs': [pair]}],
         'config': {'paths': {'raw': str((directory / 'raw').resolve())},
                    'limits': {'total_download_budget_gib': budget_gib, 'max_candidate_pairs_to_download_per_case': 1}}}
    save(path, m)
    return path


def scene_record(directory, paths, *, label=None, synthetic=False, warnings=()):
    """Verify sources before recording paths; rehash/revalidate on every reopen."""
    from .scene import Scene
    resolved = {k: str(Path(v).expanduser().resolve()) for k, v in paths.items() if v and k in ('oci', 'harp2', 'gpc', 'mie', 'atmosphere')}
    if 'oci' not in resolved or 'harp2' not in resolved:
        raise ValueError('An OCI and HARP2 L1C pair is required')
    scene = Scene(resolved['oci'], resolved['harp2'], resolved.get('gpc'), resolved.get('mie'), resolved.get('atmosphere'))
    try:
        hashes = {k: __import__('pace_l1c.reader', fromlist=['sha256']).sha256(p) for k, p in resolved.items()}
        identifier = digest(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:24]
        record = {'id': identifier, 'label': label or scene.oci.attrs.get('time_coverage_start', Path(resolved['oci']).name),
                  'paths': resolved, 'hashes': hashes, 'synthetic': synthetic, 'alignment': scene.evidence,
                  'warnings': list(warnings), 'created': datetime.now(timezone.utc).isoformat()}
        save(Path(directory) / 'scenes' / (identifier + '.json'), record)
        return record
    finally:
        scene.close()


def saved_scenes(directory):
    result = []
    for path in sorted((Path(directory) / 'scenes').glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            record = json.loads(path.read_text())
            record['available'] = all(Path(p).is_file() for p in record['paths'].values())
            result.append(record)
        except (ValueError, KeyError, OSError):
            continue
    return result


def incomplete_acquisitions(directory):
    """Failed/interrupted downloads remain visible separately from verified scenes."""
    result=[]
    for path in sorted((Path(directory)/'acquisitions').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True):
        if not re.fullmatch('[a-f0-9]{20}',path.stem):continue
        try:
            m=json.loads(path.read_text());pair=m['cases'][0]['pairs'][0]
            core=[m['files'][pair[role]] for role in ('oci','harp2')]
            if m['cases'][0].get('status')=='aligned' and all(f['status']=='complete' for f in core):continue
            result.append({'id':path.stem,'label':core[0]['name'],'attempted_bytes':m.get('attempted_bytes',0),
                           'budget_gib':m['config']['limits']['total_download_budget_gib'],
                           'files':[public_entry(m['files'][i]) for i in pair.values() if isinstance(i,str) and i in m['files']]})
        except (ValueError,KeyError,IndexError,OSError):continue
    return result
