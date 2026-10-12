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


BLUEPRINTS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "blueprints", "automation", "norish")


@pytest.mark.parametrize("name", ["meal_reminder.yaml", "recipe_to_groceries.yaml"])
def test_other_blueprints_are_valid(name):
    bp = Blueprint(load_yaml(os.path.join(BLUEPRINTS, name)), expected_domain="automation",
                   schema=BLUEPRINT_SCHEMA)
    config = BlueprintInputs(bp, {"use_blueprint": {"path": f"norish/{name}", "input": {}}}).async_substitute()
    assert config["triggers"] and config["actions"]


def _reminder_fires(events, slot="Dinner"):
    raw = load_yaml(os.path.join(BLUEPRINTS, "meal_reminder.yaml"))
    template = raw["actions"][1]["value_template"]
    env = jinja2.Environment()
    env.tests["search"] = lambda value, pattern: __import__("re").search(pattern, value) is not None
    out = env.from_string(template).render(
        agenda={"calendar.norish_meal_calendar": {"events": events}},
        calendar="calendar.norish_meal_calendar", slot=slot,
    )
    return out.strip() == "True"


def test_reminder_condition():
    lunch = {"summary": "Soep", "description": "Norish – Lunch"}
    dinner = {"summary": "Wraps", "description": "Norish – Dinner"}
    note = {"summary": "Uit eten", "description": "Norish – Dinner (note): Uit eten"}
    other = {"summary": "Verjaardag"}  # not from Norish: no description
    assert _reminder_fires([]) is True
    assert _reminder_fires([lunch, other]) is True
    assert _reminder_fires([lunch, dinner]) is False
    assert _reminder_fires([note]) is False
    assert _reminder_fires([lunch], slot="Lunch") is False
