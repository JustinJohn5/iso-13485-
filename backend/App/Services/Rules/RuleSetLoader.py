"""规则包加载：读取 JSON、校验正则、缓存结果。"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import ValidationError

from App.Services.Rules.RuleModels import Rule, RuleSet
from App.Utils.Errors import ApiError
from App.Utils.Logger import get_logger

logger = get_logger(__name__)

DEFAULT_RULE_SET_ID = "iso13485-core"


class RuleSetLoader:
    """从规则目录加载全部规则包，进程内缓存。"""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._cache: dict[str, RuleSet] | None = None

    def reload(self) -> None:
        """清空缓存，下次访问重新读取磁盘。"""
        self._cache = None

    def load_all(self) -> dict[str, RuleSet]:
        """加载目录下所有 .json 规则包。"""
        if self._cache is not None:
            return self._cache

        rule_sets: dict[str, RuleSet] = {}
        if not self._directory.exists():
            raise ApiError(1305, f"规则包目录不存在：{self._directory}")

        for path in sorted(self._directory.glob("*.json")):
            rule_set = self._load_file(path)
            if rule_set.rule_set_id in rule_sets:
                raise ApiError(1305, f"规则包标识重复：{rule_set.rule_set_id}（{path.name}）")
            rule_sets[rule_set.rule_set_id] = rule_set
            logger.info(
                "已加载规则包 %s v%s（%d 条规则）",
                rule_set.rule_set_id,
                rule_set.version,
                len(rule_set.rules),
            )

        if not rule_sets:
            raise ApiError(1305, "未找到任何规则包，请检查 RULE_SET_DIR 配置")
        self._cache = rule_sets
        return rule_sets

    def get(self, rule_set_id: str | None = None) -> RuleSet:
        """按标识取规则包，缺省取默认规则包。"""
        rule_sets = self.load_all()
        key = rule_set_id or DEFAULT_RULE_SET_ID
        rule_set = rule_sets.get(key)
        if rule_set is None:
            raise ApiError(1301, f"规则包不存在：{key}")
        return rule_set

    def summaries(self) -> list[dict]:
        """规则包摘要列表，用于前端选择。"""
        result: list[dict] = []
        for rule_set in self.load_all().values():
            result.append(
                {
                    "rule_set_id": rule_set.rule_set_id,
                    "title": rule_set.title,
                    "version": rule_set.version,
                    "standard": rule_set.standard,
                    "description": rule_set.description,
                    "rule_count": len(rule_set.rules),
                    "document_type_count": len(rule_set.document_types),
                }
            )
        return sorted(result, key=lambda item: item["rule_set_id"])

    def _load_file(self, path: Path) -> RuleSet:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ApiError(1305, f"规则包 {path.name} 不是合法 JSON：{exc.msg}") from exc

        try:
            rule_set = RuleSet.model_validate(payload)
        except ValidationError as exc:
            first = exc.errors()[0]
            location = ".".join(str(part) for part in first.get("loc", ()))
            raise ApiError(1305, f"规则包 {path.name} 校验失败：{location} {first.get('msg', '')}") from exc

        try:
            rule_set.validate_references()
        except ValueError as exc:
            raise ApiError(1305, f"规则包 {path.name} 引用错误：{exc}") from exc

        self._validate_patterns(rule_set)
        return rule_set

    @staticmethod
    def _validate_patterns(rule_set: RuleSet) -> None:
        """启动即校验正则，避免运行到一半才发现规则写错。"""
        for rule in rule_set.rules:
            for pattern in rule.check.patterns:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    raise ApiError(
                        1305, f"规则 {rule.rule_id} 的正则表达式非法：{exc}"
                    ) from exc

    @staticmethod
    def rules_by_id(rule_set: RuleSet) -> dict[str, Rule]:
        return {rule.rule_id: rule for rule in rule_set.rules}
