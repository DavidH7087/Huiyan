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


def test_java_not_confused_with_javascript():
    data = evaluate(['Java'],[],[{'page':1,'text':'熟悉 JavaScript 和 TypeScript，开发前端页面。'}])
    assert data['checks'][0]['state']=='待核实'
    positive = evaluate(['Java'],[],[{'page':1,'text':'负责 Java Spring Boot 服务开发。'}])
    assert positive['checks'][0]['evidence']['matched_text'] in ('Java','java','spring boot','springboot')


def test_evidence_quote_must_be_from_matching_sentence():
    data = evaluate(['客户开发'],[],[{'page':3,'text':'曾任前台岗位。\n负责独立开发客户和客户拜访。'}])
    assert '开发客户' in data['checks'][0]['evidence']['excerpt']
    assert '前台岗位' not in data['checks'][0]['evidence']['excerpt']


def test_technical_alias_with_spaces():
    data=evaluate(['Java'],[],[{'page':1,'text':'独立负责 Spring Boot 项目开发。'}])
    assert data['checks'][0]['evidence']['matched_text'] == 'spring boot'


def test_description_does_not_misread_javascript_as_java():
    rules=suggest_conditions('岗位要求有 JavaScript 前端开发经验')
    assert 'Java' not in rules['required']
