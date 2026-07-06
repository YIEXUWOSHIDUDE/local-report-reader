from __future__ import annotations

import json
import re
from typing import Any

from ..config import get_settings
from .ai import ask_ai_json
from .policy_verify import verify_policy_refs_online


class AIAnalysisError(RuntimeError):
    pass


async def analyze_report(filename: str, text: str, language: str) -> dict[str, Any]:
    ai_result = await _analyze_with_ai(filename, text, language)
    if not ai_result:
        raise AIAnalysisError("AI 主分析失败，未生成分析结果。")

    ai_audit = await _economic_audit_with_ai(text)
    if ai_audit:
        ai_result["经济测算专项审查"] = ai_audit

    _sanitize_analysis(ai_result)
    await _apply_online_policy_verification(ai_result)
    _add_output_integrity_check(ai_result)
    ai_result["来源"] = "ai"
    return ai_result


async def compare_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    ai_result = await _compare_with_ai(reports)
    if not ai_result:
        raise AIAnalysisError("AI 交叉比对失败，未生成对比结果。")
    ai_result["来源"] = "ai"
    return ai_result


async def _analyze_with_ai(filename: str, text: str, language: str) -> dict[str, Any] | None:
    policy_refs = extract_policy_refs(text)
    financial_metrics = extract_financial_metrics(text)
    prompt = f"""
你是投资可研、财税和经营测算审查专家。请精读以下报告，输出严格 JSON，不要 Markdown。
文件名：{filename}
语言：{language}

审查要求：
1. 除普通精读外，必须专项审查经济数据测算是否可行、是否有错误、是否有漏项。
2. 税收审查必须覆盖增值税、所得税、税金及附加、关税/进口环节税、税率依据、可能漏项。
3. 经营模式审查必须覆盖收入来源、成本承担、补贴依赖、结算周期、现金流压力。
4. IRR 审查必须说明 IRR 数值、投资收益率、净利润、现金流口径是否足以支持结论。
5. 政策文件核验不得编造。无法确认时写“需人工核验”。
6. 对无法从报告中确认的数据，明确写“报告未列示”或“需补充材料”，不要猜测。
7. 摘要必须是完整自然句，不要输出 [Heading]、Markdown、残缺标题或泛泛口号。
8. 投资建议必须给出具体解决方案，不能只写“关注政策变动风险”“加强合规管理”“优化成本控制”。
9. “经济测算专项审查”的“具体解决方案”必须逐条写明“对应审查项”，用于对应财务测算结论、经营模式审查、税收审查、测算错误与疑点、漏项清单、IRR结论审查、假设条件与依据。
10. “精读结论”必须加入同类企业对比和业务建议。同类企业可以给候选名单，但不能声称已核验；无法确认时在“核验状态”写“需人工核验”。
11. 业务建议必须结合报告经营模式、税费、现金流和 IRR 结论给出可执行动作，不要写空泛口号。
12. 输出重点是“如何修改报告、如何补充数据、如何落地解决”，不要把篇幅主要用于复述或评价报告本身。
13. 需要外部数据时，优先建议使用最新可核验数据。任何外部数据都必须写清数据名称、建议来源、建议截至日期或更新频率、核验状态；无法确认最新性的，写“需联网/人工核验”，不要编造。
14. 每个重要审查发现都要转化为报告修改建议或解决方案。若没有办法给出方案，写明“需要客户先补充材料后再判断”。
15. 同类企业对比只能作为业务参考和修改建议来源，不得把未核验企业案例写成已证实事实。

系统预提取的政策/依据候选：
{json.dumps(policy_refs, ensure_ascii=False)}

系统预提取的测算关键项候选：
{json.dumps(financial_metrics, ensure_ascii=False)}

JSON 结构：
{{
  "标准摘要": {{
    "类型": "宏观框架类/微观调研类/行业公司类/其他",
    "机构": "机构名称或未知",
    "核心观点": "一句到三句",
    "关键假设": ["..."],
    "投资建议": [
      {{"问题或风险": "...", "具体解决方案": "...", "需补充材料": "..."}}
    ],
    "风险提示": ["..."],
    "一句话判断": "明确说明值不值得继续读"
  }},
  "报告修改建议与解决方案": {{
    "总体修改方向": "说明这份报告应优先补强哪些内容，重点面向可交付给客户的修改动作",
    "优先修改清单": [
      {{"优先级": "高/中/低", "原报告问题": "原报告目前的问题或缺口", "建议修改位置": "建议修改的章节或段落", "具体修改建议": "应该怎么改", "解决方案": "业务、财务、税务或合规上的落地做法", "需补充的最新数据": "需要补充的数据名称", "建议数据来源": "官方/企业/行业/客户材料等来源建议", "数据时效要求": "截至日期或更新频率", "核验状态": "需联网核验/需人工核验/报告内已列示"}}
    ],
    "可直接补入报告的表述": [
      {{"适用章节": "...", "建议文本": "可直接替换或补入报告的完整中文段落", "使用前需确认": "需要客户确认的数据或材料"}}
    ],
    "客户需补充材料清单": ["..."]
  }},
  "最新数据补充与核验清单": [
    {{"数据名称": "需要补充或更新的数据", "用途": "用于修正收入/成本/税费/IRR/市场假设/同类企业对比等", "建议来源": "官方统计、主管部门、税务机关、客户台账、合同、审计资料、行业协会或企业年报等", "建议时点或频率": "例如截至最近月/最近季度/最近年度，或每月更新", "准确性要求": "必须与合同/发票/税务申报/政策原文/财务模型一致", "核验状态": "报告内已列示/需联网核验/需人工核验"}}
  ],
  "同类企业对比与业务建议": {{
    "可参考对象": [
      {{"企业或项目类型": "候选同类企业、园区平台、口岸物流、供应链贸易 SPV 等", "相似点": "可对比的业务链路或经营模式", "可借鉴做法": "对本报告修改或业务落地有用的做法", "使用边界": "不能直接套用的差异", "核验状态": "需联网核验/需人工核验/报告内已列示"}}
    ],
    "可落地业务建议": [
      {{"建议主题": "业务模式/客户开发/补贴申领/税务合规/现金流管理/成本控制等", "具体动作": "可执行动作", "写入报告的位置": "建议补入的章节", "预期效果": "对收入、成本、现金流、风险或 IRR 的影响", "前置条件或需补充材料": "需要客户补充或确认的材料"}}
    ]
  }},
  "精读结论": {{
    "定位核心逻辑": "...",
    "拆解假设与证据": {{
      "关键假设": ["..."],
      "证据线索": ["..."],
      "稳健性提示": "..."
    }},
    "评估调研深度": {{
      "一手数据线索": ["..."],
      "财务假设倾向": "保守/中性/激进，并说明原因"
    }},
    "同类企业对比": [
      {{"企业名称": "候选同类企业名称", "相似业务或模式": "与本报告主体相似的业务、贸易链路、口岸物流、供应链或 SPV 模式", "可借鉴做法": "可借鉴的业务做法", "主要差异": "与本项目不同之处", "核验状态": "需人工核验/报告内已列示"}}
    ],
    "业务建议": [
      {{"建议主题": "业务模式/客户开发/补贴申领/税务合规/现金流管理/成本控制等", "具体动作": "可执行动作", "预期效果": "对收入、成本、现金流、风险或 IRR 的影响", "前置条件或需补充材料": "需要客户补充或确认的材料"}}
    ]
  }},
  "经济测算专项审查": {{
    "总体结论": "可行/有条件可行/存疑/不可行，并用一句话说明",
    "财务测算结论": {{
      "判断": "正确/基本正确/有疑点/错误/无法判断",
      "是否可以直接采用": "是/否",
      "错因": ["如果判断为错误或有疑点，逐条列出错因；如果无法判断，列出无法判断原因"],
      "影响": "说明错误或疑点对净利润、现金流、IRR、投资收益率的影响",
      "修正建议": ["给出需要怎么改测算表或补充哪些计算"]
    }},
    "测算关键项摘录": {{
      "增值税": "...",
      "所得税": "...",
      "政府补助": "...",
      "服务收入或服务费": "...",
      "IRR": "...",
      "投资收益率": "..."
    }},
    "经营模式审查": {{
      "收入来源": ["..."],
      "成本承担": ["..."],
      "补贴依赖": "...",
      "结算周期": "...",
      "现金流压力": "..."
    }},
    "税收审查": {{
      "增值税": "...",
      "所得税": "...",
      "税金及附加": "...",
      "关税或进口环节税": "...",
      "税率依据": ["..."],
      "漏项提示": ["..."]
    }},
    "测算错误与疑点": ["..."],
    "具体解决方案": [
      {{"对应审查项": "财务测算结论/经营模式审查/税收审查/测算错误与疑点/漏项清单/IRR结论审查/假设条件与依据", "问题或风险": "...", "解决方案": "...", "责任或材料": "..."}}
    ],
    "漏项清单": ["..."],
    "IRR结论审查": {{
      "IRR数值": "...",
      "投资收益率": "...",
      "净利润": "...",
      "现金流口径": "...",
      "结论是否成立": "..."
    }},
    "假设条件与依据": [
      {{"假设条件": "...", "报告依据": "...", "证据强弱": "强/中/弱", "需补充材料": "..."}}
    ],
    "政策文件核验": [
      {{"政策名称": "...", "是否需要核验": "是/否"}}
    ],
    "需要补充的最新数据": [
      {{"数据名称": "...", "用途": "用于判断测算是否正确或修正 IRR", "建议来源": "...", "建议时点或频率": "...", "核验状态": "报告内已列示/需联网核验/需人工核验"}}
    ]
  }},
  "英文报告全文翻译": "如果原文是英文，请逐段完整翻译成中文，并尽量保留表格结构；如果不是英文，写'非英文报告，无需全文翻译'",
  "关键词": ["..."],
  "语言": "{language}"
}}

报告内容：
{text}
"""
    return await ask_ai_json(prompt)


async def _compare_with_ai(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    payload = []
    for report in reports:
        payload.append(
            {
                "filename": report["filename"],
                "analysis": report.get("analysis"),
                "extracted_text": (report.get("extracted_text") or "")[:12000],
            }
        )

    prompt = f"""
你是投资研究总监。请对多份报告做交叉比对，输出严格 JSON，不要 Markdown。
需要完成三件事：找一致性信号、找矛盾点、画预期差地图。若报告已有同类企业对比和业务建议，请纳入对比；若某份报告缺少已生成分析，请直接基于原文摘要分析，不要编造。

JSON 结构：
{{
  "报告数量": 2,
  "一致性信号": ["..."],
  "矛盾点": ["..."],
  "预期差地图": [
    {{"主题": "...", "市场共识": "...", "报告判断": "...", "预期差": "...", "跟进问题": "..."}}
  ],
  "同类企业与业务建议交叉参考": [
    {{"主题": "同类企业/业务建议", "共同做法": "...", "差异点": "...", "可落地建议": "...", "需核验事项": "..."}}
  ],
  "报告摘要": [
    {{"报告": "...", "机构": "...", "核心观点": "..."}}
  ]
}}

报告材料：
{json.dumps(payload, ensure_ascii=False)}
"""
    return await ask_ai_json(prompt)


async def _economic_audit_with_ai(text: str) -> dict[str, Any] | None:
    policy_refs = extract_policy_refs(text)
    financial_metrics = extract_financial_metrics(text)
    focused_text = _focused_audit_text(text)
    prompt = f"""
你是投资可研、财税和经营测算审查专家。只输出严格 JSON，不要 Markdown。

请审查这份可研报告的经济测算是否可行、是否有错误、是否有漏项。重点覆盖税收、经营模式、IRR、假设依据和政策文件。无法确认的数据必须写“报告未列示”或“需补充材料”。
输出重点是报告应该怎么改、补什么数据、怎么落地解决，而不是只评价原报告。需要外部数据时，优先建议使用最新可核验数据，并写清数据来源建议、建议截至日期或更新频率、核验状态。
同时必须给出可执行解决方案，不能只写“关注风险/加强管理/优化成本控制”。摘要和字段内禁止输出 [Heading]、Markdown、残缺标题。
“具体解决方案”必须逐条写明“对应审查项”，和审查发现一一对应。
每一项“测算错误与疑点”“漏项清单”“IRR结论审查”“假设条件与依据”的重要问题，都要能在“具体解决方案”中找到对应处理动作；如果需要客户先补资料，解决方案中直接写补充材料和修正测算表的动作。

系统预提取政策候选：
{json.dumps(policy_refs, ensure_ascii=False)}

系统预提取测算关键项：
{json.dumps(financial_metrics, ensure_ascii=False)}

输出 JSON 结构：
{{
  "总体结论": "可行/有条件可行/存疑/不可行，并用一句话说明",
  "财务测算结论": {{
    "判断": "正确/基本正确/有疑点/错误/无法判断",
    "是否可以直接采用": "是/否",
    "错因": ["如果判断为错误或有疑点，逐条列出错因；如果无法判断，列出无法判断原因"],
    "影响": "说明错误或疑点对净利润、现金流、IRR、投资收益率的影响",
    "修正建议": ["给出需要怎么改测算表或补充哪些计算"]
  }},
  "测算关键项摘录": {{
    "增值税": "...",
    "所得税": "...",
    "政府补助": "...",
    "服务收入或服务费": "...",
    "IRR": "...",
    "投资收益率": "..."
  }},
  "经营模式审查": {{
    "收入来源": ["..."],
    "成本承担": ["..."],
    "补贴依赖": "...",
    "结算周期": "...",
    "现金流压力": "..."
  }},
  "税收审查": {{
    "增值税": "...",
    "所得税": "...",
    "税金及附加": "...",
    "关税或进口环节税": "...",
    "税率依据": ["..."],
    "漏项提示": ["..."]
  }},
  "测算错误与疑点": ["..."],
  "具体解决方案": [
    {{"对应审查项": "财务测算结论/经营模式审查/税收审查/测算错误与疑点/漏项清单/IRR结论审查/假设条件与依据", "问题或风险": "...", "报告修改建议": "应补充或改写到报告中的内容", "解决方案": "...", "责任或材料": "...", "需补充的最新数据": "...", "建议数据来源": "...", "数据时效要求": "...", "核验状态": "需联网核验/需人工核验/报告内已列示"}}
  ],
  "漏项清单": ["..."],
  "IRR结论审查": {{
    "IRR数值": "...",
    "投资收益率": "...",
    "净利润": "...",
    "现金流口径": "...",
    "结论是否成立": "..."
  }},
  "假设条件与依据": [
    {{"假设条件": "...", "报告依据": "...", "证据强弱": "强/中/弱", "需补充材料": "..."}}
  ],
  "政策文件核验": [
    {{"政策名称": "...", "是否需要核验": "是"}}
  ],
  "需要补充的最新数据": [
    {{"数据名称": "...", "用途": "用于判断测算是否正确或修正 IRR", "建议来源": "...", "建议时点或频率": "...", "核验状态": "报告内已列示/需联网核验/需人工核验"}}
  ]
}}

报告关键原文：
{focused_text}
"""
    settings = get_settings()
    return await ask_ai_json(prompt, model=settings.economic_audit_model or settings.openai_model)


async def _apply_online_policy_verification(analysis: dict[str, Any]) -> None:
    audit = analysis.get("经济测算专项审查")
    if not isinstance(audit, dict):
        return
    refs = audit.get("政策文件核验")
    if not isinstance(refs, list):
        return
    normalized = [ref for ref in refs if isinstance(ref, dict)]
    if not normalized:
        return
    verified = await verify_policy_refs_online(normalized)
    audit["政策文件核验"] = _simplify_policy_verification(verified)
    audit["政策联网核验说明"] = "后端已按政策名称/文号进行独立联网检索；客户展示仅保留政策名称和是否需要核验。"


def _simplify_policy_verification(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    simplified: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        name = str(item.get("政策名称", "")).strip() or "未命名政策"
        if name in seen:
            continue
        seen.add(name)
        status = str(item.get("联网核验状态", ""))
        simplified.append(
            {
                "政策名称": name,
                "是否需要核验": "否" if "找到官方候选" in status else "是",
            }
        )
    return simplified


def _sanitize_analysis(value: Any) -> Any:
    if isinstance(value, dict):
        for key, item in list(value.items()):
            value[key] = _sanitize_analysis(item)
        return value
    if isinstance(value, list):
        return [_sanitize_analysis(item) for item in value]
    if isinstance(value, str):
        cleaned = re.sub(r"\[Heading(?:\s+\d+)?\]\s*", "", value)
        cleaned = cleaned.replace("", "；")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned
    return value


def _add_output_integrity_check(analysis: dict[str, Any]) -> None:
    issues: list[str] = []
    for section in [
        "标准摘要",
        "报告修改建议与解决方案",
        "最新数据补充与核验清单",
        "同类企业对比与业务建议",
        "经济测算专项审查",
        "精读结论",
    ]:
        if not analysis.get(section):
            issues.append(f"AI 输出缺少“{section}”。")

    audit = analysis.get("经济测算专项审查")
    if isinstance(audit, dict):
        expected = _expected_solution_sections(audit)
        covered = _covered_solution_sections(audit.get("具体解决方案"))
        missing = sorted(expected - covered)
        if missing:
            issues.append("经济测算专项审查的具体解决方案未覆盖：" + "、".join(missing))

        policies = audit.get("政策文件核验")
        if isinstance(policies, list):
            for index, item in enumerate(policies, start=1):
                if not isinstance(item, dict):
                    issues.append(f"政策文件核验第 {index} 项不是对象。")
                    continue
                allowed_keys = {"政策名称", "是否需要核验"}
                extra_keys = set(item) - allowed_keys
                if extra_keys:
                    issues.append(f"政策文件核验第 {index} 项含多余字段：" + "、".join(sorted(extra_keys)))

    analysis["输出完整性检查"] = {
        "是否完整": "否" if issues else "是",
        "需重新生成或人工补充的问题": issues,
    }


def _expected_solution_sections(audit: dict[str, Any]) -> set[str]:
    expected: set[str] = set()
    for section in [
        "财务测算结论",
        "经营模式审查",
        "税收审查",
        "测算错误与疑点",
        "漏项清单",
        "IRR结论审查",
        "假设条件与依据",
    ]:
        value = audit.get(section)
        if _has_meaningful_content(value):
            expected.add(section)
    return expected


def _covered_solution_sections(value: Any) -> set[str]:
    covered: set[str] = set()
    if not isinstance(value, list):
        return covered
    section_names = {
        "财务测算结论",
        "经营模式审查",
        "税收审查",
        "测算错误与疑点",
        "漏项清单",
        "IRR结论审查",
        "假设条件与依据",
    }
    for item in value:
        if not isinstance(item, dict):
            continue
        raw = str(item.get("对应审查项", ""))
        for section in section_names:
            if section in raw:
                covered.add(section)
    return covered


def _has_meaningful_content(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip() not in {"无", "无。"}
    if isinstance(value, list):
        return any(_has_meaningful_content(item) for item in value)
    if isinstance(value, dict):
        return any(_has_meaningful_content(item) for item in value.values())
    return True


def extract_policy_refs(text: str) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    pattern = re.compile(r"《([^》]{4,90})》(?:（([^）]{2,40})）)?")
    for match in pattern.finditer(text):
        name = match.group(1).strip()
        doc_no = match.group(2).strip() if match.group(2) else _near_doc_no(text, match.end())
        key = (name, doc_no)
        if key in seen:
            continue
        seen.add(key)
        refs.append(
            {
                "政策名称": name,
                "文号": doc_no,
                "报告引用位置": _context_snippet(text, match.start(), match.end(), 60),
            }
        )
        if len(refs) >= 12:
            break
    return refs


def extract_financial_metrics(text: str) -> dict[str, str]:
    terms = [
        "增值税",
        "所得税",
        "税金及附加",
        "关税",
        "政府补助",
        "服务收入",
        "服务费",
        "服务成本",
        "货站处置费",
        "资金成本",
        "贸易货款",
        "航班物流",
        "净利润",
        "利润总额",
        "投资收益率",
        "IRR",
    ]
    result: dict[str, str] = {}
    for term in terms:
        context = _find_first_context(text, [term])
        if context:
            result[term] = context
    return result


def _near_doc_no(text: str, pos: int) -> str:
    window = text[pos : pos + 50]
    match = re.search(r"([一-龥A-Za-z]{1,8}〔\d{4}〕\d+号)", window)
    return match.group(1) if match else ""


def _context_snippet(text: str, start: int, end: int, radius: int) -> str:
    return re.sub(r"\s+", " ", text[max(0, start - radius) : min(len(text), end + radius)]).strip()


def _find_first_context(text: str, terms: list[str]) -> str:
    for term in terms:
        match = re.search(re.escape(term), text, flags=re.I)
        if match:
            return _context_snippet(text, match.start(), match.end(), 90)
    return ""


def _focused_audit_text(text: str) -> str:
    terms = [
        "主营业务模式",
        "业务主体、模式",
        "经营效益分析",
        "投资测算原则",
        "基本假设",
        "业务收益测算",
        "增值税",
        "所得税",
        "税金及附加",
        "政府补助",
        "服务收入",
        "服务成本",
        "资金成本",
        "IRR",
        "投资收益率",
        "政策措施",
        "商贸发",
        "成商务",
    ]
    snippets: list[str] = []
    ranges: list[tuple[int, int]] = []
    for term in terms:
        match = re.search(re.escape(term), text, flags=re.I)
        if not match:
            continue
        start = max(0, match.start() - 800)
        end = min(len(text), match.end() + 1800)
        if any(not (end < prev_start or start > prev_end) for prev_start, prev_end in ranges):
            continue
        ranges.append((start, end))
        snippets.append(text[start:end])
    focused = "\n\n--- 摘录分隔 ---\n\n".join(snippets)
    return focused[:18000] if focused else text[:18000]
