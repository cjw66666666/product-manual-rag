import json
import os
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import pymupdf


@dataclass(frozen=True, slots=True)
class Topic:
    keyword: str
    question: str


@dataclass(frozen=True, slots=True)
class ProductSource:
    product_id: str
    category: str
    filename: str
    topics: tuple[Topic, ...]


PRODUCTS = (
    ProductSource(
        "huawei_c7",
        "tablet",
        "华为平板 C7 用户指南-(DBY-W09,HarmonyOS 2_01,ZH-CN).pdf",
        (
            Topic("开机", "华为平板 C7 如何开机？"),
            Topic("充电", "华为平板 C7 如何充电？"),
            Topic("蓝牙", "华为平板 C7 如何连接蓝牙设备？"),
            Topic("WLAN", "华为平板 C7 如何连接无线网络？"),
            Topic("截屏", "华为平板 C7 如何截屏？"),
            Topic("安全", "使用华为平板 C7 时有哪些安全注意事项？"),
            Topic("应用", "华为平板 C7 如何查看和使用应用？"),
            Topic("恢复出厂", "华为平板 C7 如何恢复出厂设置？"),
            Topic("电池", "华为平板 C7 的电池使用注意事项是什么？"),
            Topic("计算机", "华为平板 C7 如何连接计算机？"),
        ),
    ),
    ProductSource(
        "huawei_c5e_gen4",
        "tablet",
        "华为擎云 C5 (第4代) 用户指南-(BYD5-W10&AL10,HarmonyOS 4.3_01,zh-cn).pdf",
        (
            Topic("开机", "华为擎云 C5 第4代如何开机？"),
            Topic("充电", "华为擎云 C5 第4代如何充电？"),
            Topic("蓝牙", "华为擎云 C5 第4代如何连接蓝牙设备？"),
            Topic("WLAN", "华为擎云 C5 第4代如何连接无线网络？"),
            Topic("截屏", "华为擎云 C5 第4代如何截屏？"),
            Topic("安全", "使用华为擎云 C5 第4代时有哪些安全注意事项？"),
            Topic("维护", "华为擎云 C5 第4代应如何维护？"),
            Topic("恢复出厂", "华为擎云 C5 第4代如何恢复出厂设置？"),
            Topic("电池", "华为擎云 C5 第4代的电池使用注意事项是什么？"),
            Topic("USB", "华为擎云 C5 第4代有哪些 USB 相关说明？"),
        ),
    ),
    ProductSource(
        "huawei_b5_440",
        "laptop",
        "HUAWEI MateBook B5-440 用户指南-(KLVFZ,Windows11_02,zh-cn).pdf",
        (
            Topic("开机", "HUAWEI MateBook B5-440 如何开机？"),
            Topic("电源", "HUAWEI MateBook B5-440 的电源注意事项是什么？"),
            Topic("键盘", "HUAWEI MateBook B5-440 的键盘有哪些功能？"),
            Topic("触摸板", "HUAWEI MateBook B5-440 如何使用触摸板？"),
            Topic("音量", "HUAWEI MateBook B5-440 如何调节音量？"),
            Topic("USB", "HUAWEI MateBook B5-440 有哪些 USB 接口？"),
            Topic("安全", "使用 HUAWEI MateBook B5-440 时有哪些安全注意事项？"),
            Topic("清洁", "HUAWEI MateBook B5-440 应如何清洁？"),
            Topic("电池", "HUAWEI MateBook B5-440 的电池如何维护？"),
            Topic("无线", "HUAWEI MateBook B5-440 如何连接无线网络？"),
        ),
    ),
    ProductSource(
        "huawei_hm740",
        "laptop",
        "华为擎云 HM740 用户指南-(HM740-001&031,HarmonyOS 6.0_01,zh-cn).pdf",
        (
            Topic("开机", "华为擎云 HM740 如何开机？"),
            Topic("电源", "华为擎云 HM740 的电源注意事项是什么？"),
            Topic("键盘", "华为擎云 HM740 的键盘有哪些功能？"),
            Topic("设置", "华为擎云 HM740 如何打开系统设置？"),
            Topic("摄像头", "华为擎云 HM740 如何使用摄像头？"),
            Topic("USB", "华为擎云 HM740 有哪些 USB 接口？"),
            Topic("安全", "使用华为擎云 HM740 时有哪些安全注意事项？"),
            Topic("接口", "华为擎云 HM740 有哪些接口？"),
            Topic("电池", "华为擎云 HM740 的电池如何维护？"),
            Topic("无线", "华为擎云 HM740 如何连接无线网络？"),
        ),
    ),
    ProductSource(
        "huawei_b5_341w",
        "monitor",
        "华为显示器 B5-341W 用户指南-(ZQE-CBA,04,zh-cn).pdf",
        (
            Topic("HDMI", "华为显示器 B5-341W 如何连接 HDMI 设备？"),
            Topic("DP", "华为显示器 B5-341W 如何连接 DP 设备？"),
            Topic("亮度", "华为显示器 B5-341W 如何调节亮度？"),
            Topic("OSD", "华为显示器 B5-341W 的 OSD 菜单如何操作？"),
            Topic("高度", "华为显示器 B5-341W 如何调节高度？"),
            Topic("角度", "华为显示器 B5-341W 如何调节观看角度？"),
            Topic("清洁", "华为显示器 B5-341W 应如何清洁？"),
            Topic("电源", "华为显示器 B5-341W 的电源要求是什么？"),
            Topic("安全", "使用华为显示器 B5-341W 时有哪些安全注意事项？"),
            Topic("恢复出厂", "华为显示器 B5-341W 如何恢复出厂设置？"),
        ),
    ),
    ProductSource(
        "huawei_m272q",
        "monitor",
        "华为擎云 M272Q 用户指南-(XSN-27QBZ,02,zh-cn).pdf",
        (
            Topic("HDMI", "华为擎云 M272Q 如何连接 HDMI 设备？"),
            Topic("DP", "华为擎云 M272Q 如何连接 DP 设备？"),
            Topic("VGA", "华为擎云 M272Q 是否支持 VGA 接口？"),
            Topic("OSD", "华为擎云 M272Q 的 OSD 菜单如何操作？"),
            Topic("高度", "华为擎云 M272Q 如何调节高度？"),
            Topic("旋转", "华为擎云 M272Q 如何旋转屏幕？"),
            Topic("清洁", "华为擎云 M272Q 应如何清洁？"),
            Topic("电源", "华为擎云 M272Q 的电源要求是什么？"),
            Topic("安全", "使用华为擎云 M272Q 时有哪些安全注意事项？"),
            Topic("恢复出厂", "华为擎云 M272Q 如何恢复出厂设置？"),
        ),
    ),
)


def snippet(text: str, keyword: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    index = normalized.casefold().find(keyword.casefold())
    if index < 0:
        raise ValueError(f"keyword not found: {keyword}")
    start = max(0, index - 80)
    end = min(len(normalized), index + len(keyword) + 120)
    return normalized[start:end]


def find_evidence(
    document: Any,
    keyword: str,
) -> tuple[int, str]:
    candidates: list[tuple[int, int, str]] = []
    for page_number, page in enumerate(document, start=1):
        if page_number <= 5:
            continue
        text = page.get_text("text")
        count = text.casefold().count(keyword.casefold())
        if count:
            candidates.append((count, page_number, text))
    if candidates:
        _, page_number, text = max(
            candidates,
            key=lambda item: (item[0], item[1]),
        )
        return page_number, snippet(text, keyword)
    raise ValueError(f"keyword not found in PDF: {keyword}")


def build_case(
    source: ProductSource,
    document: pymupdf.Document,
    document_sha256: str,
    index: int,
) -> dict[str, object]:
    topic = source.topics[index]
    try:
        page, evidence = find_evidence(document, topic.keyword)
    except ValueError as exc:
        raise ValueError(
            f"{source.product_id} missing keyword: {topic.keyword}"
        ) from exc
    return {
        "case_id": f"{source.product_id}-{index + 1:03d}",
        "dataset_version": "v0-seed",
        "split": "dev" if index < 5 else "test",
        "product_id": source.product_id,
        "category": source.category,
        "messages": [topic.question],
        "expected_mode": "manual_grounded",
        "must_cite": [
            {
                "document_sha256": document_sha256,
                "page": page,
                "section_path": [],
                "evidence_quote": evidence,
            }
        ],
        "required_facts": [topic.keyword],
        "forbidden_claims": [],
        "reference_answer": f"依据手册：{evidence}",
        "tags": [source.category, topic.keyword],
    }


def main() -> int:
    doc_root = Path(
        os.environ.get(
            "DOC_SOURCE_ROOT",
            r"D:\1\项目汇总\Rag项目\PythonProject16\doc",
        )
    )
    output_root = Path("datasets/eval/v0")
    output_root.mkdir(parents=True, exist_ok=True)
    dev_cases: list[dict[str, object]] = []
    test_cases: list[dict[str, object]] = []

    for source in PRODUCTS:
        path = doc_root / source.filename
        content = path.read_bytes()
        digest = sha256(content).hexdigest()
        with pymupdf.open(path) as document:  # type: ignore[no-untyped-call]
            for index in range(len(source.topics)):
                case = build_case(source, document, digest, index)
                target = dev_cases if case["split"] == "dev" else test_cases
                target.append(case)

    for filename, cases in (
        ("dev.jsonl", dev_cases),
        ("test.jsonl", test_cases),
    ):
        with (output_root / filename).open("w", encoding="utf-8") as stream:
            for case in cases:
                stream.write(json.dumps(case, ensure_ascii=False) + "\n")

    print(
        f"generated {len(dev_cases)} dev and {len(test_cases)} test cases"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
