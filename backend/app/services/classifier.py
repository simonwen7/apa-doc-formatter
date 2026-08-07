def normalize_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def is_question_start(text: str) -> bool:
    t = normalize_text(text)
    return t in {"question 1", "question 2", "question 3"}


def is_answer_marker(text: str) -> bool:
    t = normalize_text(text)
    return t.startswith("include your answer to q1 here:") or \
           t.startswith("include your answer to q2 here:") or \
           t.startswith("include your answer to q3 here:")


def is_heading_text(text: str) -> bool:
    t = normalize_text(text)
    return (
        t in {"describe", "examine", "articulate learning"} or
        t.startswith("[prompt:")
    )


def classify_document(parsed: dict) -> dict:
    classified = []
    in_answer_section = False

    for para in parsed["paragraphs"]:
        text = para.get("text", "")
        style = (para.get("style") or "").lower()
        norm = normalize_text(text)

        if not norm:
            role = "empty"
        elif style in {"heading 1", "heading 2", "heading 3", "title", "subtitle"}:
            role = "heading"
        elif is_question_start(text):
            in_answer_section = False
            role = "instruction"
        elif is_answer_marker(text):
            in_answer_section = True
            role = "instruction"
        elif is_heading_text(text):
            role = "heading"
        else:
            instruction_keywords = [
                "please read through",
                "select one of the prompts",
                "use the deal model",
                "prompt a",
                "prompt b",
                "prompt c",
                "word count",
                "which prompt are you answering",
                "when answering",
                "note:",
            ]

            if any(k in norm for k in instruction_keywords):
                role = "instruction"
            elif in_answer_section:
                role = "body"
            else:
                role = "instruction"

        item = para.copy()
        item["role"] = role
        classified.append(item)

    return {"paragraphs": classified}


def classify_paragraph(para: dict) -> str:
    parsed = {"paragraphs": [para]}
    result = classify_document(parsed)
    return result["paragraphs"][0]["role"]
