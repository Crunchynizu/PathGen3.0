import json


SYSTEM_INSTRUCTION = (
    "You are a supportive tutor. Use only the provided lesson content. "
    "Do not reveal answer keys. Do not invent scores. Do not change routing. "
    "Maximum 180 words."
)
MAX_CONTEXT_CHARS = 6_000
MAX_EVIDENCE_CHARS = 3_000
MAX_PROMPT_CHARS = 12_000


def _prompt_sections(evidence_text, context_text, action):
    return (
        f"{SYSTEM_INSTRUCTION}\n\n"
        f"SESSION PERFORMANCE EVIDENCE:\n{evidence_text}\n\n"
        f"ROUTING ACTION (do not change):\n{action}\n\n"
        f"RETRIEVED LESSON CONTENT:\n{context_text}"
    )


def assemble_prompt(evidence, chunks, action):
    bounded_evidence = {
        "lesson_code": evidence["lesson_code"],
        "weak_skills": list(evidence["weak_skills"]),
        "correct_count": evidence["correct_count"],
        "total_count": evidence["total_count"],
        "hint_used": evidence["hint_used"],
    }
    evidence_text = json.dumps(
        bounded_evidence,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )[:MAX_EVIDENCE_CHARS]
    context_text = "\n\n".join(
        f"[{chunk['chunk_id']}] {chunk['text']}" for chunk in chunks
    )[:MAX_CONTEXT_CHARS]

    prompt = _prompt_sections(evidence_text, context_text, action)
    if len(prompt) > MAX_PROMPT_CHARS:
        overflow = len(prompt) - MAX_PROMPT_CHARS
        context_text = context_text[: max(0, len(context_text) - overflow)]
        prompt = _prompt_sections(evidence_text, context_text, action)
    if len(prompt) > MAX_PROMPT_CHARS:
        overflow = len(prompt) - MAX_PROMPT_CHARS
        evidence_text = evidence_text[: max(0, len(evidence_text) - overflow)]
        prompt = _prompt_sections(evidence_text, context_text, action)
    return prompt
