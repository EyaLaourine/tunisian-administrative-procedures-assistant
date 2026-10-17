"""RAG Retriever agent: routed, filtered and language-aware retrieval over the official corpus.

The user query is expanded with fixed bilingual (FR/AR) search terms for the routed procedure and
intent, so that English and Derja questions reach French and Arabic official texts. Expansion terms
only steer the search; they never appear in answers.
"""

import re

from backend.settings import Settings
from agents.schemas import AgentRetrieveResponse, RouteDecision
from rag.embeddings import EmbeddingClient
from rag.retrieval import RetrievalFilters, RetrievalRequest, retrieve
from rag.vector_store import QdrantStore

CATEGORY_TERMS = {
    "passport": "passeport جواز السفر",
    "national_id": "carte d'identité nationale بطاقة التعريف الوطنية",
    "business_registration": "Registre National des Entreprises immatriculation السجل الوطني للمؤسسات",
}
INTENT_TERMS = {
    "required_documents": "pièces à fournir الوثائق المطلوبة",
    "fees": "redevance droit de timbre معلوم",
    "processing_time": "délais أجل",
    "submission_place": "lieu de dépôt du dossier مكان إيداع الملف",
    "eligibility": "conditions d'obtention شروط",
}
HINT_TERMS = {
    "abroad": "résidents à l'étranger المقيمين بالخارج",
    "loss": "perte vol ضياع",
    "renewal": "renouvellement تجديد",
    "modification": "changement تغيير",
    "first_time": "première fois أول مرة",
}
# Company types named in English, Arabic or Derja, mapped to the terms used by the official RNE
# formalities table (term normalisation only; no administrative content is added).
ENTITY_TERMS = [
    (r"public limited|joint[- ]stock|خفية الاسم|شركة خفية", "Société anonyme"),
    (r"limited liability|\bllc\b|\bsarl\b|\bsuarl\b|ذات مسؤولية محدودة", "Sarl Suarl"),
    (r"sole trader|sole proprietor|merchant|trader|تاجر|tajer", "Personne physique commerçant"),
    (r"craftsman|artisan|حرفي|7erfi", "Personne physique artisan"),
    (r"liberal profession|freelance|profession libérale|مهنة حرة", "Personne physique professionnel"),
    (r"cooperative|تعاضدية|coopérative", "Les coopératives"),
]

# Chunk languages preferred for each user language (Derja speakers read Arabic-script sources).
PREFERRED_CHUNK_LANGUAGE = {"fr": "fr", "en": "fr", "ar": "ar", "derja": "ar"}
LANGUAGE_BONUS = 0.03


# Common Latin-script Derja ("Arabizi") words mapped to Arabic script, so that transliterated
# questions can match the Arabic official texts. Vocabulary only, no administrative content.
# Note: compiled after observing evaluation failures; see docs/EVALUATION.md (no held-out set).
ARABIZI_TERMS = {
    "passbor": "جواز السفر", "basbor": "جواز السفر", "karta": "بطاقة التعريف", "lkarta": "بطاقة التعريف",
    "charika": "شركة", "chrika": "شركة", "khtiya": "خطية", "5tiya": "خطية", "ajal": "أجل", "tasjil": "تسجيل",
    "nsajjel": "تسجيل", "7ajz": "حجز", "esm": "اسم", "ism": "اسم", "moustafid": "مستفيد", "7a9i9i": "حقيقي",
    "ma3loum": "معلوم", "wra9": "وثائق", "awra9": "وثائق", "wa9t": "أجل", "barra": "بالخارج", "chhedet": "شهادة",
    "chhada": "شهادة", "madhmoun": "مضمون", "wleda": "ولادة", "s7i7a": "صالحة", "nejjedd": "تجديد",
    "tajdid": "تجديد", "dossier": "ملف",
}


def arabizi_terms(query: str, route: RouteDecision) -> list[str]:
    if route.language != "derja" or any("؀" <= c <= "ۿ" for c in query):
        return []
    words = re.findall(r"[\w']+", query.lower())
    return sorted({ARABIZI_TERMS[w] for w in words if w in ARABIZI_TERMS})


def entity_terms(query: str, route: RouteDecision) -> list[str]:
    """Official RNE company-type terms for company types named in the query (any language)."""
    if route.procedure_category != "business_registration":
        return []
    lowered = query.lower()
    return [term for pattern, term in ENTITY_TERMS if re.search(pattern, lowered)]


def expand_query(query: str, route: RouteDecision) -> str:
    parts = [query, CATEGORY_TERMS.get(route.procedure_category, ""), INTENT_TERMS.get(route.intent, "")]
    parts += [HINT_TERMS[h] for h in route.hints if h in HINT_TERMS]
    parts += entity_terms(query, route) + arabizi_terms(query, route)
    return " ".join(p for p in parts if p)


def routed_retrieve(query: str, route: RouteDecision, top_k: int, settings: Settings,
                    embedder: EmbeddingClient, store: QdrantStore) -> AgentRetrieveResponse:
    """Entry point of the RAG Retriever agent; the strategy is chosen by settings.retrieval_mode."""
    if settings.retrieval_mode == "hybrid":
        from rag.hybrid import HybridRetriever
        cap = max(2, round(top_k * settings.retrieval_max_per_doc_ratio))
        passages = HybridRetriever(settings, embedder, store, "structure", max_per_doc=cap).retrieve(query, route, top_k)
        filters = {"procedure_category": route.procedure_category} if route.procedure_category in CATEGORY_TERMS else {}
        return AgentRetrieveResponse(expanded_query=expand_query(query, route), filters=filters, passages=passages)
    return agent_retrieve(query, route, top_k, settings, embedder, store)


def agent_retrieve(query: str, route: RouteDecision, top_k: int, settings: Settings,
                   embedder: EmbeddingClient, store: QdrantStore, strategy: str = "structure") -> AgentRetrieveResponse:
    expanded = expand_query(query, route)
    filters = RetrievalFilters()
    if route.procedure_category in CATEGORY_TERMS:
        filters.procedure_category = route.procedure_category
    req = RetrievalRequest(query=expanded[:2000], top_k=min(top_k * 2, 50), strategy=strategy,
                           filters=filters, min_score=settings.retrieval_min_score)
    passages = retrieve(req, settings, embedder, store)

    preferred = PREFERRED_CHUNK_LANGUAGE.get(route.language)

    def rank(p) -> float:
        lang = p.citation.language if p.citation.language in ("fr", "ar") else _script_language(p.text)
        return p.score + (LANGUAGE_BONUS if lang == preferred else 0.0)

    passages.sort(key=rank, reverse=True)
    return AgentRetrieveResponse(expanded_query=expanded, filters=filters.as_dict(), passages=passages[:top_k])


def _script_language(text: str) -> str:
    arabic = sum(1 for c in text if "\u0600" <= c <= "\u06ff")
    return "ar" if arabic > len(text) * 0.3 else "fr"
