"""Tests: the 'what's for dinner' blueprint is valid and answers correctly."""
import os

import jinja2
import pytest
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.util.yaml import load_yaml

PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                    "blueprints", "automation", "norish", "whats_for_dinner.yaml")


def test_blueprint_is_valid():
    bp = Blueprint(load_yaml(PATH), expected_domain="automation", schema=BLUEPRINT_SCHEMA)
    assert bp.domain == "automation"
    assert set(bp.inputs) >= {"planner", "sentences", "answer_today", "answer_nothing"}
    # every input has a default, so the automation works without filling anything in
    config = BlueprintInputs(bp, {"use_blueprint": {"path": "norish/whats_for_dinner.yaml", "input": {}}}).async_substitute()
    assert config["triggers"][0]["command"][0] == "wat eten we vanavond"
    assert config["actions"][0]["set_conversation_response"]


WEEK = [
    {"date": "2026-10-12", "meals": [{"name": "Wraps", "type": "DINNER"}, {"name": "Soep", "type": "LUNCH"}]},
    {"date": "2026-10-13", "meals": [{"name": "Lasagne", "type": "DINNER"}, {"name": "Salade", "type": "DINNER"}]},
    {"date": "2026-10-14", "meals": []},
]


def _answer(sentence, week=WEEK):
    raw = load_yaml(PATH)
    template = raw["variables"]["answer"]
    defaults = {k: v.get("default") for k, v in raw["blueprint"]["input"].items()}
    env = jinja2.Environment()
    env.filters["selectattr"] = env.filters["selectattr"]
    out = env.from_string(template).render(
        state_attr=lambda entity, attr: week if attr == "week_data" else None,
        trigger={"sentence": sentence},
        planner="sensor.norish_week_planner",
        tomorrow_word=defaults["tomorrow_word"], meal_type=defaults["meal_type"],
        answer_today=defaults["answer_today"], answer_tomorrow=defaults["answer_tomorrow"],
        answer_nothing=defaults["answer_nothing"], joiner=defaults["joiner"],
    )
    return " ".join(out.split())


@pytest.mark.parametrize("sentence,expected", [
    ("wat eten we vanavond", "Vanavond eten we Wraps."),
    ("Wat eten we morgen", "Morgen eten we Lasagne en Salade."),
])
def test_answers(sentence, expected):
    assert _answer(sentence) == expected


def test_nothing_planned():
    assert _answer("wat eten we vanavond", [{"meals": []}]) == "Daar staat in Norish nog niets voor gepland."
    assert _answer("wat eten we morgen", []) == "Daar staat in Norish nog niets voor gepland."
