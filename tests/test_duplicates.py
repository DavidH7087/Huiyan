from backend.duplicates import annotate_possible_duplicates
from backend.app import create_app
from fastapi.testclient import TestClient


def test_matching_contact_info_only_not_matching_names():
    data = [
        {'resume_id': 1, 'name': '张三', 'email': 'TEST@EXAMPLE.INVALID', 'phone': ''},
        {'resume_id': 2, 'name': '张三', 'email': 'test@example.invalid', 'phone': ''},
        {'resume_id': 3, 'name': '张三', 'email': 'unique@example.invalid', 'phone': ''},
        {'resume_id': 4, 'name': '张三', 'email': '', 'phone': '000-0000-0000'},
    ]
    annotate_possible_duplicates(data)
    assert data[0]['possible_duplicate_with'] == [2]
    assert data[1]['duplicate_reasons'] == ['邮箱一致']
    assert data[2]['possible_duplicate_with'] == []
    assert data[3]['possible_duplicate_with'] == []


def test_same_valid_phone_or_email_is_only_a_hint():
    data = [
        {'resume_id': 4, 'email': 'a@example.invalid', 'phone': '13800138000'},
        {'resume_id': 6, 'email': 'b@example.invalid', 'phone': '138 0013 8000'},
    ]
    annotate_possible_duplicates(data)
    assert data[0]['possible_duplicate_with'] == [6]
    assert data[0]['duplicate_reasons'] == ['手机号一致']
    assert len(data) == 2  # Both originals must remain.


def test_api_same_person_two_formats_kept_and_flagged(tmp_path):
    app = create_app(tmp_path / 'dedup')
    with TestClient(app) as client:
        task_id = client.post('/api/tasks', json={'title':'后端招聘', 'required':['Java']}).json()['id']
        files = [
            ('files',('version1.txt','姓名：张三\n邮箱：case@example.invalid\n负责Java服务开发'.encode(), 'text/plain')),
            ('files',('version2.txt','姓名：张三\n邮箱：CASE@example.invalid\n负责Java开发和系统联调'.encode(), 'text/plain')),
            ('files',('another.txt','姓名：张三\n邮箱：other@example.invalid\n负责财务核算'.encode(), 'text/plain')),
        ]
        imported = client.post(f'/api/tasks/{task_id}/resumes', files=files).json()
        assert imported['imported'] == 3
        rid = client.post(f'/api/tasks/{task_id}/runs', json={}).json()['id']
        records = client.get(f'/api/tasks/{task_id}/runs/{rid}/results').json()['results']
        assert len(records) == 3
        by_file = {r['filename']: r for r in records}
        assert by_file['version1.txt']['possible_duplicate_with'] == [by_file['version2.txt']['resume_id']]
        assert by_file['version2.txt']['possible_duplicate_with'] == [by_file['version1.txt']['resume_id']]
        assert by_file['another.txt']['possible_duplicate_with'] == []
        groups = client.get(f'/api/tasks/{task_id}/duplicates').json()['groups']
        assert len(groups) == 1
        assert len(groups[0]['resume_ids']) == 2
        # The grouping must not span independent recruitment tasks.
        unrelated = client.post('/api/tasks', json={'title': '另一岗位'}).json()['id']
        assert client.get(f'/api/tasks/{unrelated}/duplicates').json()['groups'] == []


def test_overlapping_phone_email_chains_form_one_group():
    from backend.duplicates import collect_duplicate_groups
    rows = [
        {'resume_id':1,'email':'a@example.invalid','phone':''},
        {'resume_id':2,'email':'a@example.invalid','phone':'13800138000'},
        {'resume_id':3,'email':'other@example.invalid','phone':'13800138000'},
    ]
    assert collect_duplicate_groups(rows) == [{
        'resume_ids':[1,2,3], 'reasons':['手机号一致','邮箱一致']
    }]
