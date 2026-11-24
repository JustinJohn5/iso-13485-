"""按本次冻结的文件关系查找明确引用，不向范围外查询。"""
import re

from App.Services.DocumentControl.Metadata import ID_PATTERN, normalize_number

MARKER = re.compile(r'参见|参照|引用|按照|依据|(?<![意见会意])见')
GENERIC = re.compile(r'参照有关文件|参见相关文件|按规定执行')
VERSION = re.compile(r'^\s*(?:版本\s*[:：]?\s*([A-Za-z0-9.]+)|[vV]\s*(\d+(?:\.\d+)*))')


def version_key(value):
    return re.sub(r'^v(?=\d)', '', value.strip().casefold())


class ControlledReferences:
    def __init__(self, documents, snapshot):
        self.documents = {row.file_uid: row for row in documents}
        self.metadata = {row['file_uid']: row['metadata'] for row in snapshot.get('documents', [])}
        self.links = {(row['source_file_uid'], row['number']): row
                      for row in snapshot.get('references', []) if row['status'] == 'linked'}

    def locate(self, source_uid, segment):
        """返回是否引用及可用于取证的目标。版本未知或不一致时保留待补。"""
        marker = MARKER.search(segment)
        if not marker:
            return bool(GENERIC.search(segment)), None
        tail = segment[marker.end():]
        numbers = list(re.finditer(ID_PATTERN, tail))
        if len(numbers) != 1:
            return bool(numbers or GENERIC.search(segment)), None
        number = numbers[0]
        relation = self.links.get((source_uid, normalize_number(number.group(1))), {})
        targets = relation.get('target_file_uids', [])
        if len(targets) != 1 or targets[0] == source_uid:
            return True, None
        uid = targets[0]
        revision = self.metadata.get(uid, {}).get('revision')
        explicit = VERSION.match(tail[number.end():])
        if not revision or (explicit and version_key(next(value for value in explicit.groups() if value)) != version_key(revision)):
            return True, None
        return True, self.documents.get(uid)
