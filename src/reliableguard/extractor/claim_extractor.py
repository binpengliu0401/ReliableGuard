from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

from src.config.runtime_config import OPENROUTER_BASE_URL, QWEN_PLUS_MODEL
from src.reliableguard.extractor.prompts import build_claim_extraction_prompt
from src.reliableguard.schema import Claim


def extract_claims(
    domain: str,
    query: str,
    agent_answer: str,
    *,
    model: str = QWEN_PLUS_MODEL,
    base_url: str = OPENROUTER_BASE_URL,
) -> list[Claim]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        try:
            return _extract_with_llm(domain, query, agent_answer, model=model, base_url=base_url)
        except Exception as exc:
            print(f"[CLAIM_EXTRACTOR] Falling back to heuristic extraction: {exc}")
    return _extract_with_heuristics(domain, agent_answer)


def _extract_with_llm(
    domain: str,
    query: str,
    agent_answer: str,
    *,
    model: str,
    base_url: str,
) -> list[Claim]:
    client = OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=build_claim_extraction_prompt(domain, query, agent_answer), # type: ignore
        temperature=0,
    )
    content = response.choices[0].message.content or "{}"
    payload = _load_json_object(content)
    return [
        Claim(**item)
        for item in payload.get("claims", [])
        if isinstance(item, dict) and item.get("text")
    ]


def _load_json_object(content: str) -> dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?", "", content).strip()
        content = re.sub(r"```$", "", content).strip()
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end >= start:
        content = content[start : end + 1]
    return json.loads(content)


def _extract_with_heuristics(domain: str, agent_answer: str) -> list[Claim]:
    claims: list[Claim] = []
    text = agent_answer or ""

    def add(claim_type: str, claim_text: str, **kwargs: Any) -> None:
        claims.append(
            Claim(
                claim_id=f"c{len(claims) + 1}",
                text=claim_text,
                claim_type=claim_type,  # type: ignore[arg-type]
                **kwargs,
            )
        )

    if domain == "ecommerce":
        for order_id, status in re.findall(r"order[_\s-]?(\d+).*?(pending|confirmed|refunded|paid)", text, re.I):
            add(
                "attribute",
                f"Order {order_id} status is {status}",
                entities={"order_id": int(order_id)},
                attribute="status",
                value=status.lower(),
            )
        for order_id, amount in re.findall(r"order[_\s-]?(\d+).*?(?:amount|金额).*?(\d+(?:\.\d+)?)", text, re.I):
            add(
                "numeric",
                f"Order {order_id} amount is {amount}",
                entities={"order_id": int(order_id)},
                attribute="amount",
                value=float(amount),
            )
    elif domain == "reference":
        for raw_doi in re.findall(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", text, re.I):
            doi = raw_doi.rstrip(".,;:)")
            add(
                "existence",
                f"DOI {doi} exists",
                entities={"doi": doi},
                attribute="doi",
                value=doi,
            )
        for ref_id, status in re.findall(r"ref(?:erence)?[_\s-]?(\d+).*?(verified|failed|pending)", text, re.I):
            add(
                "attribute",
                f"Reference {ref_id} DOI status is {status}",
                entities={"ref_id": int(ref_id)},
                attribute="doi_status",
                value=status.lower(),
            )

    if not claims and text.strip():
        add(
            "semantic",
            text.strip()[:500],
            entities={},
            attribute=None,
            value=text.strip()[:500],
            confidence=0.5,
        )
    return claims
