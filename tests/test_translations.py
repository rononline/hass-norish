"""Tests: translations stay complete and match services.yaml."""
import json
import os

import yaml

BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "custom_components", "norish")


def _load(name):
    with open(os.path.join(BASE, name), encoding="utf-8") as f:
        return json.load(f)


def _keys(d, prefix=""):
    out = set()
    for k, v in d.items():
        out |= _keys(v, f"{prefix}{k}.") if isinstance(v, dict) else {prefix + k}
    return out


def test_en_and_nl_match_strings():
    strings = _keys(_load("strings.json"))
    for lang in ("en", "nl"):
        assert _keys(_load(f"translations/{lang}.json")) == strings, lang


def test_services_are_translated():
    with open(os.path.join(BASE, "services.yaml"), encoding="utf-8") as f:
        services = yaml.safe_load(f)
    strings = _load("strings.json")["services"]
    for name, spec in services.items():
        assert set(spec.get("fields", {})) == set(strings[name]["fields"]), name
