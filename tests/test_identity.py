from backend.parsing import extract_identity


def test_labelled_name_and_spaced_phone():
    result=extract_identity([{'page':1,'text':'个人简历\n姓名：王小明\n手机号：138 0000 1234\n邮箱：xx@example.com'}],'file.docx')
    assert result['name']=='王小明'
    assert result['phone']=='13800001234'
    assert result['email']=='xx@example.com'


def test_title_is_not_a_person():
    out=extract_identity([{'page':1,'text':'个人简历\n应聘职位：财务专员'}],'周某-财务.txt')
    assert out['name']=='周某-财务'


def test_simple_chinese_name_still_works():
    out=extract_identity([{'page':1,'text':'张三\nPython开发工程师'}],'candidate.txt')
    assert out['name']=='张三'
