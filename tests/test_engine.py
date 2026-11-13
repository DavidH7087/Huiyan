from backend.engine import suggest_conditions, evaluate, alias_options
from backend.parsing import extract_pages, ParseError, expand_upload
import io
import zipfile
import pytest


def test_description_rules():
    d=suggest_conditions('寻找有企业客户开发经验，熟悉 B2B 销售，最好有制造业客户资源的候选人。不要求润滑油行业经验。')
    assert '客户开发' in d['required']
    assert 'B2B销售' in d['required']
    assert '制造业' in d['preferred']
    assert '润滑油' not in d['required']


def test_evidence_not_missing_equals_false():
    data=evaluate(['B2B销售','客户开发'],['制造业'],[{'page':2,'text':'负责工业品销售，独立开发制造企业客户。'}])
    assert data['group']=='优先查看'
    assert all(c['evidence']['page']==2 for c in data['checks'])
    missing=evaluate(['团队管理'],[],[{'page':1,'text':'负责销售'}])
    assert missing['group']=='需要确认'
    assert missing['checks'][0]['state']=='待核实'


def test_zip_rejects_traversal():
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:
        z.writestr('../a.txt','test')
    with pytest.raises(ParseError):
        list(expand_upload('resumes.zip',b.getvalue()))


def test_txt_chinese():
    pages=extract_pages('张三.txt','张三\n负责客户开发'.encode())
    assert '客户开发' in pages[0]['text']


def test_negative_sentence_is_not_positive_evidence():
    result=evaluate(['B2B销售'],[],[{'page':1,'text':'没有 B2B 销售经历。'}])
    assert result['checks'][0]['state']=='待核实'
