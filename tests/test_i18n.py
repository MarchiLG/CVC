"""
Tests for the shared translation catalog (src/i18n.py).

The catalog feeds BOTH interfaces — the desktop GUI imports t()
directly, the web UI fetches it through GET /api/i18n — so a key missing
from one language would show up as untranslated text in both. The
completeness test below is what keeps that from happening silently.
"""

import pytest

import i18n
from config.calibration import CalibrationError, build_geometry_params
from config.loader import load_app_config


# ---------------------------------------------------------------------- #
# Catalog integrity
# ---------------------------------------------------------------------- #
def test_only_english_and_portuguese_are_offered():
    assert [code for code, _label in i18n.LANGUAGES] == ["en", "pt"]


def test_english_is_the_default():
    assert i18n.DEFAULT_LANGUAGE == "en"
    assert i18n.LANGUAGES[0][0] == "en"


@pytest.mark.parametrize("code", [code for code, _label in i18n.LANGUAGES])
def test_every_language_has_every_key(code):
    """No language may be missing a key the others define — otherwise
    that string would silently fall back to English in the middle of an
    otherwise translated screen."""
    reference = set(i18n.CATALOG[i18n.DEFAULT_LANGUAGE])

    assert set(i18n.CATALOG[code]) == reference


@pytest.mark.parametrize("code", [code for code, _label in i18n.LANGUAGES])
def test_no_translation_is_empty(code):
    empty = [key for key, value in i18n.CATALOG[code].items() if not value.strip()]

    assert empty == []


def test_placeholders_match_across_languages():
    """{placeholders} must be the same in every language: a translation
    that renames one would render the literal "{name}" on screen."""
    import re

    def placeholders(text):
        return set(re.findall(r"\{(\w+)\}", text))

    mismatched = []
    for key, english in i18n.CATALOG["en"].items():
        for code, _label in i18n.LANGUAGES:
            if placeholders(i18n.CATALOG[code][key]) != placeholders(english):
                mismatched.append((code, key))

    assert mismatched == []


# ---------------------------------------------------------------------- #
# t()
# ---------------------------------------------------------------------- #
def test_translates_and_interpolates():
    assert i18n.t("live.tracked", "en", count=3) == "3 tracked"
    assert i18n.t("live.tracked", "pt", count=3) == "3 rastreado(s)"


def test_unknown_language_falls_back_to_english():
    assert i18n.t("nav.live", "de") == i18n.t("nav.live", "en")


def test_unknown_key_returns_the_key_itself():
    """A missing key must be visible on screen, never a crash."""
    assert i18n.t("does.not.exist", "pt") == "does.not.exist"


def test_missing_placeholder_value_does_not_raise():
    result = i18n.t("live.tracked", "en")  # no count= given

    assert "{count}" in result


def test_normalize_accepts_case_and_whitespace():
    assert i18n.normalize("  PT ") == "pt"
    assert i18n.normalize(None) == "en"
    assert i18n.normalize("klingon") == "en"


# ---------------------------------------------------------------------- #
# app.yaml -> ui.language
# ---------------------------------------------------------------------- #
def test_language_is_read_from_app_yaml(tmp_path):
    path = tmp_path / "app.yaml"
    path.write_text("ui:\n  language: pt\n")

    assert load_app_config(str(path)).ui.language == "pt"


def test_language_defaults_to_english_when_absent(tmp_path):
    path = tmp_path / "app.yaml"
    path.write_text("vision:\n  device: cpu\n")

    assert load_app_config(str(path)).ui.language == "en"


def test_invalid_language_falls_back_instead_of_breaking(tmp_path):
    """A typo in app.yaml must degrade into the default, not stop the
    application from starting."""
    path = tmp_path / "app.yaml"
    path.write_text("ui:\n  language: portugues\n")

    assert load_app_config(str(path)).ui.language == "en"


# ---------------------------------------------------------------------- #
# Error codes reaching the catalog
# ---------------------------------------------------------------------- #
def test_calibration_errors_carry_a_translatable_code():
    """Both interfaces translate CalibrationError.code — the Qt GUI
    through t(), the browser through the same key in i18n.js."""
    with pytest.raises(CalibrationError) as excinfo:
        build_geometry_params("item_counting", {}, [(1.0, 2.0)])

    error = excinfo.value
    assert error.code == "calibration.line_needs_two_points"
    assert error.code in i18n.CATALOG["en"]
    assert error.code in i18n.CATALOG["pt"]
    assert str(error) == i18n.t(error.code, "en")


def test_api_error_codes_all_exist_in_the_catalog():
    """Every ApiError raised in web/api.py must have a translation, or
    the interface would show a raw key like "api.no_frame"."""
    import re
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "src" / "web" / "api.py"
    codes = set(re.findall(r'ApiError\(\s*\d+,\s*"([^"]+)"', source.read_text(encoding="utf-8")))

    assert codes, "no ApiError call was found — did the pattern change?"
    assert codes <= set(i18n.CATALOG["en"])
    assert codes <= set(i18n.CATALOG["pt"])


def test_flag_message_keys_all_exist_in_the_catalog():
    """Same idea for the alert messages produced by the analyzers."""
    import re
    from pathlib import Path

    tasks_dir = Path(__file__).resolve().parents[1] / "src" / "tasks"
    codes = set()
    for path in tasks_dir.glob("*.py"):
        codes.update(re.findall(r'message_key="([^"]+)"', path.read_text(encoding="utf-8")))

    assert codes, "no message_key was found — did the pattern change?"
    assert codes <= set(i18n.CATALOG["en"])
    assert codes <= set(i18n.CATALOG["pt"])
