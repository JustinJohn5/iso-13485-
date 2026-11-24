"""保存套册检查时的文件修订与结果，兼容已有的单份检查快照。"""

MAX_PREVIOUS_INSPECTIONS = 3


def unpack_inspections(saved, revision):
    if not saved:
        return None, []
    if 'current' in saved and 'history' in saved:
        return saved['current'], saved['history']
    return {**saved, 'checked_revision': max(revision - 1, 1)}, []


def restore_findings(report):
    if report and report.get('prescreen') and 'findings' not in report:
        return {**report, 'findings': report['prescreen']['items']}
    return report


def update_inspections(saved, new_result, revision):
    current, history = unpack_inspections(saved, revision)
    if current:
        history = [current, *history][:MAX_PREVIOUS_INSPECTIONS]
    if new_result:
        new_result = {**new_result, 'checked_revision': revision}
        if new_result.get('prescreen'):
            new_result.pop('findings', None)
    return {'current': new_result, 'history': history} if new_result or history else None


def inspection_summaries(history):
    return [dict(checked_revision=report['checked_revision'], checked_at=report['checked_at'],
                 version=report['rule_set']['version']) for report in history]
