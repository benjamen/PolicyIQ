from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_compare_life_returns_graded_ranked_results():
    resp = client.post(
        "/api/v1/compare/life",
        json={
            "age": 35,
            "smoker_status": "non_smoker",
            "occupation_category": "Professional",
            "product_type": "life_cover",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_source"] == "synthetic_fixture"
    assert len(body["results"]) == 3

    insurers = [r["insurer"] for r in body["results"]]
    assert "Insurer Alpha" in insurers

    # results are sorted eligible-first, then by overall_score descending
    eligible_flags = [r["eligible"] for r in body["results"]]
    assert eligible_flags == sorted(eligible_flags, reverse=True)


def test_compare_excludes_products_ineligible_for_occupation():
    resp = client.post(
        "/api/v1/compare/life",
        json={
            "age": 35,
            "smoker_status": "non_smoker",
            "occupation_category": "Manual Trade",
            "product_type": "life_cover",
        },
    )
    body = resp.json()
    beta = next(r for r in body["results"] if r["insurer"] == "Insurer Beta")
    assert beta["eligible"] is False
    assert "excluded" in beta["ineligibility_reason"].lower()


def test_every_criterion_with_a_score_has_a_source_or_is_occupation_restrictions():
    resp = client.post(
        "/api/v1/compare/life",
        json={"age": 35, "smoker_status": "any", "occupation_category": "Professional", "product_type": "life_cover"},
    )
    for result in resp.json()["results"]:
        for name, criterion in result["criteria"].items():
            if criterion["score"] is not None and name != "occupation_restrictions":
                assert criterion["source"] is not None, f"{result['insurer']}.{name} scored with no source"


def test_missing_data_reflected_in_completeness_not_hidden():
    resp = client.post(
        "/api/v1/compare/life",
        json={"age": 35, "smoker_status": "any", "occupation_category": "Professional", "product_type": "life_cover"},
    )
    gamma = next(r for r in resp.json()["results"] if r["insurer"] == "Insurer Gamma")
    assert gamma["data_completeness"] < 1.0
    assert gamma["criteria"]["tpd_definition"]["score"] is None
