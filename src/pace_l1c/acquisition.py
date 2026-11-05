"""Bounded, auditable catalog discovery and complete-product cache."""
import json
from pathlib import Path
from datetime import datetime, timezone
import yaml
from .reader import sha256, Product, jsonable


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(jsonable(value), indent=2, allow_nan=False))
    tmp.replace(path)


def boxes(bbox):
    west, south, east, north = bbox
    return [bbox] if west <= east else [[west, south, 180, north], [-180, south, east, north]]


def catalog_record(g, role):
    umm = g["umm"]
    distributions = umm.get("DataGranule", {}).get("ArchiveAndDistributionInformation", [])
    size = sum(float(d.get("SizeInBytes", 0)) or float(d.get("Size", 0)) * {"KB": 1024, "MB": 1024**2, "GB": 1024**3, "BYTES": 1}.get(str(d.get("SizeUnit", "MB")).upper(), 1024**2) for d in distributions)
    return {"id": g["meta"]["concept-id"], "role": role,
            "name": Path(g.data_links()[0]).name if g.data_links() else umm["GranuleUR"], "size_bytes": int(size),
            "links": g.data_links(), "catalog": dict(g), "status": "candidate"}


def discover(config_path, manifest_path):
    import earthaccess
    cfg = yaml.safe_load(Path(config_path).read_text())
    previous = json.loads(Path(manifest_path).read_text()) if Path(manifest_path).is_file() else {}
    manifest = {"schema_version": 1, "created": datetime.now(timezone.utc).isoformat(),
                "config": cfg, "files": {}, "cases": [],"attempted_bytes":previous.get("attempted_bytes",0)}
    for case in cfg["cases"]:
        record = dict(case, status="unverified", searches=[], pairs=[])
        found = {}
        for role, collection in cfg["collections"].items():
            if role == "harp2_gpc" and not cfg["limits"]["include_gpc_when_available"]:
                continue
            candidates = {}
            for bbox in boxes(case["bbox"]):
                try:
                    results = earthaccess.search_data(**collection, temporal=(case["start"], case["end"]),
                        bounding_box=tuple(bbox), count=cfg["limits"]["max_candidate_pairs_to_download_per_case"] * 4)
                    record["searches"].append({"role": role, "collection":collection, "bbox": bbox, "count": len(results), "status": "success"})
                    for g in results:
                        f = catalog_record(g, role)
                        if f["id"] in previous.get("files",{}):
                            old=previous["files"][f["id"]]
                            f.update({k:v for k,v in old.items() if k in ("status","sha256","path","actual_bytes","reason")})
                        candidates[f["id"]] = f
                        manifest["files"][f["id"]] = f
                except Exception as e:
                    record["searches"].append({"role": role, "collection":collection, "bbox": bbox, "status": "failed", "reason": type(e).__name__})
            found[role] = list(candidates.values())
        # Filename timestamp is a ranking hint only. Scene later verifies grid + geolocation.
        def stamp(f):
            return f["name"].split(".")[1]
        for o in sorted(found.get("oci_l1c", []), key=lambda f: (stamp(f) != case.get("preferred_timestamp"), f["name"])):
            for h in found.get("harp2_l1c", []):
                if stamp(o) == stamp(h):
                    pair = {"oci": o["id"], "harp2": h["id"], "status": "candidate", "ranking_evidence": "common filename timestamp; correspondence unverified"}
                    gpc = next((g for g in found.get("harp2_gpc", []) if stamp(g) == stamp(h)), None)
                    if gpc:
                        pair["gpc"] = gpc["id"]
                    old_case=next((c for c in previous.get('cases',[]) if c['id']==case['id']),{})
                    old_pair=next((p for p in old_case.get('pairs',[]) if p['oci']==pair['oci'] and p['harp2']==pair['harp2']),{})
                    if 'manual_review' in old_pair:
                        pair['manual_review']=old_pair['manual_review']
                    record["pairs"].append(pair)
        record["pairs"] = record["pairs"][:cfg["limits"]["max_candidate_pairs_to_download_per_case"]]
        if not record["pairs"]:
            record["status"] = "missing"
        manifest["cases"].append(record)
        save(manifest_path, manifest)
        print(case["id"], record["status"], len(record["pairs"]), "candidate pairs", flush=True)
    return manifest


class DownloadCancelled(RuntimeError):
    pass


def download(manifest_path, *, session=None, cancelled=None, progress=None, authenticate=True):
    import earthaccess
    from earthaccess.results import DataGranule
    m = json.loads(Path(manifest_path).read_text())
    cfg = m["config"]
    authenticated = False
    cancelled = cancelled or (lambda: False)
    progress = progress or (lambda value: None)
    raw = Path(cfg["paths"]["raw"])
    raw.mkdir(parents=True, exist_ok=True)
    budget = int(cfg["limits"]["total_download_budget_gib"] * 1024**3)
    used = m.get("attempted_bytes", 0)
    # Round-robin cases so extra candidates cannot consume the entire budget
    # before every development scenario receives its first candidate.
    limit = cfg["limits"]["max_candidate_pairs_to_download_per_case"]
    ids = list(dict.fromkeys(p[role] for rank in range(limit) for c in m["cases"]
        for p in c["pairs"][rank:rank+1] for role in ("oci", "harp2", "gpc") if role in p))
    for id_ in ids:
        if cancelled():
            raise DownloadCancelled('Acquisition cancelled; completed files retained')
        f = m["files"][id_]
        if session is not None:
            # Isolate catalog identities/revisions, including identical producer names.
            import hashlib
            directory = raw / hashlib.sha256((id_ + ':' + str(f.get('revision_id'))).encode()).hexdigest()[:24]
            directory.mkdir(exist_ok=True)
        else:
            directory = raw
        final = directory / Path(f["name"]).name
        if final.exists() and f.get("sha256") == sha256(final):
            f["status"] = "complete"
            continue
        staging=directory/(id_+'.partial')
        staged=staging/Path(f['name']).name
        # A fully transferred file that failed an older reader can be revalidated
        # offline. Do not charge bytes again or redownload a known-complete body.
        archive=f['catalog'].get('umm',{}).get('DataGranule',{}).get('ArchiveAndDistributionInformation',[])
        exact=next((d['SizeInBytes'] for d in archive if d.get('Name')==f['name'] and 'SizeInBytes' in d),None)
        if session is not None and staged.is_file() and exact is not None and staged.stat().st_size==int(exact):
            try:
                digest=_validate_content(staged,f)
                staged.replace(final)
                f.update(status='complete',path=str(final),sha256=digest,actual_bytes=final.stat().st_size,recovered_staged=True)
                f.pop('reason',None);f.pop('failure_stage',None)
            except Exception as error:
                f.update(status='validation_failed',failure_stage='validation',reason=f'{type(error).__name__}: '+(str(error) if isinstance(error,ValueError) else 'Complete staged file did not pass NetCDF/catalog checks'))
            save(manifest_path,m)
            progress({'file':f['name'],'status':f['status'],'bytes':int(exact),'expected_bytes':f['size_bytes'],'attempted_bytes':used})
            continue
        if f["size_bytes"] <= 0 or used + f["size_bytes"] > budget:
            f.update(status="budget_excluded", reason="unknown size or total configured transfer budget exceeded")
            save(manifest_path, m)
            continue
        if session is None and authenticate and not authenticated:
            auth = earthaccess.login(strategy="netrc", persist=False)
            if not auth.authenticated:
                raise RuntimeError("Earthdata login required: run pace-l1c login, then retry")
            authenticated = True
        # Reserve attempted volume even for failure; never evade limits by retries.
        used += f["size_bytes"]
        m["attempted_bytes"] = used
        staging = directory / (id_ + ".partial")
        staging.mkdir(exist_ok=True)
        f["status"] = "transferring"
        save(manifest_path, m)
        phase='transfer'
        try:
            progress({'file':f['name'],'status':'transferring','bytes':0,'expected_bytes':f['size_bytes'],'attempted_bytes':used})
            if session is None:
                paths = earthaccess.download([DataGranule(f["catalog"])], local_path=str(staging), threads=1)
            else:
                paths = [_stream_product(f, staging, session, budget - (used - f['size_bytes']), cancelled, progress)]
            if len(paths) != 1 or not Path(paths[0]).is_file():
                raise OSError("No complete transfer returned")
            source = Path(paths[0])
            phase='validation'
            if cancelled():raise DownloadCancelled('Acquisition cancelled before validation')
            if source.stat().st_size > budget - (used - f['size_bytes']):raise ValueError('Actual size exceeds remaining budget')
            digest=_validate_content(source,f,strict_identity=session is not None)
            source.replace(final)
            actual = final.stat().st_size
            # Reserve the larger of catalog and actual size, including failed attempts.
            used += max(0, actual - f['size_bytes'])
            f.update(status="complete", path=str(final), sha256=digest, actual_bytes=actual)
            f.pop("reason",None);f.pop("failure_stage",None)
            progress({'file':f['name'],'status':'complete','bytes':actual,'expected_bytes':f['size_bytes'],'attempted_bytes':used})
        except Exception as e:
            used += max(0, f.get('received_bytes',0)-f['size_bytes'])
            # Stream helper never writes beyond its reservation. Failed retries still cost bytes.
            status='cancelled' if isinstance(e,DownloadCancelled) else 'validation_failed' if phase=='validation' else 'failed'
            detail=str(e) if isinstance(e,ValueError) else 'Transfer failed (HTTP '+str(getattr(getattr(e,'response',None),'status_code','unavailable'))+'); check authentication/network' if phase=='transfer' else 'NetCDF/catalog validation failed; complete staged file retained'
            f.update(status=status,failure_stage=phase,reason=f'{type(e).__name__}: {detail}')
            if isinstance(e,DownloadCancelled):
                m['attempted_bytes']=used
                save(manifest_path,m)
                raise
        m["attempted_bytes"] = used
        save(manifest_path, m)
        print(f["name"], f["status"], flush=True)
    return m


def _validate_content(source,f,*,strict_identity=True):
    archive=f['catalog'].get('umm',{}).get('DataGranule',{}).get('ArchiveAndDistributionInformation',[])
    exact=next((d['SizeInBytes'] for d in archive if d.get('Name')==f['name'] and 'SizeInBytes' in d),None)
    if exact is not None and source.stat().st_size!=int(exact):
        raise OSError('Downloaded byte count differs from catalog SizeInBytes')
    # NetCDF parse required before marking complete; GPC has different adapter.
    if f["role"] != "harp2_gpc":
        product = Product(source)
        try:
            if strict_identity and product.attrs.get('product_name')!=f['name']:
                raise ValueError('Downloaded product identity differs from selected catalog product')
        finally:
            product.close()
    else:
        import xarray as xr
        with xr.open_dataset(source, engine="h5netcdf") as product:
            if strict_identity and product.attrs.get('product_name')!=f['name']:
                raise ValueError('Downloaded GPC identity differs from selected catalog product')
    digest = sha256(source)
    for archive_entry in archive:
        check=archive_entry.get('Checksum',{})
        if archive_entry.get('Name') not in (None,f['name']) or not check:continue
        algorithm=str(check.get('Algorithm','')).lower().replace('-','')
        expected=str(check.get('Value','')).lower()
        if algorithm in ('md5','sha1','sha256') and expected:
            import hashlib
            hasher=hashlib.new(algorithm)
            with source.open('rb') as stream:
                for chunk in iter(lambda:stream.read(2**20),b''):hasher.update(chunk)
            if hasher.hexdigest()!=expected:raise ValueError('Catalog checksum mismatch')
    return digest


def _stream_product(record, staging, session, allowance, cancelled, progress):
    """Chunked path for the launcher; uses the existing manifest/budget protocol."""
    from .discovery import role_and_stamp
    name=record['name']
    role_and_stamp(name)  # No arbitrary URL/path is accepted from the browser.
    target=staging/name
    size=record['size_bytes']
    # Cap at catalog reservation, even when Content-Length is absent or inaccurate.
    maximum=min(size,allowance)
    received=0
    record['received_bytes']=0
    with session.get('https://oceandata.sci.gsfc.nasa.gov/ob/getfile/'+name,stream=True,timeout=(15,30)) as response:
        response.raise_for_status()
        if 'text/html' in response.headers.get('Content-Type',''):
            raise RuntimeError('Earthdata returned a sign-in page; check authentication')
        declared=int(response.headers.get('Content-Length',0))
        if declared and declared>maximum:
            raise ValueError('Transfer size exceeds catalog reservation; refresh catalog/budget')
        with target.open('wb') as out:
            for chunk in response.iter_content(2**20):
                received+=len(chunk)
                record['received_bytes']=received
                if cancelled():
                    raise DownloadCancelled('Acquisition cancelled')
                if not chunk:continue
                if received>maximum:
                    raise ValueError('Transfer exceeds reserved size')
                out.write(chunk)
                progress({'file':name,'status':'transferring','bytes':received,'expected_bytes':size})
    if declared and received!=declared:
        raise OSError('Incomplete Content-Length transfer')
    if not received:
        raise OSError('Empty product transfer')
    return target


def inspect_manifest(path):
    from .scene import Scene
    m = json.loads(Path(path).read_text())
    for case in m["cases"]:
        verified = 0
        for pair in case["pairs"]:
            o, h = m["files"][pair["oci"]], m["files"][pair["harp2"]]
            if o["status"] != "complete" or h["status"] != "complete":
                pair.update(status="unavailable", reason="pair transfer incomplete")
                continue
            try:
                scene = Scene(o["path"], h["path"])
                pair.update(status="aligned", evidence=scene.evidence)
                qualifies, evidence = scene.qualify(case["id"], case["bbox"])
                review=pair.get('manual_review')
                if case['id']=='science_scene' and isinstance(evidence,str) and 'requires visual inspection' in evidence and review and review.get('input_sha256')==[o['sha256'],h['sha256']] and review.get('bbox')==case['bbox']:
                    qualifies,evidence=True,review
                pair.update(case_verified=qualifies, case_evidence=evidence)
                if qualifies and verified>=m["config"]["limits"]["max_pairs_per_case"]:
                    pair["case_verified"]=False
                    pair["case_evidence"]="Additional aligned candidate; qualifying-pair limit already reached"
                else:
                    verified += int(qualifies)
                scene.close()
            except Exception as e:
                pair.update(status="rejected", reason=str(e))
        case["status"] = "verified" if verified else "missing_qualification"
        save(path, m)
    return m
