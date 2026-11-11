import html
import inspect
import json
import os
from unittest import mock

import pytest
import requests

from conftest import make_job, make_match

from src.agents.nodes.draft_letter import candidate_name, ensure_signature, remove_sentence
from src.agents.state import choose_for_letters
from src.config import DOMAIN_KEYWORDS, PHD_ROLE_KEYWORDS, ROLE_KEYWORDS
from src.evaluation.evaluate_scoring import load_labels, precision_at_k, spearman
from src.agents.nodes import scrape
from src.scrapers import cea_offres, cnrs_offres, inria_offres
from src.settings import clean_keywords, load_settings, save_settings
from src.scrapers.inria_offres import compile_keywords, matches_any
from src.utils import telegram

ROLE = compile_keywords(ROLE_KEYWORDS)
DOMAIN = compile_keywords(DOMAIN_KEYWORDS)


# Keyword filter. Titles are from the run on 2026-10-31.

@pytest.mark.parametrize("title", [
    "Master Internship in AI for biological microscopy",
    "Internship Research / World Models for Networking",
    "Stage : Reconnaissance d’entités nommées dans la parole",
    "Stage M/F : acceptation d'un robot de livraison autonome en environnement de bureau",
])
def test_internship_titles_pass_the_role_filter(title):
    assert matches_any(ROLE, title)


@pytest.mark.parametrize("title", [
    "Adjoint(e)-Fondé(e) de pouvoir de l’Agent Comptable – Pôle Comptabilité, Recouvrement (H/F)",
    "Ingénieur d’étude en biologie",
    "Chef.fe de projet Animation & événementiel du programme IA",
    "Post-Doctoral Research Visit F/M Learning crowd dynamics from real-world data",
    "PhD Position F/M Trustable Machine Learning : Analysis and Verification of Soft Automata",
    "Research Engineer F/M — Crowd data acquisition, processing and modelling",
    "Machine Learning Engineer",
    "Internal auditor",
])
def test_other_titles_fail_the_role_filter(title):
    assert not matches_any(ROLE, title)


PHD_ROLE = compile_keywords(PHD_ROLE_KEYWORDS)


@pytest.mark.parametrize("title", [
    "PhD Position F/M Theory for Discrete Diffusion Models",
    "Doctorant F/H Évaluation des risques liés aux modèles d’IA en Santé",
    "Proposition de thèse : apprentissage profond pour la vision",
])
def test_phd_titles_pass_the_phd_role_filter(title):
    assert matches_any(PHD_ROLE, title)


@pytest.mark.parametrize("title", [
    "Post-Doctoral Research Visit F/M Distributed Learning for Streaming Data",
    "Master Internship in AI for biological microscopy",
])
def test_other_titles_fail_the_phd_role_filter(title):
    assert not matches_any(PHD_ROLE, title)


@pytest.mark.parametrize("text", [
    "Stage en IA", "An AI system", "Using LLMs in networks", "apprentissage profond", "Deep Learning",
])
def test_domain_terms_match(text):
    assert matches_any(DOMAIN, text)


@pytest.mark.parametrize("text", [
    "J'ai travaillé sur la chimie", "J’ai un stage", "biologie marine", "email the team", "Mail us",
])
def test_domain_terms_do_not_match_inside_other_words(text):
    assert not matches_any(DOMAIN, text)


def test_inria_about_text_does_not_count_as_a_domain_match():
    about = ("Together, we explore strategic fields such as artificial intelligence, cybersecurity, "
             "and quantum computing. We develop practical solutions.")
    assert not inria_offres.matches_domain(DOMAIN, "Stage en robotique", about)
    assert inria_offres.matches_domain(DOMAIN, "Stage en robotique", f"Deep learning for robots. {about}")


# Scraper, with HTTP faked

def page(body):
    response = mock.Mock(text=body, status_code=200)
    response.raise_for_status = lambda: None
    return response


def fake_site(details):
    links = "".join(f'<a href="/public/classic/en/offres/{i}">{title}</a>' for i, title in details["links"])

    def get(url, **kwargs):
        if url == inria_offres.INRIA_SEARCH_URL:
            return page(links)
        job_id = url.split("/")[-1]
        if job_id in details["errors"]:
            raise requests.ConnectionError("down")
        return page(f"<main>{details['pages'][job_id]}</main>")
    return get


def test_scraper_applies_role_then_domain_and_keeps_failed_pages(monkeypatch):
    site = fake_site({
        "links": [
            ("2026-1", "Stage : reconnaissance de la parole"),
            ("2026-2", "Stage en biologie"),
            ("2026-3", "PhD Position in AI"),
            ("2026-4", "Internship in chemistry"),
        ],
        "pages": {
            "2026-1": "Modèles de langage et deep learning.",
            "2026-2": "J'ai dit: culture cellulaire.",
        },
        "errors": {"2026-4"},
    })
    monkeypatch.setattr(inria_offres.requests, "get", site)
    monkeypatch.setattr(inria_offres.time, "sleep", lambda _: None)

    jobs = {job["id"]: job for job in inria_offres.get_inria_jobs()}

    assert set(jobs) == {"2026-1", "2026-4"}
    assert jobs["2026-1"]["source"] == "inria"
    assert jobs["2026-4"]["description"] is None


def cnrs_card(ref, title, lab):
    return (f'<div class="card-body"><h3 class="h5"><a href="/Offres/PASS/{ref}/Default.aspx">{title}</a></h3>'
            f'<div class="meta"><p><strong>{lab}</strong></p></div></div>')


def test_cnrs_scraper_searches_internships_and_filters_on_domain(monkeypatch):
    search_page = (cnrs_card("UMR1-AAA-001", "Stage M2 : vision par ordinateur", "LIRIS")
                   + cnrs_card("UMR2-BBB-002", "Stage M2 en écologie", "CEFE")
                   + cnrs_card("UMR3-CCC-003", "Stage M2 en chimie", "ICMR")
                   + cnrs_card("UMR4-DDD-004", "Stage communication", "INSHS"))
    about = "À propos du CNRS\n\nLe CNRS fait de l'intelligence artificielle et de tout le reste."
    pages = {
        "UMR1-AAA-001": "Segmentation d'images.",
        "UMR2-BBB-002": "Modèles de deep learning pour suivre les oiseaux.",
        "UMR3-CCC-003": f"Synthèse organique. {about}",
    }
    posted = {}

    def post(url, data=None, **kwargs):
        posted.update(data)
        return page(search_page)

    def get(url, **kwargs):
        ref = url.split("/")[-2]
        if ref not in pages:
            raise requests.ConnectionError("down")
        return page(f'<article><div class="post-body">{pages[ref]}</div></article>')

    monkeypatch.setattr(cnrs_offres.requests, "post", post)
    monkeypatch.setattr(cnrs_offres.requests, "get", get)
    monkeypatch.setattr(cnrs_offres.time, "sleep", lambda _: None)

    jobs = {job["id"]: job for job in cnrs_offres.get_cnrs_jobs()}

    assert posted["ContractType"] == "STAG"
    # Title match, description match, failed page kept; the CNRS about text alone doesn't count.
    assert set(jobs) == {"UMR1-AAA-001", "UMR2-BBB-002", "UMR4-DDD-004"}
    assert jobs["UMR1-AAA-001"]["source"] == "cnrs"
    assert jobs["UMR1-AAA-001"]["company"] == "CNRS - LIRIS"
    assert jobs["UMR4-DDD-004"]["description"] is None


def cea_offer_url(offer_id):
    return f"{cea_offres.CEA_BASE_URL}/offre-de-emploi/emploi-stage_{offer_id}.aspx"


def cea_offer_page(lab, position):
    return ('<div id="contenu-ficheoffre"><h2>General information</h2>'
            '<div id="x_divEntityDesc"><h3>Organisation</h3>The CEA does artificial intelligence.</div>'
            f'<h3>Description de l\'unité</h3>{lab}'
            f'<h2>Position description</h2>{position}</div>')


def test_cea_scraper_pages_through_results_and_filters_on_position_text(monkeypatch):
    result_pages = {
        1: [("1001", "Stage LLM pour la simulation"), ("1002", "Stage en robotique"),
            ("1003", "Stage capteurs")],
        2: [("1004", "Stage logiciel"), ("1005", "Stage fermé")],
        3: [("1001", "Stage LLM pour la simulation")],   # nothing new, so paging stops
    }
    pages = {
        "1001": cea_offer_page("Laboratoire capteurs.", "Assistant en Python."),
        "1002": cea_offer_page("Laboratoire robotique.", "Planification par deep learning."),
        # The lab works on AI, but this internship doesn't.
        "1003": cea_offer_page("Experts en intelligence artificielle.", "Conception électronique."),
    }
    requested_pages = []

    def get(url, params=None, **kwargs):
        if url == cea_offres.CEA_SEARCH_URL:
            requested_pages.append(params["page"])
            assert params["facet_Contract"] == 579   # "Stage", the default
            cards = "".join(f'<a class="ts-offer-card__title-link" href="{cea_offer_url(i)}">{t}</a>'
                            for i, t in result_pages.get(params["page"], []))
            return page(cards)
        offer_id = url.split("_")[-1].removesuffix(".aspx")
        if offer_id == "1004":
            raise requests.ConnectionError("down")
        response = page(f"<html>{pages.get(offer_id, '')}</html>")
        # A closed offer redirects to the homepage.
        response.url = url if offer_id in pages else f"{cea_offres.CEA_BASE_URL}/accueil.aspx"
        return response

    monkeypatch.setattr(cea_offres.requests, "get", get)
    monkeypatch.setattr(cea_offres.time, "sleep", lambda _: None)

    jobs = {job["id"]: job for job in cea_offres.get_cea_jobs()}

    assert requested_pages == [1, 2, 3]
    assert set(jobs) == {"1001", "1002", "1004"}
    assert jobs["1001"]["source"] == "cea"
    assert "The CEA does artificial intelligence" not in jobs["1001"]["description"]
    assert jobs["1004"]["description"] is None


def test_one_failing_scraper_does_not_stop_the_others(monkeypatch):
    def broken(**keywords):
        raise RuntimeError("site changed")

    monkeypatch.setattr(scrape, "get_inria_jobs", broken)
    monkeypatch.setattr(scrape, "get_cnrs_jobs", lambda **keywords: [{"source": "cnrs", "id": "X"}])
    monkeypatch.setattr(scrape, "get_cea_jobs", lambda **keywords: [])

    assert scrape.scrape_node({})["job_listings"] == [{"source": "cnrs", "id": "X"}]


def test_scrape_node_runs_only_the_selected_sources(monkeypatch):
    calls = []
    for name in ("inria", "cnrs", "cea"):
        monkeypatch.setattr(scrape, f"get_{name}_jobs", lambda name=name, **keywords: calls.append(name) or [])

    save_settings(["cea", "inria"])
    scrape.scrape_node({})

    assert calls == ["inria", "cea"]


def test_scrape_node_passes_the_saved_keywords_and_the_contracts_role_keywords(monkeypatch):
    real = {name: getattr(scrape, f"get_{name}_jobs") for name in ("inria", "cnrs", "cea")}
    received = {}
    for name in real:
        monkeypatch.setattr(scrape, f"get_{name}_jobs", lambda name=name, **keywords: received.update({name: keywords}) or [])

    save_settings(domain_keywords=["robotics"])
    scrape.scrape_node({})

    # CNRS and CEA filter on the contract type in their search form, so they only get the domain keywords.
    assert received == {
        "inria": {"role_keywords": ROLE_KEYWORDS, "domain_keywords": ["robotics"]},
        "cnrs": {"domain_keywords": ["robotics"], "contract_code": "STAG"},
        "cea": {"domain_keywords": ["robotics"], "contract_code": 579},
    }
    # The fakes accept anything, so check the real scrapers accept these arguments too.
    for name, keywords in received.items():
        inspect.signature(real[name]).bind(**keywords)


def test_phd_search_uses_the_phd_codes_and_skips_ceas_site(monkeypatch, capsys):
    received = {}
    for name in ("inria", "cnrs", "cea"):
        monkeypatch.setattr(scrape, f"get_{name}_jobs", lambda name=name, **keywords: received.update({name: keywords}) or [])

    save_settings(contract_type="phd")
    scrape.scrape_node({})

    assert set(received) == {"inria", "cnrs"}   # CEA has no PhD filter
    output = capsys.readouterr().out
    assert "CEA has no PhD offers" in output
    assert "failed" not in output               # skipped on purpose, not by an error
    assert received["cnrs"]["contract_code"] == "DOCTOR"
    assert received["inria"]["role_keywords"] == PHD_ROLE_KEYWORDS


def test_scrape_node_uses_the_config_keywords_by_default(monkeypatch):
    received = {}
    monkeypatch.setattr(scrape, "get_inria_jobs", lambda **keywords: received.update(keywords) or [])
    monkeypatch.setattr(scrape, "get_cnrs_jobs", lambda **keywords: [])
    monkeypatch.setattr(scrape, "get_cea_jobs", lambda **keywords: [])

    scrape.scrape_node({})

    assert received == {"role_keywords": ROLE_KEYWORDS, "domain_keywords": DOMAIN_KEYWORDS}


# Settings

def test_settings_default_to_every_source_when_the_file_is_missing():
    assert load_settings()["sources"] == ["inria", "cnrs", "cea"]


@pytest.mark.parametrize("content", ["{not json", "[]", '{"sources": []}', '{"sources": ["monster"]}'])
def test_broken_settings_fall_back_to_every_source(settings_file, content):
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write(content)
    assert load_settings()["sources"] == ["inria", "cnrs", "cea"]


def test_saved_settings_keep_known_sources_in_order():
    save_settings(["cea", "monster", "cnrs", "cea"])
    assert load_settings()["sources"] == ["cnrs", "cea"]


def test_settings_need_at_least_one_source(settings_file):
    with pytest.raises(ValueError):
        save_settings([])
    assert not os.path.exists(settings_file)


@pytest.mark.parametrize("keywords, expected", [
    (["  NLP ", "data engineering"], ["NLP", "data engineering"]),   # stripped, and new keywords are kept
    (["NLP", "", "   ", 123, None], ["NLP"]),                          # empty and non-text values dropped
    (["LLM", "AI", "LLM"], ["LLM", "AI"]),                              # duplicates dropped, user's order kept
    (["AI", "ai"], ["AI", "ai"]),                                       # case matters: "AI" is case-sensitive
    ("NLP", []),                                                        # not a list
    (None, []),
])
def test_clean_keywords(keywords, expected):
    assert clean_keywords(keywords) == expected


def test_settings_default_to_the_config_domain_keywords_when_the_file_is_missing():
    assert load_settings()["domain_keywords"] == DOMAIN_KEYWORDS


def test_changing_loaded_settings_does_not_change_the_defaults():
    load_settings()["domain_keywords"].append("changed")
    assert load_settings()["domain_keywords"] == DOMAIN_KEYWORDS


def test_a_file_saved_before_keywords_existed_uses_the_default_keywords(settings_file):
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump({"sources": ["cea"]}, f)
    settings = load_settings()
    assert settings["sources"] == ["cea"]
    assert settings["domain_keywords"] == DOMAIN_KEYWORDS


@pytest.mark.parametrize("value", ["AI", [], ["", "  "], [1, 2]])
def test_broken_keywords_fall_back_without_resetting_the_sources(settings_file, value):
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump({"sources": ["cnrs"], "contract_type": "phd", "domain_keywords": value}, f)
    settings = load_settings()
    assert settings["domain_keywords"] == DOMAIN_KEYWORDS
    assert settings["contract_type"] == "phd"
    assert settings["sources"] == ["cnrs"]


def test_saving_one_setting_keeps_the_others():
    save_settings(contract_type="phd", domain_keywords=["robotics"])
    save_settings(["inria"])
    assert_settings(sources=["inria"], contract_type="phd", domain_keywords=["robotics"], delivery="all")

    save_settings(domain_keywords=["NLP"], delivery="top_k", top_k=3)
    assert_settings(sources=["inria"], contract_type="phd", domain_keywords=["NLP"], delivery="top_k", top_k=3)


def assert_settings(**expected):
    """Compares only the given settings, so adding a new setting doesn't break this test."""
    settings = load_settings()
    assert {name: settings[name] for name in expected} == expected


def test_keywords_cannot_be_saved_empty(settings_file):
    save_settings(domain_keywords=["robotics"])
    with pytest.raises(ValueError):
        save_settings(domain_keywords=["", "   "])
    assert load_settings()["domain_keywords"] == ["robotics"]


def test_saved_keywords_keep_accents_readable(settings_file):
    save_settings(domain_keywords=["apprentissage profond", "vision par ordinateur", "réseau de neurones"])
    with open(settings_file, encoding="utf-8") as f:
        assert "réseau de neurones" in f.read()


def test_contract_type_defaults_to_internship():
    assert load_settings()["contract_type"] == "internship"


def test_role_keywords_are_not_a_setting(settings_file):
    # Files saved before role keywords came from the contract type may still hold them.
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump({"contract_type": "internship", "role_keywords": ["PhD"]}, f)
    assert "role_keywords" not in load_settings()

    save_settings(["cnrs"])
    with open(settings_file, encoding="utf-8") as f:
        assert "role_keywords" not in json.load(f)   # dropped from the file on the next save


def test_each_contract_type_has_its_own_role_keywords(monkeypatch):
    # The conflict this design prevents: looking for an internship while Inria filters on PhD titles.
    received = {}
    monkeypatch.setattr(scrape, "get_inria_jobs", lambda **keywords: received.update(keywords) or [])
    monkeypatch.setattr(scrape, "get_cnrs_jobs", lambda **keywords: [])
    monkeypatch.setattr(scrape, "get_cea_jobs", lambda **keywords: [])

    for contract_type, expected in [("internship", ROLE_KEYWORDS), ("phd", PHD_ROLE_KEYWORDS)]:
        save_settings(contract_type=contract_type)
        scrape.scrape_node({})
        assert received["role_keywords"] == expected


@pytest.mark.parametrize("value", ["cdi", ["phd"], 5, None])
def test_unknown_contract_type_falls_back_to_internship(settings_file, value):
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump({"sources": ["cnrs"], "contract_type": value}, f)
    settings = load_settings()
    assert settings["contract_type"] == "internship"
    assert settings["sources"] == ["cnrs"]


@pytest.mark.parametrize("value", ["cdi", ["phd"]])
def test_unknown_contract_type_cannot_be_saved(settings_file, value):
    with pytest.raises(ValueError):
        save_settings(contract_type=value)
    assert not os.path.exists(settings_file)


def test_delivery_defaults_to_every_strong_match():
    settings = load_settings()
    assert settings["delivery"] == "all"
    assert settings["top_k"] == 5


def test_an_invalid_delivery_mode_falls_back_to_all(settings_file):
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump({"sources": ["cnrs"], "delivery": "best", "top_k": 3}, f)
    settings = load_settings()
    assert settings["delivery"] == "all"
    assert settings["top_k"] == 3          # the valid K is kept
    assert settings["sources"] == ["cnrs"]


@pytest.mark.parametrize("top_k", [0, 51, "3", True, 2.5, None])
def test_an_invalid_k_falls_back_to_5(settings_file, top_k):
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump({"delivery": "top_k", "top_k": top_k}, f)
    settings = load_settings()
    assert settings["top_k"] == 5
    assert settings["delivery"] == "top_k"  # the valid mode is kept


@pytest.mark.parametrize("arguments", [{"delivery": "best"}, {"top_k": 0}, {"top_k": 51}, {"top_k": 2.5}, {"top_k": True}])
def test_invalid_delivery_settings_cannot_be_saved(settings_file, arguments):
    with pytest.raises(ValueError):
        save_settings(**arguments)
    assert not os.path.exists(settings_file)


# Choosing which strong matches get a letter

def scored(title, score_value):
    return {"job": make_job(title, title), "job_match": make_match(score_value), "llm_score": score_value}


def test_every_strong_match_is_chosen_best_first():
    jobs = [scored("A", 75), scored("B", 90), scored("C", 40), scored("D", 70)]
    assert choose_for_letters(jobs, None) == ["inria:B", "inria:A", "inria:D"]


def test_top_k_keeps_the_best_k_strong_matches():
    jobs = [scored("A", 75), scored("B", 90), scored("C", 40), scored("D", 70)]
    assert choose_for_letters(jobs, 2) == ["inria:B", "inria:A"]


def test_top_k_never_adds_weak_jobs():
    jobs = [scored("A", 75), scored("C", 40)]
    assert choose_for_letters(jobs, 5) == ["inria:A"]


def test_ties_are_broken_by_title_so_runs_agree():
    jobs = [scored("Zeta", 80), scored("Alpha", 80), scored("Mid", 80)]
    assert choose_for_letters(jobs, 2) == ["inria:Alpha", "inria:Mid"]
    assert choose_for_letters(list(reversed(jobs)), 2) == ["inria:Alpha", "inria:Mid"]


# Removing flagged sentences

@pytest.mark.parametrize("letter, quote, expected", [
    ("One. Two. Three.", "Two.", "One. Three."),
    ("One. Two. Three.", "Two", "One. Three."),
    ("One.\n\nTwo.\n\nThree.", "Two.", "One.\n\nThree."),
    ("One. Two.", "Two.", "One."),
    ("One. Two.", "One.", "Two."),
    ("Score 0.892 here. Next.", "Score 0.892 here.", "Next."),
    ("One. Two.", "Missing", "One. Two."),
])
def test_remove_sentence(letter, quote, expected):
    assert remove_sentence(letter, quote) == expected


# Signature

def test_candidate_name_comes_from_the_first_heading():
    assert candidate_name("intro\n# Abdelhak ABDELHAKEM\n## Profil\n# Other") == "Abdelhak ABDELHAKEM"
    assert candidate_name("## Profil only") is None


@pytest.mark.parametrize("letter, expected", [
    ("Text.\n\nSincerely,", "Text.\n\nSincerely,\nAlex Example"),
    ("Text.\n\nSincerely,\nAlex Example", "Text.\n\nSincerely,\nAlex Example"),
    ("Text.\n\nCordialement, ALEX EXAMPLE\n", "Text.\n\nCordialement, ALEX EXAMPLE"),
    ("I am Alex Example, a student." + " Long text." * 20 + "\n\nSincerely,",
     "I am Alex Example, a student." + " Long text." * 20 + "\n\nSincerely,\nAlex Example"),
])
def test_ensure_signature(letter, expected):
    assert ensure_signature(letter, "Alex Example") == expected


def test_no_known_name_leaves_the_letter_unchanged():
    assert ensure_signature("Sincerely,", None) == "Sincerely,"


# Telegram

def test_split_keeps_every_part_under_the_limit_after_escaping():
    text = "&<>_*[ " * 3000
    parts = telegram.split_text(text)
    assert len(parts) > 1
    assert all(len(html.escape(part)) <= telegram.MAX_MESSAGE_LENGTH for part in parts)
    assert "".join(parts).replace(" ", "") == text.replace(" ", "")


def test_split_handles_text_with_no_spaces():
    parts = telegram.split_text("x" * 10000)
    assert [len(part) for part in parts] == [4096, 4096, 1808]


def test_short_text_is_one_part_and_empty_text_is_none():
    assert telegram.split_text("Hello") == ["Hello"]
    assert telegram.split_text("   ") == []


def test_special_characters_are_escaped_and_arrive_intact(world):
    assert telegram.send_plain("a_b *c* [d] <e> & f")
    assert world.sent == ["a_b *c* [d] &lt;e&gt; &amp; f"]


def test_long_letter_is_sent_as_several_messages(world):
    assert telegram.send_plain("word & " * 2000)
    assert len(world.sent) > 1
    assert all(len(message) <= telegram.MAX_MESSAGE_LENGTH for message in world.sent)


def test_send_lines_never_splits_a_line(world):
    lines = [f'<a href="https://x/{i}">job {i}</a>' for i in range(500)]
    assert telegram.send_lines(lines)
    assert len(world.sent) > 1
    assert "\n".join(world.sent).split("\n") == lines


def test_network_error_returns_false_and_hides_the_token(world, monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise requests.ConnectionError("failed: https://api.telegram.org/botSECRET-TOKEN/sendMessage")
    monkeypatch.setattr(telegram.requests, "post", boom)

    assert telegram.send_html("hi") is False
    assert "SECRET-TOKEN" not in capsys.readouterr().out


def test_rate_limit_waits_and_retries_once(world, monkeypatch):
    from conftest import FakeResponse
    responses = [FakeResponse(429, {"parameters": {"retry_after": 7}}), FakeResponse()]
    waits = []
    monkeypatch.setattr(telegram.requests, "post", lambda *a, **k: responses.pop(0))
    monkeypatch.setattr(telegram.time, "sleep", waits.append)

    assert telegram.send_html("hi") is True
    assert waits == [7]


def test_missing_credentials_return_false(world, monkeypatch):
    monkeypatch.setattr(telegram, "TELEGRAM_BOT_TOKEN", None)
    assert telegram.send_html("hi") is False


# Evaluation

def test_precision_at_k():
    rows = [{"score": 90, "label": 1}, {"score": 80, "label": 0}, {"score": 10, "label": 1}]
    assert precision_at_k(rows, 2) == 0.5


def test_spearman_known_values():
    assert spearman([1, 2, 3], [10, 20, 30]) == pytest.approx(1)
    assert spearman([1, 2, 3], [30, 20, 10]) == pytest.approx(-1)
    assert spearman([1, 2, 3, 4], [1, 1, 2, 2]) == pytest.approx(0.8944, abs=1e-4)
    assert spearman([1, 2], [5, 5]) is None


def test_load_labels_skips_unlabelled_rows(tmp_path):
    path = tmp_path / "labels.csv"
    path.write_text("key,title,url,score,label\na,t,u,80,1\nb,t,u,40,\n", encoding="utf-8")
    assert load_labels(str(path)) == [{"score": 80, "label": 1}]


# Notification channels setting

def test_channels_default_to_telegram():
    assert load_settings()["channels"] == ["telegram"]


@pytest.mark.parametrize("value", ["gmail", [], ["sms"], None])
def test_invalid_channels_fall_back_to_telegram(settings_file, value):
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump({"sources": ["cnrs"], "channels": value}, f)
    settings = load_settings()
    assert settings["channels"] == ["telegram"]
    assert settings["sources"] == ["cnrs"]


def test_saved_channels_keep_known_ones_in_order():
    save_settings(channels=["gmail", "sms", "telegram", "gmail"])
    assert load_settings()["channels"] == ["telegram", "gmail"]


def test_channels_need_at_least_one(settings_file):
    with pytest.raises(ValueError):
        save_settings(channels=["sms"])
    assert not os.path.exists(settings_file)
