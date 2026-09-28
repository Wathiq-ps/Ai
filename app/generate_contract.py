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

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import date

from app.arabic_money import PERIODS, amount_ar
from app.errors import JobFailed
from app.knowledge import SearchResult, search_many
from app.providers.base import EmbeddingProvider, LLMProvider
from app.usage import job_tag, stage
from app.wire import ErrorCode

logger = logging.getLogger("wathiq_ai")

# The conditions every contract carries — a sale's full list, and the checklist
# for a contract of unknown type.
CLAUSE_KINDS = [
    "parties", "subject", "price", "payment_terms", "duration", "obligations",
    "warranties", "termination", "dispute_resolution", "governing_law", "other",
]

# A lease also carries the mechanics every West Bank / Jordanian residential
# form has and the 11 did not (compared 2026-09-28): the deposit, who pays the
# utilities and fees, the maintenance split, the handover memo, and the
# landlord's access. Each is its own clause so it can be checked and edited on
# its own; renewal stays in `duration`.
RENT_EXTRA_KINDS = ["deposit", "utilities", "maintenance", "handover", "inspection"]
CLAUSE_KINDS_BY_TYPE = {
    "rent": [
        "parties", "subject", "price", "payment_terms", "deposit", "duration", "obligations",
        "utilities", "maintenance", "handover", "inspection", "warranties", "termination",
        "dispute_resolution", "governing_law", "other",
    ],
    "sale": CLAUSE_KINDS,
}
# Every kind any contract type uses — the wire enum (openapi.yaml ClauseKind).
ALL_CLAUSE_KINDS = CLAUSE_KINDS_BY_TYPE["rent"]

# Terms of the parties' bargain the law does not speak to: an honest draft of
# these may cite nothing, and forcing a citation only made the model reach for
# an unrelated article. Every other clause still must cite (BR-25).
CITATION_OPTIONAL_KINDS = {"deposit", "utilities", "handover", "inspection", "dispute_resolution", "other"}


def clause_kinds(contract_type: str | None) -> list[str]:
    """The conditions a contract of this type must carry, in contract order."""
    return CLAUSE_KINDS_BY_TYPE.get(contract_type, CLAUSE_KINDS)

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
    "deposit": "security deposit (تأمين) paid by the tenant and its return",
    "utilities": "electricity, water and municipal charges and taxes during the lease: who pays",
    "maintenance": "repairs of the leased property: what the landlord must repair and what the tenant bears",
    "handover": "delivery of the leased property to the tenant, its condition, and its return at the end",
    "inspection": "the landlord's entry into the leased property to inspect or repair it",
}

# "contract duration" is a lease's question. A sale has no term; its timeline
# is handover and the registry transfer, and a duration query invites the
# Mejelle's lease-term articles into a sale's context.
CLAUSE_TOPIC_OVERRIDES = {
    "sale": {"duration": "delivery of the property and completing the sale at the Land Registry"},
}


def clause_topics(contract_type: str | None) -> dict[str, str]:
    topics = CLAUSE_TOPICS | CLAUSE_TOPIC_OVERRIDES.get(contract_type, {})
    return {kind: topics[kind] for kind in clause_kinds(contract_type)}


MAX_ATTEMPTS = 3

# A contract is governed by its own subject-matter law plus the `general`
# layer (the Mejelle). Without this filter a rent draft happily cites the
# foreigners-ownership law at whatever the embedder ranks highest.
CONTRACT_LAW_TYPES = {
    "rent": ["rent", "general"],
    # `tax` belongs to a sale, not a lease: Law 11/1954 art. 14(5) bars the
    # registry from recording the sale until the property's tax is paid, and
    # art. 17 makes the buyer liable only from the year after — which is what
    # the sale's obligations clause allocates. A lease moves neither.
    "sale": ["sale", "ownership", "tax", "general"],
}

# What each clause has to *do*, in the register Palestinian/Jordanian leases
# actually use (see the templates surveyed 2026-09-13). Without per-kind
# direction the model falls back on reciting whatever it retrieved — which is
# exactly what `termination` and `other` did.
DRAFTING_NOTES = {
    "parties": "Name both parties as الطرف الأول (المؤجر) and الطرف الثاني (المستأجر) with their id numbers and addresses, and record that they contract in full legal capacity.",
    "subject": "Describe the let property and the use it is let for, and record that the tenant received it in the condition described.",
    "price": "State the rent as digits (words) currency period: Terms' price_ar copied character for character, then price_unit_ar — never a bare decimal or a currency code. If Terms carry no price, a bracketed blank. Nothing else belongs in this clause.",
    "payment_terms": "State when rent falls due (Terms' payment_timing, else in advance at the start of each period), how it is paid, and that the landlord's receipt is the valid discharge. Late payment is dealt with in termination, not here.",
    "deposit": "The deposit (تأمين) the tenant pays on signing — Terms' deposit_ar copied character for character, else [مبلغ التأمين] — what it secures (unpaid rent, proven damage beyond fair wear), that it is not rent and is not set against the last period without the landlord's written consent, and that it is returned within [مدة رد التأمين] of the property being handed back.",
    "duration": "State the start and end dates, and that the parties may renew in writing on terms they agree. Under the Landlords and Tenants Law the end of the term is not by itself a ground to evict: never write that expiry obliges the tenant to vacate or lets the landlord repossess — if the tenant stays on, this contract's terms continue to govern. Use bracketed blanks for any date not supplied.",
    "obligations": "A numbered list of what each party must and must not do in using the property — lawful use for the agreed purpose only, no subletting or assignment and no alteration without the landlord's written consent, no nuisance to neighbours. Repairs, utilities, handover and access have their own clauses; do not repeat them. Duties only: no remedies or procedures copied from the law.",
    "utilities": "Who pays what during the term: the tenant pays electricity, water and other consumption charges from the start date and settles them before handing back; the landlord pays taxes charged on the property itself. Any charge not allocated by Terms that the parties must still decide (building services, municipal fees) is a bracketed blank naming who pays.",
    "maintenance": "Split the repairs: the landlord bears the repairs needed to keep the property fit for the agreed use (structure, roof, main water, electricity and sewage lines); the tenant bears minor repairs from ordinary use and any damage he or his household causes. If the landlord leaves a necessary repair undone after written notice, the tenant may carry it out at the landlord's cost.",
    "handover": "The property and its keys are handed over on the start date; a handover memo (محضر تسليم واستلام) signed by both parties, listing its fittings, contents and meter readings, forms part of this contract. At the end the tenant returns the property and keys in the condition the memo records, fair wear excepted.",
    "inspection": "The landlord may enter to inspect or carry out repairs at a reasonable hour after [مدة الإشعار] notice to the tenant, and at any time in an emergency.",
    "warranties": "Two sentences: the landlord warrants he may let the property and that the tenant will enjoy it undisturbed, and if a defect prevents the agreed use the tenant may rescind or have it repaired at the landlord's cost. No ownership shares, conditions or procedures copied from the law.",
    "termination": "State when the landlord may seek to recover the property for the tenant's breach: rent left unpaid, or a term of this contract broken, and not remedied within the number of days the cited article gives after notice served through الكاتب العدل — write that number of days out, never 'the legal period'. The term simply running out is not such a ground. Two or three sentences, not a list — do not enumerate the statute's repossession grounds one by one; that is the law's content, not a term of this contract.",
    "dispute_resolution": "Name the courts of the city where the property lies as competent (محاكم <that city>), each party's address for service (الموطن المختار), and notification through الكاتب العدل.",
    "governing_law": "Name every statute this lease rests on — the Landlords and Tenants Law and the Mejelle — by its full title as it appears in parentheses after the label of an excerpt you cite — the title once, not repeated in brackets — and cite an excerpt from each one you name. Never write a law number or year that is not in one of those titles.",
    "other": "Execution formalities only: number of copies, that the preamble forms part of the contract, that the contract is an executory instrument (سند تنفيذي), and signature by both parties and witnesses. No legal doctrine.",
}

# A West Bank sale of land is transacted only at دائرة تسجيل الأراضي (Law
# 49/1953 art. 2, Regulation 1/1953 art. 3), so the parties' own contract
# cannot pass ownership. It is drafted as a sale agreement binding them to
# sell, buy, pay, and complete the transfer at the registry by a deadline.
SALE_DRAFTING_NOTES = {
    "parties": "Name the party whose role is seller as الطرف الأول (البائع) and the buyer as الطرف الثاني (المشتري) with their id numbers, and record that they contract in full legal capacity.",
    "subject": "Describe the property sold as the Land Registry records it — the town, اسم الحوض ورقمه, رقم القطعة, رقم الشقة where it is an apartment, and the area — with a bracketed blank for each identifier not supplied, and record that the seller is its registered owner.",
    "price": "State the total sale price as digits (words) currency: Terms' price_ar copied character for character — never a bare decimal or a currency code. If Terms carry no price, a bracketed blank. Nothing else belongs in this clause.",
    "payment_terms": "State how the price is paid — in full on signing, a deposit (عربون) now and the balance at the registry transfer, or instalments with their amounts and due dates — and what counts as valid discharge. Use bracketed blanks for any amount or date not supplied.",
    "duration": "State the date the property is handed over and the deadline by which both parties complete the transfer at دائرة تسجيل الأراضي. Use bracketed blanks for any date not supplied.",
    "obligations": "A numbered list: the seller hands the property over free of occupants, bears its taxes and charges and clears any encumbrance up to the transfer, and attends the registry to transfer it; the buyer pays the price as agreed and attends the registry to take the transfer. Who bears the registry transfer fees is a bracketed blank.",
    "warranties": "The seller's warranty that he owns the property and may sell it, that it is free of any رهن or حجز, against hidden defects (خيار العيب), and against the buyer's eviction by a third party's claim (ضمان الاستحقاق).",
    "termination": "State plainly when this agreement may be rescinded: the buyer's failure to pay the price as agreed, or either party's failure to complete the transfer at the registry by the deadline, after notice. Two or three sentences, not a list.",
    "dispute_resolution": DRAFTING_NOTES["dispute_resolution"],
    "governing_law": "Name every statute this agreement rests on — the land sale and registration laws and the Mejelle — by its full title as it appears in parentheses after the label of an excerpt you cite — the title once, not repeated in brackets — and cite an excerpt from each one you name. Never write a law number or year that is not in one of those titles.",
    "other": "Execution formalities only: number of copies, that the preamble forms part of the agreement, and signature by both parties and witnesses — and state that ownership passes to the buyer only when the sale is registered at دائرة تسجيل الأراضي. No legal doctrine.",
}

# The only lines of the system prompt that differ by contract type: the
# instrument being drafted, which excerpts have no place in it, what the Terms
# hold, the example blank, and the clause notes. Rent's values are the lease
# prompt verbatim.
DRAFTING_BY_TYPE = {
    "rent": {
        "instrument": "a عقد إيجار executed before الكاتب العدل",
        "off_topic": "an excerpt about foreigners, sales or taxes has no place in a lease between two Palestinians",
        "terms": "the rent, its period, payment_timing, the deposit, starts_on, ends_on",
        "blank": "[تاريخ بدء الإجارة]",
        "notes": DRAFTING_NOTES,
    },
    "sale": {
        "instrument": "an اتفاقية بيع that binds the parties to complete the sale at دائرة تسجيل الأراضي",
        "off_topic": "an excerpt about foreigners or leases has no place in a sale between two Palestinians",
        "terms": "the price, starts_on, ends_on",
        "blank": "[رقم القطعة]",
        "notes": SALE_DRAFTING_NOTES,
    },
}

# The job endpoint refuses any other type rather than draft it in another
# type's wording.
DRAFTABLE_CONTRACT_TYPES = set(DRAFTING_BY_TYPE)

# A statute is pinned by its number/year pair — "رقم (62) لسنة 1953", "رقم 62
# لعام ١٩٥٣", "رقم 62/1953". `\d` matches Arabic-Indic digits and int()
# normalises them, so the pair compares equal however it was written.
# Regression: governing_law once named "قانون المالكين والمستأجرين رقم (7) لسنة
# 1958" — the knowledge base holds 62/1953, not that.
# ponytail: only number/year pairs are checked; a statute named by title alone
# slips through. That is not the form the invention took, and a bare title
# can't be matched to a source without fuzzy matching.
_STATUTE_REF = re.compile(r"رقم\s*\(?\s*(\d+)\s*\)?\s*(?:/|ل?(?:سنة|عام))\s*(\d{4})")


# A long span inside quote marks is law copied in, not a term drafted — once the
# prompt forbade reciting a rule, the model started quoting it instead
# ("يحق للمؤجر 'فسخ العقد في حال تأخر المستأجر ...'", measured 2026-09-28).
# ponytail: 40 chars leaves a quoted defined term ("المأجور") alone.
_QUOTED_SPAN = re.compile(r"""['"«“‘][^'"«»“”‘’]{40,}['"»”’]""")


def _statute_refs(text: str) -> set[tuple[int, int]]:
    return {(int(number), int(year)) for number, year in _STATUTE_REF.findall(text)}


class GenerationFailed(JobFailed):
    """No verified law found, or the LLM never produced valid structured
    output after MAX_ATTEMPTS — fail closed (BR-28), no partial draft."""


@dataclass
class Citation:
    source_id: uuid.UUID
    article_ref: str | None
    chunk_id: uuid.UUID
    excerpt: str
    # The statute's title as knowledge.sources names it — what a reader needs
    # next to "المادة (4)" to know *which* law's article 4.
    law: str = ""


def citation_from(result: SearchResult) -> Citation:
    return Citation(
        source_id=result.source_id,
        article_ref=result.article,
        chunk_id=result.chunk_id,
        excerpt=result.content,
        law=result.source_title,
    )


@dataclass
class Clause:
    clause_kind: str
    content: str
    # The excerpts this clause cited, so a reviewer sees which law backs which term.
    citations: list[Citation] = field(default_factory=list)


@dataclass
class GenerateContractResult:
    body: str
    clauses: list[Clause]
    citations: list[Citation]
    kb_version_id: uuid.UUID


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
    with stage("retrieval"):
        context = await _retrieve_context(
            pool, embedder, jurisdiction_id=jurisdiction_id, contract_type=contract_type,
            k_per_clause=k_per_clause,
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
            clauses, citations = _parse_and_ground(raw, context, clause_kinds(contract_type))
        except _InvalidDraft as exc:
            last_error = str(exc)
            # What the repair round is for: the one rule the model most often
            # breaks is where a prompt fix pays back a whole extra LLM call.
            logger.info("job %s rejected attempt %d: %s", job_tag(), attempt, last_error)
            continue
        body = "\n\n".join(c.content for c in clauses)
        return GenerateContractResult(body=body, clauses=clauses, citations=citations, kb_version_id=kb_version_id)

    raise GenerationFailed(f"LLM never produced valid structured output: {last_error}", ErrorCode.LLM_INVALID_OUTPUT)


class _InvalidDraft(Exception):
    pass


async def _retrieve_context(
    pool, embedder: EmbeddingProvider, *, jurisdiction_id: uuid.UUID, contract_type: str,
    k_per_clause: int,
) -> dict[str, SearchResult]:
    """One retrieval per clause topic, deduplicated by chunk_id, labeled `C1..Cn`.

    The queries are the clause topics alone. They used to append the property's
    values ("apartment رام الله 12 120 3 2"), which named no law and made every
    draft's queries unique — so every draft paid a fresh embedding call (1.5-6.5s
    measured, against a free tier of ~50 requests/day). Fixed per contract type,
    their vectors are cached by the embedding provider after the first draft."""
    law_types = CONTRACT_LAW_TYPES.get(contract_type, ["general"])
    queries = [f"{contract_type} contract: {topic}" for topic in clause_topics(contract_type).values()]
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
    # ponytail: a type with no entry is drafted as a lease, as every type was
    # before sale. Only reachable by calling generate_contract directly — the
    # job endpoint refuses anything not in DRAFTABLE_CONTRACT_TYPES.
    drafting = DRAFTING_BY_TYPE.get(contract_type, DRAFTING_BY_TYPE["rent"])
    kinds = clause_kinds(contract_type)
    notes = "\n".join(f"- {kind}: {drafting['notes'][kind]}" for kind in kinds)
    optional = [k for k in kinds if k in CITATION_OPTIONAL_KINDS]
    system = (
        "You draft contracts the way a Palestinian lawyer drafts them: the plain, operative register "
        f"of {drafting['instrument']}, not an academic restatement of the law.\n"
        "\n"
        "The excerpts are legal AUTHORITY, not content to reproduce. Never quote, paraphrase or "
        "restate a rule from them. Write the binding term the rule requires or permits, in the voice "
        "of the contract, addressing the parties as الطرف الأول and الطرف الثاني — then cite the "
        "excerpt that authorises it. A clause that says what the law provides, instead of what these "
        "two parties owe each other, is wrong and will be rejected.\n"
        f"Never cite an excerpt that does not apply to these parties — {drafting['off_topic']}.\n"
        f"Use the supplied Terms ({drafting['terms']}) exactly as given "
        "wherever a clause needs them.\n"
        "If a clause needs a detail that was not supplied (a date, a term length, a notice period, a "
        f"deposit), write the term with a bracketed blank such as {drafting['blank']} rather than "
        "inventing a value or padding the clause with legal doctrine. Every number, identifier and "
        "date in the contract comes from Parties, Property or Terms, under the meaning its label "
        "gives it — a room count is not an apartment number. One the clause needs but nobody "
        "supplied (an id number, an address) is a bracketed blank, never left out.\n"
        "Keep each clause to what it is for — one clause, one job:\n"
        f"{notes}\n"
        "\n"
        "Do not invent legal content beyond the excerpts. Reply with JSON only, no prose, no markdown "
        'fences, shaped exactly as: {"clauses": [{"clause_kind": "...", "content": "...", "cites": ["C1"]}]}. '
        f"clause_kind must be one of: {', '.join(kinds)}. "
        "Include exactly one clause per kind, in that order. Every clause must cite at least one label "
        f"from the excerpts that supports it, except {', '.join(optional)}: those are the parties' own "
        "bargain, and cite an excerpt only where one really speaks to them — otherwise cites is []. "
        "Write clause content in "
        + ("Arabic." if language == "ar" else "English.")
    )
    user = (
        f"Contract type: {contract_type}\n"
        f"Parties: {json.dumps(_prompt_parties(parties, language), ensure_ascii=False)}\n"
        f"Property: {json.dumps(_prompt_property(property, language), ensure_ascii=False)}\n"
        f"Terms: {json.dumps(_prompt_terms(terms, language), ensure_ascii=False)}\n\n"
        f"Law excerpts:\n{excerpts}"
    )
    return system, user


# Back-end's property keys (AiJobService::draftPayload) in the words a
# contract uses. Raw keys were misread: `rooms: 3` became "الشقة رقم 3", an
# apartment number nobody supplied. Unknown keys pass through as sent.
PROPERTY_LABELS_AR = {
    "type": "نوع العقار", "city": "المدينة", "district": "الحي", "address_line": "العنوان",
    "building_number": "رقم البناية", "area_sqm": "المساحة بالمتر المربع", "rooms": "عدد الغرف",
    "bathrooms": "عدد الحمامات", "floor_number": "رقم الطابق", "is_furnished": "مفروش",
}
PROPERTY_TYPES_AR = {
    "apartment": "شقة", "house": "منزل", "villa": "فيلا", "land": "أرض", "office": "مكتب",
    "shop": "محل تجاري", "warehouse": "مستودع", "building": "بناية", "farm": "مزرعة",
}


# Back-end's party keys (AiJobService::party). `role` stays as sent: the
# drafting notes key the parties on it.
PARTY_LABELS_AR = {
    "name": "الاسم", "nationality": "الجنسية", "document_type": "نوع وثيقة الهوية",
    "document_number": "رقم وثيقة الهوية", "address": "العنوان",
}
DOCUMENT_TYPES_AR = {
    "national_id": "بطاقة هوية", "passport": "جواز سفر", "residency_permit": "تصريح إقامة",
    "commercial_register": "سجل تجاري",
}


def _prompt_parties(parties: list[dict], language: str) -> list[dict]:
    if language != "ar":
        return parties
    return [
        {PARTY_LABELS_AR.get(k, k): DOCUMENT_TYPES_AR.get(v, v) if k == "document_type" else v
         for k, v in party.items()}
        for party in parties
    ]


def _prompt_property(property: dict, language: str) -> dict:
    if language != "ar":
        return property
    shown = {}
    for key, value in property.items():
        if key == "type":
            value = PROPERTY_TYPES_AR.get(value, value)
        elif isinstance(value, bool):
            value = "نعم" if value else "لا"
        shown[PROPERTY_LABELS_AR.get(key, key)] = value
    return shown


def _date_ar(value):
    """2026-11-01 -> 1/11/2026, the day-first form Palestinian contracts use.
    Anything that is not an ISO date is passed through untouched."""
    try:
        d = date.fromisoformat(value)
    except (TypeError, ValueError):
        return value
    return f"{d.day}/{d.month}/{d.year}"


def _prompt_terms(terms: dict | None, language: str) -> dict:
    """The Terms the model sees. A price we can state in Arabic replaces the
    raw price/currency/price_unit, so "450.000" and "JOD" never reach an
    Arabic draft — the model copied both verbatim when it had them, and a
    reviewer read 450.000 as four hundred fifty thousand."""
    terms = dict(terms or {})
    price_ar = amount_ar(terms.get("price"), terms.get("currency")) if language == "ar" else None
    if price_ar:
        # The deposit is in the rent's currency; stated the same way, or left
        # as sent if it can't be.
        deposit_ar = amount_ar(terms.get("deposit"), terms["currency"])
        if deposit_ar:
            del terms["deposit"]
            terms["deposit_ar"] = deposit_ar
        del terms["price"], terms["currency"]
        terms["price_ar"] = price_ar
        if terms.get("price_unit") in PERIODS:
            terms["price_unit_ar"] = PERIODS[terms.pop("price_unit")]
    if language == "ar":
        for key in ("starts_on", "ends_on"):
            if key in terms:
                terms[key] = _date_ar(terms[key])
    return terms


def _parse_and_ground(
    raw: str, context: dict[str, SearchResult], kinds: list[str] = CLAUSE_KINDS,
) -> tuple[list[Clause], list[Citation]]:
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
        if kind not in kinds:
            raise _InvalidDraft(f"unknown clause_kind {kind!r}")
        if kind in seen_kinds:
            raise _InvalidDraft(f"duplicate clause_kind {kind!r}")
        if not isinstance(content, str) or not content.strip():
            raise _InvalidDraft(f"empty content for clause_kind {kind!r}")
        # A label we never handed out can't be hydrated, so it is dropped; the
        # clause is sent back only if nothing real is left. Rejecting the draft
        # for one stray label re-rolled all 11 clauses (~7.5s, measured).
        cites = [label for label in cites if label in context]
        if not cites and kind not in CITATION_OPTIONAL_KINDS:
            raise _InvalidDraft(f"clause_kind {kind!r} cites no label from the excerpts")
        if _QUOTED_SPAN.search(content):
            raise _InvalidDraft(
                f"clause_kind {kind!r} quotes text; write the parties' own term in the contract's voice"
            )
        if kind == "governing_law":
            _check_statutes_are_cited(content, [context[label] for label in cites])
        seen_kinds.add(kind)
        cited_labels.update(cites)
        clauses.append(Clause(
            clause_kind=kind, content=content.strip(),
            citations=[citation_from(context[label]) for label in dict.fromkeys(cites)],
        ))

    missing = set(kinds) - seen_kinds
    if missing:
        raise _InvalidDraft(f"missing clause_kind(s): {sorted(missing)}")
    # Contract order, whatever order the model replied in: Laravel numbers the
    # clauses by position (contract_clauses.ordinal), so position is meaning.
    clauses.sort(key=lambda c: kinds.index(c.clause_kind))

    citations = [citation_from(context[label]) for label in sorted(cited_labels)]
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
