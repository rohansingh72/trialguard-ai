from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import MessagesState, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agents.tools import build_investigation_tools
from app.services.data_store import TrialDataStore


SYSTEM_PROMPT = """You are TrialGuard AI, a read-only clinical-trial data quality investigation assistant.

Rules:
1. Use the supplied deterministic tools for factual claims about trial data.
2. Never invent records, values, dates, findings, or clinical conclusions.
3. For narrow questions, call the minimum QC tools needed to answer the question.
4. Clearly separate deterministic QC findings from your explanation.
5. Do not modify trial data. Do not claim that a finding is a confirmed clinical error; describe it as a data-quality finding requiring human review.
6. If tools return no finding, say that no issue was detected by the currently implemented rules. Do not imply the data are globally error-free.
7. Do not reinterpret laboratory test codes or values beyond what the deterministic finding states.
8. End with a concise human-review recommendation when a finding exists.
"""

BROAD_SUMMARY_PROMPT = """You are TrialGuard AI. Summarize ONLY the deterministic QC findings supplied below.

Strict rules:
- Do not infer any additional diagnosis, laboratory interpretation, clinical significance, or data problem.
- Do not rename tests, measurements, domains, or findings.
- Use the rule ID, title, description, and evidence exactly as the factual basis.
- If a QC domain has zero findings, you may say that the currently implemented rules found no issue in that domain.
- Never say the data are error-free.
- Describe findings as data-quality findings requiring human review, not confirmed clinical errors.
- Be concise and structured.
"""


BROAD_REVIEW_TOOL_NAMES = [
    "get_subject_overview",
    "review_adverse_events",
    "review_labs",
    "review_exposure",
    "review_demographics",
]


def _is_broad_investigation(question: str) -> bool:
    q = question.lower()
    broad_phrases = (
        "investigate this subject",
        "investigate subject",
        "possible data-quality issues",
        "possible data quality issues",
        "data-quality issues",
        "data quality issues",
        "full review",
        "complete review",
        "overall review",
        "all issues",
    )
    return any(phrase in q for phrase in broad_phrases)


def _run_broad_qc(store: TrialDataStore, subject_id: str) -> tuple[dict[str, Any], list[str]]:
    tools = {tool.name: tool for tool in build_investigation_tools(store)}

    # Overview is intentionally reduced to presence/counts before it reaches the LLM.
    # Raw clinical rows are not used for free-form interpretation.
    overview = tools["get_subject_overview"].invoke({"subject_id": subject_id})
    safe_overview = {
        "subject_id": subject_id,
        "record_counts": {
            "DM": len(overview.get("DM", [])),
            "AE": len(overview.get("AE", [])),
            "LB": len(overview.get("LB", [])),
            "EX": len(overview.get("EX", [])),
        },
    }

    evidence: dict[str, Any] = {"overview": safe_overview, "qc": {}}
    for tool_name in BROAD_REVIEW_TOOL_NAMES[1:]:
        evidence["qc"][tool_name] = tools[tool_name].invoke({"subject_id": subject_id})

    return evidence, BROAD_REVIEW_TOOL_NAMES.copy()


def _build_model() -> ChatOllama:
    return ChatOllama(
        model=os.getenv("TRIALGUARD_OLLAMA_MODEL", "llama3.2:3b"),
        base_url=os.getenv("TRIALGUARD_OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        temperature=0,
    )


def build_investigation_graph(store: TrialDataStore):
    tools = build_investigation_tools(store)
    model_with_tools = _build_model().bind_tools(tools)

    def call_model(state: MessagesState):
        response = model_with_tools.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        )
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("agent", call_model)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")

    return builder.compile()


def _summarize_broad_evidence(
    subject_id: str,
    question: str,
    evidence: dict[str, Any],
) -> str:
    model = _build_model()
    payload = json.dumps(evidence, indent=2, default=str)
    response = model.invoke(
        [
            SystemMessage(content=BROAD_SUMMARY_PROMPT),
            HumanMessage(
                content=(
                    f"Subject ID: {subject_id}\n"
                    f"Question: {question}\n\n"
                    "Deterministic evidence:\n"
                    f"{payload}"
                )
            ),
        ]
    )
    content = response.content
    if isinstance(content, list):
        return "\n".join(str(item) for item in content)
    return str(content)


def run_investigation(
    store: TrialDataStore,
    subject_id: str,
    question: str,
) -> dict[str, Any]:
    # Broad subject-level QC must cover all implemented QC domains. We enforce
    # that in code instead of trusting a small local model to voluntarily call
    # every required tool.
    if _is_broad_investigation(question):
        evidence, tools_used = _run_broad_qc(store, subject_id)
        answer = _summarize_broad_evidence(subject_id, question, evidence)
        return {
            "subject_id": subject_id,
            "question": question,
            "answer": answer,
            "tools_used": tools_used,
            "evidence": evidence,
            "review_mode": "broad_forced_qc",
        }

    # Narrow questions retain genuine model-directed tool selection.
    graph = build_investigation_graph(store)
    user_prompt = (
        f"Subject ID: {subject_id}\n"
        f"Question: {question}\n"
        "Only investigate this subject. Use deterministic QC tools before making factual claims."
    )

    result = graph.invoke(
        {"messages": [HumanMessage(content=user_prompt)]},
        config={"recursion_limit": 20},
    )

    messages = result["messages"]
    tool_calls: list[str] = []
    for message in messages:
        for call in getattr(message, "tool_calls", []) or []:
            name = call.get("name")
            if name:
                tool_calls.append(name)

    final_message = messages[-1]
    content = getattr(final_message, "content", "")
    if isinstance(content, list):
        answer = "\n".join(str(item) for item in content)
    else:
        answer = str(content)

    return {
        "subject_id": subject_id,
        "question": question,
        "answer": answer,
        "tools_used": tool_calls,
        "review_mode": "agent_selected_tools",
    }
