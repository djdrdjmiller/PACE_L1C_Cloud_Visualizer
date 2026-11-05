from pace_l1c.acquisition import boxes,catalog_record,save,download
from pathlib import Path
import json
import sys
from types import SimpleNamespace


class Granule(dict):
    def data_links(self):
        return ['https://example.invalid/PACE_OCI.20251002T182635.L1C.V3.5km.nc']


def test_dateline_and_actual_catalog_size():
    assert boxes([170,-25,-170,25])==[[170,-25,180,25],[-180,-25,-170,25]]
    g=Granule(meta={'concept-id':'G1'},umm={'GranuleUR':'prefix', 'DataGranule':{'ArchiveAndDistributionInformation':[{'SizeInBytes':1234}]}})
    record=catalog_record(g,'oci_l1c')
    assert record['size_bytes']==1234
    assert record['name'].startswith('PACE_OCI.')


def test_budget_reserves_failures_and_deduplicates_cases(tmp_path,monkeypatch):
    called=[]
    def fail(*args,**kwargs):
        called.append(args)
        raise OSError('interrupted')
    import earthaccess
    monkeypatch.setattr(earthaccess,'login',lambda **kw:SimpleNamespace(authenticated=True))
    monkeypatch.setattr(earthaccess,'download',fail)
    from earthaccess.results import DataGranule
    monkeypatch.setattr('earthaccess.results.DataGranule',lambda x:x)
    m={'schema_version':1,'config':{'limits':{'total_download_budget_gib':100/1024**3,'max_candidate_pairs_to_download_per_case':1},'paths':{'raw':str(tmp_path/'raw')}},
       'files':{k:{'name':k+'.nc','size_bytes':60,'status':'candidate','catalog':{},'role':'oci_l1c'} for k in ['a','b']},
       'cases':[{'pairs':[{'oci':'a','harp2':'b'}]},{'pairs':[{'oci':'a','harp2':'b'}]}]}
    path=tmp_path/'manifest.json';save(path,m)
    result=download(path)
    assert len(called)==1 and result['attempted_bytes']==60
    assert result['files']['a']['status']=='failed'
    assert result['files']['b']['status']=='budget_excluded'
    download(path)
    assert len(called)==1  # repeated command cannot evade failed-attempt budget
