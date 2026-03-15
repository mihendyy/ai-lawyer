"""Запрос к AiTunnel (OpenAI API): анализ договора → BPMN-JSON и/или Mermaid + рекомендации."""
import json
import re
from typing import Optional, Tuple
from openai import OpenAI

from config import AI_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL
from prompts import (
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_BRIEF,
    SYSTEM_PROMPT_MERMAID,
    SYSTEM_PROMPT_MERMAID_WITH_RECOMMENDATIONS,
    SYSTEM_PROMPT_RISKS,
    SYSTEM_PROMPT_UPDATE_BPMN,
    user_prompt,
    user_prompt_brief,
    user_prompt_mermaid,
    user_prompt_mermaid_with_recommendations,
    user_prompt_risks,
    user_prompt_update_bpmn,
)
from bpmn_schema import validate_bpmn_data


def _extract_json_block(content: str) -> str:
    """Достаёт блок между ---JSON--- и следующим ---."""
    if "---JSON---" not in content:
        return ""
    _, rest = content.split("---JSON---", 1)
    # Берём до следующего маркера --- или ---РЕКОМЕНДАЦИИ---
    part = rest.split("---")[0].strip()
    # Убираем обёртку ```json ... ``` если есть
    if part.startswith("```"):
        part = re.sub(r"^```\w*\n?", "", part)
    if part.endswith("```"):
        part = part.rsplit("```", 1)[0].strip()
    return part


def _extract_recommendations(content: str) -> str:
    """Извлекает блок РЕКОМЕНДАЦИИ."""
    if "---РЕКОМЕНДАЦИИ---" not in content:
        return ""
    _, rest = content.split("---РЕКОМЕНДАЦИИ---", 1)
    return rest.split("---")[0].strip()


def _extract_mermaid_fallback(content: str) -> str:
    """Пытается найти код Mermaid в ответе (для fallback)."""
    if "```" in content:
        parts = content.split("```")
        for p in parts:
            p = p.strip()
            if ("flowchart" in p or "graph " in p) and "mermaid" not in p.lower().split("\n")[0]:
                code = p.split("\n", 1)[-1] if "\n" in p else p
                code = re.sub(r"^mermaid\s*\n?", "", code, flags=re.I).strip()
                for marker in ("---MERMAID---", "---РЕКОМЕНДАЦИИ---", "---JSON---"):
                    if marker in code:
                        code = code.split(marker)[0].strip().rstrip(";")
                if code:
                    return code
    return ""


def _parse_response(content: str) -> Tuple[Optional[dict], str, str]:
    """
    Парсит ответ модели.
    Возвращает (bpmn_data или None, рекомендации, mermaid_код для fallback).
    """
    recommendations = _extract_recommendations(content) or "Рекомендации не сформированы."
    json_str = _extract_json_block(content)
    bpmn_data = None

    if json_str:
        try:
            data = json.loads(json_str)
            if validate_bpmn_data(data):
                bpmn_data = data
        except (json.JSONDecodeError, TypeError):
            pass

    mermaid_fallback = _extract_mermaid_fallback(content) if not bpmn_data else ""

    return (bpmn_data, recommendations, mermaid_fallback)


def analyze_contract(contract_text: str) -> Tuple[Optional[dict], str, str]:
    """
    Отправляет текст договора в модель.
    Возвращает (bpmn_data или None, recommendations, mermaid_fallback).
    """
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY не задан в окружении")

    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt(contract_text)},
        ],
        max_tokens=4000,
    )

    content = response.choices[0].message.content or ""
    return _parse_response(content)


def analyze_contract_mermaid_fallback(contract_text: str) -> str:
    """Отдельный запрос только за Mermaid-схемой (если BPMN не удалось получить)."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY не задан в окружении")
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_MERMAID},
            {"role": "user", "content": user_prompt_mermaid(contract_text)},
        ],
        max_tokens=2000,
    )
    content = response.choices[0].message.content or ""
    for marker in ("---MERMAID---", "---РЕКОМЕНДАЦИИ---", "---JSON---"):
        if marker in content:
            content = content.split(marker)[0].strip().rstrip(";")
    if content.startswith("```"):
        content = re.sub(r"^```\w*\n?", "", content)
    if content.lower().startswith("mermaid"):
        content = content[6:].strip()
    return content.strip()


def _extract_mermaid_block(content: str) -> str:
    """Извлекает блок между ---MERMAID--- и следующим ---."""
    if "---MERMAID---" not in content:
        return ""
    _, rest = content.split("---MERMAID---", 1)
    part = rest.split("---")[0].strip()
    for marker in ("---РЕКОМЕНДАЦИИ---", "---JSON---"):
        if marker in part:
            part = part.split(marker)[0].strip()
    if part.startswith("```"):
        part = re.sub(r"^```\w*\n?", "", part)
    if part.endswith("```"):
        part = part.rsplit("```", 1)[0].strip()
    if part.lower().startswith("mermaid"):
        part = part[6:].strip()
    return part.rstrip("; \t")


def analyze_contract_mermaid_only(contract_text: str) -> tuple[str, str]:
    """
    Один запрос: только Mermaid + рекомендации (режим «схема Mermaid»).
    Возвращает (mermaid_code, recommendations).
    """
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY не задан в окружении")
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_MERMAID_WITH_RECOMMENDATIONS},
            {"role": "user", "content": user_prompt_mermaid_with_recommendations(contract_text)},
        ],
        max_tokens=4000,
    )
    content = response.choices[0].message.content or ""
    mermaid = _extract_mermaid_block(content)
    recommendations = _extract_recommendations(content) or "Рекомендации не сформированы."
    return (mermaid, recommendations)


def update_bpmn_from_correction(
    contract_text: str, bpmn_data: dict, user_correction: str
) -> Optional[dict]:
    """
    Обновляет BPMN с учётом текстовой правки пользователя (не regenerate).
    Возвращает новый bpmn_data или None при ошибке.
    """
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY не задан в окружении")
    bpmn_json_str = json.dumps(bpmn_data, ensure_ascii=False, indent=2)
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_UPDATE_BPMN},
            {"role": "user", "content": user_prompt_update_bpmn(contract_text, bpmn_json_str, user_correction)},
        ],
        max_tokens=4000,
    )
    content = response.choices[0].message.content or ""
    json_str = _extract_json_block(content)
    if not json_str:
        return None
    try:
        data = json.loads(json_str)
        if validate_bpmn_data(data):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def get_contract_brief(contract_text: str) -> str:
    """Кратко о договоре: о чём, стороны, логика процесса, основные блоки."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY не задан в окружении")
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_BRIEF},
            {"role": "user", "content": user_prompt_brief(contract_text)},
        ],
        max_tokens=2000,
    )
    return (response.choices[0].message.content or "").strip()


def get_contract_risks(contract_text: str) -> str:
    """Ключевые риски: название, объяснение, возможное улучшение по каждому."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY не задан в окружении")
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_RISKS},
            {"role": "user", "content": user_prompt_risks(contract_text)},
        ],
        max_tokens=2000,
    )
    return (response.choices[0].message.content or "").strip()
