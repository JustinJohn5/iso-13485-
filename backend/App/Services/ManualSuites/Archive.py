"""导出独立套册归档；保留原件、Word 草稿、目录与检查依据。"""
from io import BytesIO
import json
import re
from zipfile import ZipFile, ZIP_DEFLATED

from App.Services.Authoring.WordExport import export_word
from App.Utils.Errors import ApiError
from App.Utils.FileGuard import ensure_inside, sanitize_filename


def build_archive(suite, upload_dir) -> bytes:
    if not suite.items:
        raise ApiError(1001, '空套册不能下载，请先添加文件')
    if sum(row.get('size_bytes', 0) for row in suite.items) > 200 * 1024 * 1024:
        raise ApiError(1001, '整套原件超过200 MB，请分套归档后下载')
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        manifest = dict(suite_uid=suite.suite_uid, name=suite.name, version=suite.version,
                        revision=suite.revision, items=[])
        for index, item in enumerate(suite.items, 1):
            title = re.sub(r'[<>:"/\\|?*]', '-', sanitize_filename(item['title'])).rstrip(' .') or '文件'
            if item['origin'] == 'generated':
                name = f'{index:03d}-{title}.docx'
                archive.writestr(name, export_word(item['snapshot'], item.get('revision', 1)))
            else:
                path = ensure_inside(upload_dir / item['stored_name'], upload_dir)
                if not path.is_file():
                    raise ApiError(1203, f'原件缺失，下载未完成：{title}')
                name = f'{index:03d}-{title}'
                archive.write(path, name)
            manifest['items'].append(dict(title=item['title'], number=item['number'],
                                          file_version=item['file_version'], catalog_key=item['catalog_key'],
                                          origin=item['origin'], sha256=item['sha256'], archive_name=name))
        archive.writestr('目录.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr('检查结果.json', json.dumps(suite.inspection, ensure_ascii=False, indent=2))
    return output.getvalue()
