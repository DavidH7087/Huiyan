"""Precise, non-inferential résumé profile regressions (fictional candidates)."""
from backend.profile import PROFILE_VERSION, extract_profile


def _profile(text):
    return extract_profile([{'page': 2, 'text': text, 'source': 'pdf_text'}])


def test_total_and_specific_years_are_not_a_conflict():
    out=_profile('8年工作经验\n5年B2B销售与客户开发经验')
    assert PROFILE_VERSION == 'rules-v3'
    assert out['stated_experience_years']==[5,8]
    assert not out['experience_years_conflict']
    assert {(m['scope'],m['years']) for m in out['experience_duration_mentions']} == {
        ('total',8),('specific',5)}
    assert all(m['evidence']['page']==2 and m['context'] for m in out['experience_duration_mentions'])


def test_genuinely_conflicting_total_years_are_marked():
    out=_profile('3年工作经验\n相关工作经验5年')
    assert out['experience_years_conflict']


def test_multiple_skill_years_do_not_claim_conflicting_total_employment():
    out=_profile('5年销售经验\n3年渠道拓展经验')
    assert not out['experience_years_conflict']
    assert len(out['experience_duration_mentions'])==2


def test_negated_education_and_skills_do_not_become_positive_facts():
    out=_profile('未取得本科学历；拥有大专学历\n'
                 '不熟悉 Python，但熟悉 Excel；没有 Java 使用经验\n'
                 '技能：SQL')
    assert [e['label'] for e in out['education_mentions']]==['大专']
    assert {s['label'] for s in out['skill_mentions']} == {'Excel','SQL'}


def test_job_requirements_and_negated_years_not_marked_as_experience():
    out=_profile('岗位要求至少5年工作经验\n'
                 '没有3年销售管理经验\n'
                 '本人具有5年以上的工作经验')
    assert out['stated_experience_years']==[5]
    assert len(out['experience_duration_mentions'])==1
    assert out['experience_duration_mentions'][0]['scope']=='total'


def test_ocr_source_traceability_retained():
    out=extract_profile([
        {'page': 4,'source':'ocr','text':'5年销售项目经验\n技能：Excel',
         'warning':'图片识别需要核对'}
    ])
    years=out['experience_duration_mentions']
    assert len(years)==1 and years[0]['evidence']['page']==4
    assert years[0]['evidence']['needs_verification']
    assert out['needs_source_review']
