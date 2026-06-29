import os
import brok.server as server


def test_review_architecture_description_names_trigger_moments():
    doc = server.review_architecture.__doc__.lower()
    assert "scal" in doc          # scaling / scale
    assert "design" in doc
    assert "trade-off" in doc or "tradeoff" in doc


def test_review_components_description_names_trigger_moments():
    doc = server.review_components.__doc__.lower()
    assert "design" in doc or "scal" in doc
    assert "component" in doc


def test_skill_file_exists_and_triggers_on_design():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skill", "SKILL.md")
    text = open(path, encoding="utf-8").read().lower()
    assert "brok" in text
    assert "scal" in text and "design" in text
    assert "—" not in open(path, encoding="utf-8").read()  # no em dash in shipped copy
