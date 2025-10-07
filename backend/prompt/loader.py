"""
提示词加载器：按模型档位从本目录加载提示词模板。

约定每个提示词模块导出以下常量（至少第一个）：
- TOOLS_SYSTEM_PROMPT_TEMPLATE: str  用于工具判定阶段的系统提示词模板
- STREAM_SYSTEM_PROMPT_TEMPLATE: str 可选；用于纯流式回答的系统提示词模板

文件命名：LLM_<PROFILE_ID_UPPER>_PROMPT.py
若缺失，回退到 LLM_DEFAULT_PROMPT.py
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Dict


def _load_module_from_path(module_path: Path):
    if not module_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(module_path.stem, str(module_path))
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_prompts(profile_id: str | None) -> Dict[str, str]:
    """
    加载指定档位的提示词模板，返回字典：
    {
      "tools_system_prompt_template": str,
      "stream_system_prompt_template": str
    }
    若指定档位不存在，则回退到 DEFAULT。
    若均不存在，返回最小兜底模板。
    """
    base_dir = Path(__file__).parent
    candidates = []
    if profile_id:
        candidates.append(base_dir / f"LLM_{profile_id.upper()}_PROMPT.py")
    candidates.append(base_dir / "LLM_DEFAULT_PROMPT.py")

    module = None
    for path in candidates:
        module = _load_module_from_path(path)
        if module is not None:
            break

    if module is None:
        # 最小兜底
        return {
            "tools_system_prompt_template": (
                "Today is {current_date} ({current_weekday}). You are Dolphin Data Insight Agent.\n"
                "Default to no tool calls. Only call tools when necessary."
            ),
            "stream_system_prompt_template": "",
        }

    # 兼容两种命名
    tools = getattr(module, "TOOLS_SYSTEM_PROMPT_TEMPLATE", None) or getattr(module, "TOOLS_SYSTEM_PROMPT", None) or ""
    stream = getattr(module, "STREAM_SYSTEM_PROMPT_TEMPLATE", None) or getattr(module, "STREAM_SYSTEM_PROMPT", None) or ""

    return {
        "tools_system_prompt_template": str(tools),
        "stream_system_prompt_template": str(stream),
    }


