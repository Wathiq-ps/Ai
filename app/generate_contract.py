"""Sprint 5 (1C) — generate_contract: retrieve -> draft -> ground.
See AI_IMPLEMENTATION_PLAN.md Phase 1C and openapi.yaml's GenerateContractResult.

Design: one LLM call, not a graph. Retrieval per clause kind is deterministic
fan-out (no branching/looping needed), and the only retry loop is "did the
model return valid JSON" — a bounded for-loop covers that without pulling in
LangGraph. Revisit if analyze_contract's multi-finding-type dispatch turns out
to need real branching.

Grounding is enforced structurally, not trusted from the model: the model
picks citations by short label (`[C3]`) from the excerpts it was given, and we
hydrate the real `Citation` (source_id/chunk_id/excerpt) from what we actually
retrieved — a scrambled UUID in the model's output can't forge a citation.

`body` is assembled deterministically from `clauses[]` in a fixed order rather
than asked of the model separately, so the two can never drift apart.
"""

import hashlib
import json
import re
import uuid
from dataclasses import dataclass

from app.arabic_money import PERIODS, amount_ar
from app.errors import JobFailed
from app.knowledge import SearchResult, search_many
from app.providers.base import EmbeddingProvider, LLMProvider
from app.usage import stage
from app.wire import ErrorCode

CLAUSE_KINDS = [
    "parties", "subject", "price", "payment_terms", "duration", "obligations",
    "warranties", "termination", "dispute_resolution", "governing_law", "other",
]

# ponytail: FR-6.2 lists 14 required clause groups against an 11-value DB
# enum (see SPRINT4_NEXT_STEPS.md). registration/competent court/fees-tax fold
# into these until the enum grows.
CLAUSE_TOPICS = {
    "parties": "identification of the parties (buyer/seller or landlord/tenant)",
    "subject": "the property being sold or rented",
    "price": "price or rent value",
    "payment_terms": "payment mechanism and schedule",
    "duration": "contract duration",
    "obligations": "obligations and rights of each party",
    "warranties": "warranties",
    "termination": "termination and breach",
    "dispute_resolution": "dispute resolution, competent court, and force majeure",
    "governing_law": "governing law, registration, and fees/tax",
    "other": "signatures and any other required formalities",
}

MAX_ATTEMPTS = 3

# A contract is governed by its own subject-matter law plus the `general`
# layer (the Mejelle). Without this filter a rent draft happily cites the
# foreigners-ownership law at whatever the embedder ranks highest.
CONTRACT_LAW_TYPES = {
    "rent": ["rent", "general"],
    "sale": ["sale", "ownership", "general"],
}

# What each clause has to *do*, in the register Palestinian/Jordanian leases
# actually use (see the templates surveyed 2026-09-13). Without per-kind
# direction the model falls back on reciting whatever it retrieved — which is
# exactly what `termination` and `other` did.
DRAFTING_NOTES = {
    "parties": "Name both parties as الطرف الأول (المؤجر) and الطرف الثاني (المستأجر) with their id numbers, and record that they contract in full legal capacity.",
    "subject": "Describe the let property and the use it is let for, and record that the tenant received it in the condition described.",
    "price": "State the rent as digits (words) currency period: Terms' price_ar copied character for character, then price_unit_ar — never a bare decimal or a currency code. If Terms carry no price, a bracketed blank. Nothing else belongs in this clause.",
    "payment_terms": "State when and how rent falls due, what counts as valid discharge, and what happens on late payment.",
    "duration": "State the start date, the end date, and what happens at expiry (renewal or vacancy). Use bracketed blanks for any date not supplied.",
    "obligations": "A numbered list of what each party must and must not do — upkeep, subletting, lawful use, returning the property as received.",
    "warranties": "The landlord's warranty of title and of quiet enjoyment, and the tenant's remedy if a defect prevents the agreed use.",
    "termination": "State plainly when this contract ends: at the term's expiry, and on the tenant's breach of an obligation this contract itself imposes (rent, upkeep, lawful use) after notice. Two or three sentences, not a list — do not enumerate the statute's repossession grounds one by one, even paraphrased; that is the law's content, not a term of this contract.",
    "dispute_resolution": "The competent court, each party's address for service (الموطن المختار), and notification through الكاتب العدل.",
    "governing_law": "Name the governing statute exactly as the source of an excerpt you cite names it (the title in parentheses after its label), and cite an excerpt from every statute you name. Never write a law number or year that is not in one of those titles.",
    "other": "Execution formalities only: number of copies, that the preamble forms part of the contract, that the contract is an executory instrument (سند تنفيذي), and signature by both parties and witnesses. No legal doctrine.",
}

# DRAFTING_NOTES and the system prompt are written for a lease, so a sale
# drafted through them comes out in lease wording. The job endpoint refuses
# anything not listed here; adding sale means its own notes (and, ideally, its
# registration law in the KB), then adding it to this set.
DRAFTABLE_CONTRACT_TYPES = {"rent"}

# A statute is pinned by its number/year pair — "رقم (62) لسنة 1953", "رقم 62
# لعام ١٩٥٣", "رقم 62/1953". `\d` matches Arabic-Indic digits and int()
# normalises them, so the pair compares equal however it was written.
# Regression: governing_law once named "قانون المالكين والمستأجرين رقم (7) لسنة
# 1958" — the knowledge base holds 62/1953, not that.
# ponytail: only number/year pairs are checked; a statute named by title alone
# slips through. That is not the form the invention took, and a bare title
# can't be matched to a source without fuzzy matching.
_STATUTE_REF = re.compile(r"رقم\s*\(?\s*(\d+)\s*\)?\s*(?:/|ل?(?:سنة|عام))\s*(\d{4})")


def _statute_refs(text: str) -> set[tuple[int, int]]:
    return {(int(number), int(year)) for number, year in _STATUTE_REF.findall(text)}


class GenerationFailed(JobFailed):
    """No verified law found, or the LLM never produced valid structured
    output after MAX_ATTEMPTS — fail closed (BR-28), no partial draft."""


@dataclass
class Clause:
    clause_kind: str
    content: str


@dataclass
class Citation:
    source_id: uuid.UUID
    article_ref: str | None
    chunk_id: uuid.UUID
    excerpt: str


@dataclass
class GenerateContractResult:
    body: str
    clauses: list[Clause]
    citations: list[Citation]
    kb_version_id: uuid.UUID


# Re-running the *same* draft request should not be a fresh roll of the dice —
# BACKEND_INTEGRATION.md already tells Laravel "store the result, don't
# re-run", but Laravel has nothing to store into yet (Sprint 7, on hold). This
# is the stopgap until it does: identical inputs return the identical draft,
# in-process, no extra tokens spent. Unbounded key space is fine at demo
# scale; capped so a long-running process can't grow this forever.
_CACHE_CAPACITY = 64
_draft_cache: dict[tuple, GenerateContractResult] = {}


def _draft_cache_key(
    jurisdiction_id: uuid.UUID, contract_type: str, parties: list[dict],
    property: dict, terms: dict | None, language: str, k_per_clause: int,
) -> tuple:
    payload = json.dumps(
        {"parties": parties, "property": property, "terms": terms}, sort_keys=True, ensure_ascii=False
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return (jurisdiction_id, contract_type, digest, language, k_per_clause)


async def generate_contract(
    pool,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    *,
    jurisdiction_id: uuid.UUID,
    contract_type: str,
    parties: list[dict],
    property: dict,
    terms: dict | None = None,
    language: str = "ar",
    k_per_clause: int = 5,
) -> GenerateContractResult:
    cache_key = _draft_cache_key(
        jurisdiction_id, contract_type, parties, property, terms, language, k_per_clause
    )
    if cache_key in _draft_cache:
        return _draft_cache[cache_key]

    with stage("retrieval"):
        context = await _retrieve_context(
            pool, embedder, jurisdiction_id=jurisdiction_id, contract_type=contract_type,
            property=property, k_per_clause=k_per_clause,
        )
    if not context:
        raise GenerationFailed("no verified law found for this jurisdiction/contract type", ErrorCode.NO_VERIFIED_SOURCES)

    # search() only ever queries the one `active` kb_version per jurisdiction
    # (see app/knowledge.py), so every result here shares the same id.
    kb_version_id = next(iter(context.values())).kb_version_id

    system, user = _build_prompt(contract_type, parties, property, terms, language, context)

    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        prompt = user if not last_error else f"{user}\n\nYour last reply was invalid: {last_error}. Reply with corrected JSON only."
        with stage("llm", attempt=attempt):
            raw = await llm.chat(system, prompt, json_mode=True, max_tokens=16384)
        try:
            clauses, citations = _parse_and_ground(raw, context)
        except _InvalidDraft as exc:
            last_error = str(exc)
            continue
        body = "\n\n".join(c.content for c in clauses)
        result = GenerateContractResult(body=body, clauses=clauses, citations=citations, kb_version_id=kb_version_id)
        if len(_draft_cache) >= _CACHE_CAPACITY:
            _draft_cache.pop(next(iter(_draft_cache)))
        _draft_cache[cache_key] = result
        return result

    raise GenerationFailed(f"LLM never produced valid structured output: {last_error}", ErrorCode.LLM_INVALID_OUTPUT)


class _InvalidDraft(Exception):
    pass


async def _retrieve_context(
    pool, embedder: EmbeddingProvider, *, jurisdiction_id: uuid.UUID, contract_type: str,
    property: dict, k_per_clause: int,
) -> dict[str, SearchResult]:
    """One retrieval per clause topic, deduplicated by chunk_id, labeled `C1..Cn`."""
    property_desc = " ".join(str(v) for v in property.values())
    law_types = CONTRACT_LAW_TYPES.get(contract_type, ["general"])
    queries = [f"{contract_type} contract: {topic}. {property_desc}" for topic in CLAUSE_TOPICS.values()]
    context: dict[str, SearchResult] = {}
    for results in await search_many(
        pool, embedder, jurisdiction_id=jurisdiction_id, queries=queries,
        law_type=law_types, k=k_per_clause,
    ):
        for result in results:
            context.setdefault(str(result.chunk_id), result)

    return {f"C{i + 1}": result for i, result in enumerate(context.values())}


def _build_prompt(
    contract_type: str, parties: list[dict], property: dict, terms: dict | None, language: str,
    context: dict[str, SearchResult],
) -> tuple[str, str]:
    excerpts = "\n".join(f"[{label}] ({r.source_title}) {r.content}" for label, r in context.items())
    notes = "\n".join(f"- {kind}: {DRAFTING_NOTES[kind]}" for kind in CLAUSE_KINDS)
    system = (
        "You draft contracts the way a Palestinian lawyer drafts them: the plain, operative register "
        "of a عقد إيجار executed before الكاتب العدل, not an academic restatement of the law.\n"
        "\n"
        "The excerpts are legal AUTHORITY, not content to reproduce. Never quote, paraphrase or "
        "restate a rule from them. Write the binding term the rule requires or permits, in the voice "
        "of the contract, addressing the parties as الطرف الأول and الطرف الثاني — then cite the "
        "excerpt that authorises it. A clause that says what the law provides, instead of what these "
        "two parties owe each other, is wrong and will be rejected.\n"
        "Never cite an excerpt that does not apply to these parties — an excerpt about foreigners, "
        "sales or taxes has no place in a lease between two Palestinians.\n"
        "Use the supplied Terms (the rent, its period, starts_on, ends_on) exactly as given "
        "wherever a clause needs them.\n"
        "If a clause needs a detail that was not supplied (a date, a term length, a notice period, a "
        "deposit), write the term with a bracketed blank such as [تاريخ بدء الإجارة] rather than "
        "inventing a value or padding the clause with legal doctrine.\n"
        "Keep each clause to what it is for — one clause, one job:\n"
        f"{notes}\n"
        "\n"
        "Do not invent legal content beyond the excerpts. Reply with JSON only, no prose, no markdown "
        'fences, shaped exactly as: {"clauses": [{"clause_kind": "...", "content": "...", "cites": ["C1"]}]}. '
        f"clause_kind must be one of: {', '.join(CLAUSE_KINDS)}. "
        "Include exactly one clause per kind, in that order. Every clause must cite at least one label "
        "from the excerpts that supports it. Write clause content in "
        + ("Arabic." if language == "ar" else "English.")
    )
    user = (
        f"Contract type: {contract_type}\n"
        f"Parties: {json.dumps(parties, ensure_ascii=False)}\n"
        f"Property: {json.dumps(property, ensure_ascii=False)}\n"
        f"Terms: {json.dumps(_prompt_terms(terms, language), ensure_ascii=False)}\n\n"
        f"Law excerpts:\n{excerpts}"
    )
    return system, user


def _prompt_terms(terms: dict | None, language: str) -> dict:
    """The Terms the model sees. A price we can state in Arabic replaces the
    raw price/currency/price_unit, so "450.000" and "JOD" never reach an
    Arabic draft — the model copied both verbatim when it had them, and a
    reviewer read 450.000 as four hundred fifty thousand."""
    terms = dict(terms or {})
    price_ar = amount_ar(terms.get("price"), terms.get("currency")) if language == "ar" else None
    if price_ar:
        del terms["price"], terms["currency"]
        terms["price_ar"] = price_ar
        if terms.get("price_unit") in PERIODS:
            terms["price_unit_ar"] = PERIODS[terms.pop("price_unit")]
    return terms


def _parse_and_ground(raw: str, context: dict[str, SearchResult]) -> tuple[list[Clause], list[Citation]]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _InvalidDraft(f"not valid JSON ({exc})") from exc

    raw_clauses = data.get("clauses")
    if not isinstance(raw_clauses, list) or not raw_clauses:
        raise _InvalidDraft("missing or empty 'clauses' array")

    clauses: list[Clause] = []
    cited_labels: set[str] = set()
    seen_kinds: set[str] = set()
    for entry in raw_clauses:
        kind = entry.get("clause_kind")
        content = entry.get("content")
        cites = entry.get("cites") or []
        if kind not in CLAUSE_KINDS:
            raise _InvalidDraft(f"unknown clause_kind {kind!r}")
        if kind in seen_kinds:
            raise _InvalidDraft(f"duplicate clause_kind {kind!r}")
        if not isinstance(content, str) or not content.strip():
            raise _InvalidDraft(f"empty content for clause_kind {kind!r}")
        if not cites or not all(label in context for label in cites):
            raise _InvalidDraft(f"clause_kind {kind!r} cites an unknown or missing label")
        if kind == "governing_law":
            _check_statutes_are_cited(content, [context[label] for label in cites])
        seen_kinds.add(kind)
        cited_labels.update(cites)
        clauses.append(Clause(clause_kind=kind, content=content.strip()))

    missing = set(CLAUSE_KINDS) - seen_kinds
    if missing:
        raise _InvalidDraft(f"missing clause_kind(s): {sorted(missing)}")

    citations = [
        Citation(
            source_id=context[label].source_id,
            article_ref=context[label].article,
            chunk_id=context[label].chunk_id,
            excerpt=context[label].content,
        )
        for label in sorted(cited_labels)
    ]
    return clauses, citations


def _check_statutes_are_cited(content: str, cited: list[SearchResult]) -> None:
    """Every statute the clause names by number/year must be the source of an
    excerpt it cites — the model may choose among the retrieved laws, never
    supply one."""
    grounded = set().union(*(_statute_refs(f"{r.source_title} {r.source_citation or ''}") for r in cited))
    invented = _statute_refs(content) - grounded
    if invented:
        named = ", ".join(f"رقم ({number}) لسنة {year}" for number, year in sorted(invented))
        sources = "; ".join(sorted({r.source_title for r in cited}))
        raise _InvalidDraft(
            f"governing_law names {named}, which is not the source of any excerpt it cites ({sources}); "
            "name the statute exactly as a cited excerpt's source names it"
        )
