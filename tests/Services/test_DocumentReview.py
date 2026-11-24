"""文件集版本、引用和保存期限冲突的纯计算回归。"""
from datetime import date
from hashlib import sha256
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from App.Schemas.DocumentReview import MetadataOverride, ReviewDecision
from App.Services.DocumentControl.Metadata import extract_metadata
from App.Services.DocumentControl.ReviewEngine import build_review, decide, review_ready
from App.Services.DocumentControl.ReviewStore import check_snapshot_files
from App.Services.DocumentControl.Versions import selected_documents
from App.Utils.Errors import ApiError

AS_OF = date(2026, 11, 23)


def sample(uid, number='QP-01', revision='01', effective='2025年01月01日', body='', name='采购程序.txt', status='现行有效'):
    text = f'文件编号：{number}\n版本：{revision}\n生效日期：{effective}\n文件状态：{status}\n{body}'
    return SimpleNamespace(file_uid=uid, original_name=name, document_type='procedure', extracted_text=text,
                           sha256=sha256(text.encode()).hexdigest())


def make_review(*files, overrides=None):
    return build_review(list(files), AS_OF, overrides or {})


def test_latest_effective_is_suggested_but_requires_confirmation():
    snapshot = make_review(sample('old'), sample('new', revision='10', effective='2026年02月01日'))
    group = snapshot['version_groups'][0]
    assert group['suggested_file_uid'] == 'new'
    assert not review_ready(snapshot)
    confirmed = decide(snapshot, 'version', group['id'], 'new', '已核对批准及受控清单', 7)
    assert review_ready(confirmed)
    assert [item['file_uid'] for item in selected_documents(confirmed)] == ['new']
    assert len(confirmed['documents']) == 2
    assert snapshot['decision_history'] == []
    assert confirmed['decision_history'][0]['user_id'] == 7


@pytest.mark.parametrize(('status', 'effective'), [('草稿', '2026年01月01日'), ('已作废', '2026年01月01日'), ('现行有效', '2027年01月01日')])
def test_draft_obsolete_and_future_cannot_be_formal(status, effective):
    snapshot = make_review(sample('old'), sample('blocked', revision='02', effective=effective, status=status))
    group = snapshot['version_groups'][0]
    assert group['ineligible']['blocked']
    with pytest.raises(ApiError):
        decide(snapshot, 'version', group['id'], 'blocked', '用户不应跳过生效限制', 7)


def test_same_revision_different_content_never_gets_automatic_suggestion():
    snapshot = make_review(sample('a', body='采购职责为质量部门'), sample('b', body='采购职责为采购部门', effective='2026年01月01日'))
    assert snapshot['version_groups'][0]['suggested_file_uid'] == ''
    assert '同版本' in snapshot['version_groups'][0]['explanation']


def test_identical_files_and_different_numbers_are_not_competing_versions():
    assert make_review(sample('a'), sample('b'))['version_groups'] == []
    assert make_review(sample('a', number='QP-01'), sample('b', number='QP-02'))['version_groups'] == []


def test_category_enumeration_does_not_override_date_evidence():
    snapshot = make_review(sample('a'), sample('b', revision='02', effective='2026年01月01日'),
                           overrides={'a': {'category': 'regulatory'}, 'b': {'category': 'organization'}})
    assert snapshot['version_groups'][0]['suggested_file_uid'] == 'b'


def test_record_instances_sharing_form_number_remain_separate():
    a = sample('a', number='QR-01', body='供应商甲已评价', name='供应商评价记录甲.txt')
    b = sample('b', number='QR-01', body='供应商乙已评价', name='供应商评价记录乙.txt')
    assert make_review(a, b)['version_groups'][0]['suggested_file_uid'] == ''
    snapshot = make_review(a, b, overrides={'a': {'layer': 'record'}, 'b': {'layer': 'record'}})
    assert not snapshot['version_groups']
    assert len(selected_documents(snapshot)) == 2


def test_missing_dates_do_not_rank_revision_strings():
    snapshot = make_review(sample('a', revision='9', effective='未知'), sample('b', revision='10', effective='未知'))
    assert snapshot['version_groups'][0]['suggested_file_uid'] == ''


def test_reference_waits_for_version_confirmation_and_missing_is_not_nonexistence():
    snapshot = make_review(sample('manual', number='QM-01', body='按 QP-01 执行，并使用 QR-99 表单'),
                           sample('a'), sample('b', revision='02', effective='2026年01月01日'))
    assert next(ref for ref in snapshot['references'] if ref['number'] == 'QP-01')['status'] == 'pending'
    assert next(ref for ref in snapshot['references'] if ref['number'] == 'QR-99')['status'] == 'missing'
    result = decide(snapshot, 'version', snapshot['version_groups'][0]['id'], 'b', '已确认新版受控发布', 7)
    reference = next(ref for ref in result['references'] if ref['number'] == 'QP-01')
    assert reference['status'] == 'linked'
    assert reference['target_file_uids'] == ['b']


def test_retention_conflict_keeps_both_files_and_decision_history():
    snapshot = make_review(sample('manual', number='QM-01', body='QR-07 记录自放行日起保存期限为3年，按 QP-07 执行'),
                           sample('procedure', number='QP-07', body='QR-07 记录自放行日起保存期限为5年'))
    group = snapshot['requirement_conflicts'][0]
    assert group['number'] == 'QR-07'
    assert group['facts'][0]['line'] == 5
    confirmed = decide(snapshot, 'requirement', group['id'], 'procedure', '已核对适用要求并安排手册修订', 7)
    assert review_ready(confirmed)
    assert len(selected_documents(confirmed)) == 2
    assert confirmed['requirement_conflicts'][0]['decision']['file_uid'] == 'procedure'
    assert '修订' in confirmed['requirement_conflicts'][0]['explanation']


@pytest.mark.parametrize(('first', 'second'), [('至少3年', '至少5年'), ('至少3年', '5年'), ('3年', '36个月')])
def test_compatible_retention_requirements_are_not_false_conflicts(first, second):
    snapshot = make_review(sample('a', number='QM-01', body=f'QR-07 保存期限{first}'),
                           sample('b', number='QP-07', body=f'QR-07 保存期限{second}'))
    assert not snapshot['requirement_conflicts']


def test_retention_on_unrelated_numbers_is_not_compared():
    snapshot = make_review(sample('a', number='QM-01', body='QR-01 保存期限3年'),
                           sample('b', number='QP-07', body='QR-02 保存期限5年'))
    assert not snapshot['requirement_conflicts']


def test_changing_version_removes_conflicts_based_only_on_excluded_old_file():
    snapshot = make_review(sample('a', number='QM-01', body='QR-01 自放行日起保存期限3年'),
                           sample('old', body='QR-01 自放行日起保存期限5年'),
                           sample('new', revision='02', effective='2026年01月01日', body='QR-01 自放行日起保存期限3年'))
    assert snapshot['requirement_conflicts']
    confirmed = decide(snapshot, 'version', snapshot['version_groups'][0]['id'], 'new', '已确认新版发布并替代旧版', 7)
    assert not confirmed['requirement_conflicts']
    assert review_ready(confirmed)


@pytest.mark.parametrize('second', ['QR-01 记录保存期限5年', 'QR-01 记录自归档日起保存期限5年'])
def test_unclear_or_different_start_events_require_manual_review(second):
    snapshot = make_review(sample('a', number='QM-01', body='QR-01 记录自放行日起保存期限3年'),
                           sample('b', number='QP-07', body=second))
    assert not snapshot['requirement_conflicts']
    assert snapshot['requirement_manual'][0]['number'] == 'QR-01'


def test_matching_release_event_retains_minimum_and_disposal_conflict_evidence():
    snapshot = make_review(sample('a', number='QM-01', body='QR-01 记录自放行日起保存期限至少3年'),
                           sample('b', number='QP-07', body='QR-01 记录自放行日起保存1年后销毁'))
    assert len(snapshot['requirement_conflicts'][0]['facts']) == 2


def test_approval_label_does_not_claim_verified_approval():
    metadata = extract_metadata('采购程序.txt', '文件编号：QP-01\n批准：经理\n发布日期：2026年01月01日', 'procedure')
    assert metadata['status'] == 'unknown'
    assert metadata['effective_date'] == ''
    assert metadata['category'] == 'organization'


def test_control_procedure_mentions_do_not_make_the_document_obsolete_or_draft():
    metadata = extract_metadata('文件控制程序.txt', '文件编号：QP-01\n草稿由文控员拟定\n作废版本应及时撤回', 'procedure')
    assert metadata['status'] == 'unknown'


def test_invalid_override_dates_extra_fields_and_empty_reason_rejected():
    for values in ({'effective_date': '2026-02-31'}, {'status': 'approved'}, {'extra': 'value'}):
        with pytest.raises(ValidationError):
            MetadataOverride(**values)
    with pytest.raises(ValidationError):
        ReviewDecision(revision=1, kind='version', issue_id='a', file_uid='b', reason='     ')


def test_modified_type_or_file_set_invalidates_review_snapshot():
    file = sample('a')
    snapshot = make_review(file)
    file.document_type = 'other'
    with pytest.raises(ApiError) as caught:
        check_snapshot_files(snapshot, [file])
    assert caught.value.code == 1603


def test_corrected_number_does_not_make_original_header_a_missing_reference():
    snapshot = make_review(sample('a', body='采用 QR-01 记录'), overrides={'a': {'number': 'QP-001'}})
    assert [item['number'] for item in snapshot['references']] == ['QR-01']
