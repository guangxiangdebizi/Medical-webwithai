"""
模型档位管理模块
"""

import os
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI


class ModelManager:
    """模型档位管理器"""
    
    def __init__(self):
        self.llm_profiles = self._load_llm_profiles_from_env()
        self.default_profile_id = os.getenv("LLM_DEFAULT", "default").strip() or "default"
        if self.default_profile_id not in self.llm_profiles:
            self.default_profile_id = "default"
        self._llm_cache: Dict[str, Dict[str, Any]] = {}
        
        # 数值配置，带默认
        try:
            self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
        except Exception:
            self.temperature = 0.2
        try:
            self.timeout = int(os.getenv("OPENAI_TIMEOUT", "60"))
        except Exception:
            self.timeout = 60
        
        # 基础模型配置
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "").strip()
        self.model_name = os.getenv("OPENAI_MODEL", os.getenv("OPENAI_MODEL_NAME", "deepseek-chat")).strip()

    def _load_llm_profiles_from_env(self) -> Dict[str, Dict[str, Any]]:
        """从环境变量解析多模型档位配置。
        约定：
        - LLM_PROFILES=profile1,profile2
        - 每个档位变量：
          LLM_<ID>_LABEL、LLM_<ID>_API_KEY、LLM_<ID>_BASE_URL、LLM_<ID>_MODEL、
          （可选）LLM_<ID>_TEMPERATURE、LLM_<ID>_TIMEOUT
        - 同时提供一个向后兼容的 default 档位，来自 OPENAI_* 变量
        """
        profiles: Dict[str, Dict[str, Any]] = {}

        # default 档位（向后兼容现有 OPENAI_*）
        profiles["default"] = {
            "id": "default",
            "label": os.getenv("LLM_DEFAULT_LABEL", "Default"),
            "api_key": os.getenv("OPENAI_API_KEY", "").strip(),
            "base_url": os.getenv("OPENAI_BASE_URL", "").strip(),
            "model": os.getenv("OPENAI_MODEL", os.getenv("OPENAI_MODEL_NAME", "deepseek-chat")).strip(),
            "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
            "timeout": int(os.getenv("OPENAI_TIMEOUT", "60")),
        }

        ids_raw = os.getenv("LLM_PROFILES", "").strip()
        if ids_raw:
            for pid in [x.strip() for x in ids_raw.split(",") if x.strip()]:
                key = f"LLM_{pid.upper()}_API_KEY"
                model_key = f"LLM_{pid.upper()}_MODEL"
                # 没有 api_key 或 model 的跳过
                api_key = os.getenv(key, "").strip()
                model_name = os.getenv(model_key, "").strip()
                if not api_key or not model_name:
                    continue
                base_url = os.getenv(f"LLM_{pid.upper()}_BASE_URL", "").strip()
                label = os.getenv(f"LLM_{pid.upper()}_LABEL", pid)
                try:
                    temperature = float(os.getenv(f"LLM_{pid.upper()}_TEMPERATURE", os.getenv("OPENAI_TEMPERATURE", "0.2")))
                except Exception:
                    temperature = 0.2
                try:
                    timeout = int(os.getenv(f"LLM_{pid.upper()}_TIMEOUT", os.getenv("OPENAI_TIMEOUT", "60")))
                except Exception:
                    timeout = 60
                profiles[pid] = {
                    "id": pid,
                    "label": label,
                    "api_key": api_key,
                    "base_url": base_url,
                    "model": model_name,
                    "temperature": temperature,
                    "timeout": timeout,
                }

        return profiles

    def get_models_info(self) -> Dict[str, Any]:
        """对外暴露的模型档位信息（用于前端展示）。"""
        profiles = self.llm_profiles or {}
        ids = list(profiles.keys())
        non_default_ids = [pid for pid in ids if pid != "default"]

        # 计算有效默认档位：优先采用 LLM_DEFAULT 指定且存在的ID；
        # 否则若存在非 default 档位，取第一个；否则只能是 default（单模型旧兼容）
        if self.default_profile_id and self.default_profile_id != "default" and self.default_profile_id in profiles:
            effective_default = self.default_profile_id
        elif non_default_ids:
            effective_default = non_default_ids[0]
        else:
            effective_default = "default"

        # 展示策略：
        # - 若存在任意非 default 档位，则完全隐藏 default（它只作为别名/回退，不单独显示）。
        # - 若只有 default 一个档位，则显示它（旧版单模型场景）。
        show_ids = non_default_ids if non_default_ids else (["default"] if "default" in profiles else [])

        models = []
        for pid in show_ids:
            cfg = profiles.get(pid, {})
            models.append({
                "id": pid,
                "label": cfg.get("label", pid),
                "model": cfg.get("model", ""),
                "is_default": pid == effective_default,
            })

        # 极端兜底：如果最终一个都没有（理论不会发生），返回空列表与默认ID
        return {"models": models, "default": effective_default}

    def get_current_model_key(self, session_contexts: Dict[str, Dict[str, Any]], session_id: Optional[str] = None) -> str:
        """获取当前会话使用的模型标识（用于记录多模态支持情况）"""
        try:
            profile_id = None
            if session_id and session_contexts.get(session_id):
                profile_id = session_contexts[session_id].get("model") or session_contexts[session_id].get("llm_profile")
            if not profile_id:
                profile_id = self.default_profile_id
            cfg = self.llm_profiles.get(profile_id, {})
            model_name = cfg.get("model", "")
            base_url = cfg.get("base_url", "")
            return f"{model_name}@{base_url}"
        except Exception:
            return "unknown"

    def get_or_create_llm_instances(self, profile_id: str, tools: list) -> Dict[str, Any]:
        """根据档位获取/创建对应的 LLM 实例集合：llm、llm_nontool、llm_tools。"""
        pid = profile_id or self.default_profile_id
        if pid not in self.llm_profiles:
            pid = self.default_profile_id

        if pid in self._llm_cache:
            return self._llm_cache[pid]

        cfg = self.llm_profiles[pid]

        # 临时切换环境变量，构造实例
        prev_key = os.getenv("OPENAI_API_KEY")
        prev_base = os.getenv("OPENAI_BASE_URL")
        try:
            if cfg.get("api_key"):
                os.environ["OPENAI_API_KEY"] = cfg["api_key"]
            if cfg.get("base_url"):
                os.environ["OPENAI_BASE_URL"] = cfg["base_url"]

            base_llm = ChatOpenAI(
                model=cfg.get("model", self.model_name),
                temperature=cfg.get("temperature", self.temperature),
                timeout=cfg.get("timeout", self.timeout),
                max_retries=3,
            )
            llm_nontool = ChatOpenAI(
                model=cfg.get("model", self.model_name),
                temperature=cfg.get("temperature", self.temperature),
                timeout=cfg.get("timeout", self.timeout),
                max_retries=3,
            )
            llm_tools = base_llm.bind_tools(tools)
        finally:
            # 还原环境，避免影响其他逻辑
            if prev_key is not None:
                os.environ["OPENAI_API_KEY"] = prev_key
            if prev_base is not None:
                os.environ["OPENAI_BASE_URL"] = prev_base

        bundle = {"llm": base_llm, "llm_nontool": llm_nontool, "llm_tools": llm_tools}
        self._llm_cache[pid] = bundle
        return bundle
