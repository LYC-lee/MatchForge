"""
型号正则提取工具
从用户输入中识别常见元器件型号 pattern
"""

from __future__ import annotations

import re
from typing import Optional

# 常见元器件型号正则
PART_PATTERNS = [
    # Taiyo Yuden MLCC (TMK212BJ105KG-T)
    (r'\bTMK\d+[A-Za-z0-9\-]+', 'Taiyo Yuden'),
    # Murata MLCC (GRM188R61A106KE69D)
    (r'\bGRM\d+[A-Za-z0-9]+', 'Murata'),
    # YAGEO MLCC (CC0805KKX7R9BB106)
    (r'\bCC\d+[A-Za-z0-9]+', 'YAGEO'),
    # Walsin MLCC (0805F105Z500NT)
    (r'\b\d{4}[A-Z]\d+[A-Za-z0-9]+', 'Walsin'),
    # Samsung MLCC (CL05A106MQ5NUNC)
    (r'\bCL\d+[A-Za-z0-9]+', 'Samsung'),
    # TDK MLCC (C1005X5R1A106K)
    (r'\bC\d{4}[A-Za-z0-9]+', 'TDK'),
    # AVX / KEMET 通用
    (r'\b[A-Z]{2,4}\d{2,4}[A-Z][A-Za-z0-9]+', 'Unknown'),
]


def extract_part_number(text: str) -> Optional[str]:
    """
    从用户输入中提取型号

    返回: 匹配到的型号字符串，未匹配返回 None
    """
    for pattern, _ in PART_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


def extract_part_number_with_brand(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    从用户输入中提取型号和品牌

    返回: (型号, 品牌推断)
    """
    for pattern, brand in PART_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(0), brand
    return None, None


def validate_package(pkg: str) -> bool:
    """校验封装是否为合法值"""
    valid = {"01005", "0201", "0402", "0603", "0805", "1206", "1210",
             "1808", "1812", "2010", "2220", "2512", "2520", "3216"}
    return pkg.strip() in valid


def validate_temp_coeff(tc: str) -> bool:
    """校验温度系数是否为合法值"""
    valid = {"X5R", "X7R", "X8R", "X8L", "C0G", "NP0", "Y5V", "Z5U", "X6S", "X7S"}
    return tc.strip().upper() in valid