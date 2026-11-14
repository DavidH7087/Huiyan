"""Fast safeguards for repeatable synthetic HR fixtures; no model download required."""
import json
from collections import Counter
from testdata.synthetic.build_corpus import ROLES, build_cases, create


def test_synthetic_case_count_and_balance():
    jobs,cases=build_cases()
    assert len(jobs)==6
    assert len(cases)==120
    assert len({case['id'] for case in cases})==120
    assert Counter(case['job_id'] for case in cases)=={job['id']:20 for job in jobs}
    assert Counter(case['human_expected_group'] for case in cases)=={'优先查看':60,'需要确认':60}
    assert all('合成测试简历' in case['text'] for case in cases)
    assert all('@example.invalid' in case['text'] for case in cases)
    assert all('000-0000-0000' in case['text'] for case in cases)


def test_generator_text_only_is_reproducible(tmp_path):
    first=tmp_path/'a';second=tmp_path/'b'
    meta1=create(first, include_binary=False)
    meta2=create(second, include_binary=False)
    assert meta1==meta2
    assert (first/'truth.json').read_bytes()==(second/'truth.json').read_bytes()
    for a in sorted((first/'txt').glob('*.txt')):
        assert a.read_bytes()==(second/'txt'/a.name).read_bytes()
    assert len(list((first/'txt').glob('*.txt')))==120


def test_actual_parser_can_extract_all_synthetic_txt(tmp_path):
    from backend.parsing import extract_pages
    out=tmp_path/'fixtures';create(out,include_binary=False)
    for p in (out/'txt').glob('*.txt'):
        pages=extract_pages(p.name,p.read_bytes())
        assert pages and pages[0]['text'].strip()
