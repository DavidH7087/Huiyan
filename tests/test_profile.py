from backend.profile import extract_profile


def test_structured_profile_explicit_with_source():
    result = extract_profile([
        {'page': 1, 'text': '教育经历：本科\n技能：Python、Excel、SQL\n5年工作经验', 'source': 'pdf_text'},
        {'page': 2, 'text': '项目经历：负责库存管理项目', 'source': 'ocr', 'warning': '需核对'},
    ])
    assert result['education_mentions'][0]['label'] == '本科'
    assert {x['label'] for x in result['skill_mentions']} == {'Python','Excel','SQL'}
    assert result['stated_experience_years'] == [5]
    assert result['needs_source_review']
    assert result['experience_mentions'][-1]['page'] == 2
    assert result['experience_mentions'][-1]['needs_verification']


def test_no_fabricated_years_or_sensitive_traits():
    out = extract_profile([{'page':1,'text':'2020-2025 销售岗\n熟悉 JavaScript\n硕士学历'}])
    assert out['stated_experience_years'] == []
    assert [s['label'] for s in out['skill_mentions']] == ['JavaScript']
    assert 'Java' not in [s['label'] for s in out['skill_mentions']]
    assert 'gender' not in out and 'age' not in out


def test_conflicting_explicit_years_are_visible():
    out = extract_profile([{'page':1,'text':'3年工作经验\n相关工作经验5年'}])
    assert out['stated_experience_years'] == [3,5]
    assert out['experience_years_conflict']
