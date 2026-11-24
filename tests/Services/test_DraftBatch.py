"""共享参数联动计划的完整校验与原快照隔离。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from App.Schemas.DraftBatch import DraftBatchChange
from App.Services.Authoring.BatchUpdate import build_batch_plan
from App.Services.Authoring.TemplateLibrary import build_snapshot
from App.Utils.Errors import ApiError


def row(uid, owner=1, revision=1):
    snapshot = build_snapshot('design-plan', {'company': '测试组织', 'project': '联动项目', 'product': '测试产品',
                                             'model': 'MODEL-A', 'number': f'DP-{uid}', 'version': '01', 'requirements': '测试要求'})
    return SimpleNamespace(draft_uid=uid, created_by=owner, revision=revision, snapshot=snapshot, history=[])


def payload():
    return DraftBatchChange(drafts=[{'draft_uid': uid, 'revision': 1} for uid in ('a', 'b')],
                            parameters={'model': 'MODEL-B'}, reason='统一更新产品型号')


def test_batch_plan_regenerates_all_selected_drafts_without_overwriting_originals():
    rows = [row('a'), row('b')]
    old = deepcopy([item.snapshot for item in rows])
    plan = build_batch_plan(rows, payload(), SimpleNamespace(id=1, role='auditor'))
    assert len(plan) == 2
    assert all(item['snapshot']['parameters']['model'] == 'MODEL-B' for item in plan)
    assert [item.snapshot for item in rows] == old
    assert plan[0]['snapshot']['parameters']['number'] != plan[1]['snapshot']['parameters']['number']


@pytest.mark.parametrize(('rows', 'code'), [([row('a')], 1702), ([row('a'), row('b', revision=2)], 1703),
                                          ([row('a'), row('b', owner=2)], 1104)])
def test_any_missing_stale_or_unauthorized_draft_rejects_plan(rows, code):
    with pytest.raises(ApiError) as error:
        build_batch_plan(rows, payload(), SimpleNamespace(id=1, role='auditor'))
    assert error.value.code == code


def test_batch_rejects_per_document_identifiers_and_no_changes():
    with pytest.raises(ValidationError):
        DraftBatchChange(drafts=[{'draft_uid': 'a', 'revision': 1}], parameters={'number': 'SAME-01'}, reason='不能共享文件编号')
    data = payload()
    data.parameters = {'model': 'MODEL-A'}
    with pytest.raises(ApiError) as error:
        build_batch_plan([row('a'), row('b')], data, SimpleNamespace(id=1, role='auditor'))
    assert error.value.code == 1001


def test_batch_regeneration_preserves_frozen_rule_basis():
    rows = [row('a'), row('b')]
    rows[0].snapshot['requirements_basis'] = {'version': '历史依据', 'requirements': []}
    plan = build_batch_plan(rows, payload(), SimpleNamespace(id=1, role='auditor'))
    assert plan[0]['snapshot']['requirements_basis'] == rows[0].snapshot['requirements_basis']
    assert plan[0]['snapshot']['generation_review']['basis_version'] == '历史依据'
