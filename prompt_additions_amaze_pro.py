"""Pruefvorschlag fuer die Amaze-Pro-Unterteil-Promptanpassungen.

Diese Datei veraendert die App oder ``backend/templates.py`` nicht automatisch.
Sie enthaelt nur die vorgeschlagenen Ersetzungen und Ergaenzungen sowie eine
optionale Funktion, mit der sie auf ein bereits geparstes Prompt-Dictionary
angewendet werden koennen.

Konkreter Fehler im Testvideo:
Der SMILODOX-Wordmark-Tag der Leggings wurde auf das Oberteil uebertragen.
In den Referenzen hat das Oberteil stattdessen einen eigenen Icon-Tag.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


TARGET_TEMPLATE = "UNTERTEIL_PROMPT"
SCOPE = "product-specific review proposal for Leggings Amaze Pro"


# Vollstaendige Ersatzwerte fuer bereits vorhandene Felder.
FIELD_REPLACEMENTS = {
    "brand_identity.default_style": (
        "Do not generate branding from a textual brand description. Determine "
        "every visible mark exclusively from the exact garment and location "
        "where it appears in the reference images. Branding is garment-specific "
        "and position-specific. The primary lower garment and the styling upper "
        "garment must be treated as two independent products with independent "
        "marks."
    ),
    "brand_identity.no_invention_rule": (
        "STRICT BRAND-SLOT ISOLATION: image2 and image4 define branding only for "
        "the primary lower garment. Their wordmark, tag shape and lettering must "
        "never be applied to the upper garment or shoes. The upper garment's own "
        "tag is defined only by the upper-garment region visible in image1 and "
        "image3. Preserve that separate mark at its original location, size and "
        "type. Never replace an icon-only upper-garment tag with the lower "
        "garment's SMILODOX wordmark. Never make both garments carry matching "
        "tags unless the references independently show the same mark on both."
    ),
    "shots.shot_02_side_lower_garment.supporting_reference_roles": [
        (
            "image1 for model identity, body proportions, overall lower-garment "
            "silhouette and the upper styling garment's own independent tag type"
        ),
        "image3 for rear construction continuity",
        (
            "image4 only for the lower garment's waistband wordmark; image4 must "
            "not influence the upper garment"
        ),
    ],
    "shots.shot_04_garment_detail.framing": (
        "match image4 as closely as possible and show only the primary lower "
        "garment, its waistband wordmark and the adjacent skin visible in image4; "
        "the upper garment and its separate tag remain completely outside the frame"
    ),
}


# Dieser Satz wird an product_lock.primary_product angehaengt.
PRIMARY_PRODUCT_ADDITION = (
    " CRITICAL BRAND-SLOT LOCK: the visible white SMILODOX wordmark tag on the "
    "lower garment belongs exclusively to the lower garment. It must appear only "
    "at the waistband position shown in the lower-garment references and must "
    "never be copied to the upper garment. The upper garment carries its own "
    "independently referenced icon tag and must not inherit the lower garment's "
    "wordmark, tag proportions or lettering."
)


# Diese Eintraege werden an die vorhandene negative_prompt-Liste angehaengt.
NEGATIVE_PROMPT_ADDITIONS = [
    "lower-garment wordmark copied onto upper garment",
    "SMILODOX text tag replacing upper-garment icon tag",
    "image4 branding applied to upper garment",
    "matching tags on both garments",
    "cross-garment logo transfer",
    "upper-garment logo type changing between shots",
    "upper garment visible in lower-garment detail shot",
]


def _shot_by_id(prompt: dict[str, Any], shot_id: str) -> dict[str, Any]:
    """Findet einen Shot, ohne seine Position im Array vorauszusetzen."""
    for shot in prompt["shots"]:
        if shot.get("id") == shot_id:
            return shot
    raise KeyError(f"Shot nicht gefunden: {shot_id}")


def apply_proposal(source_prompt: dict[str, Any]) -> dict[str, Any]:
    """Gibt eine gepatchte Kopie zur Pruefung zurueck.

    ``source_prompt`` bleibt unveraendert. Erwartet wird das bereits mit
    ``json.loads(UNTERTEIL_PROMPT)`` geparste Dictionary.
    """
    prompt = deepcopy(source_prompt)

    prompt["brand_identity"]["default_style"] = FIELD_REPLACEMENTS[
        "brand_identity.default_style"
    ]
    prompt["brand_identity"]["no_invention_rule"] = FIELD_REPLACEMENTS[
        "brand_identity.no_invention_rule"
    ]

    prompt["product_lock"]["primary_product"] += PRIMARY_PRODUCT_ADDITION

    side_shot = _shot_by_id(prompt, "shot_02_side_lower_garment")
    side_shot["supporting_reference_roles"] = FIELD_REPLACEMENTS[
        "shots.shot_02_side_lower_garment.supporting_reference_roles"
    ]

    detail_shot = _shot_by_id(prompt, "shot_04_garment_detail")
    detail_shot["framing"] = FIELD_REPLACEMENTS[
        "shots.shot_04_garment_detail.framing"
    ]

    for constraint in NEGATIVE_PROMPT_ADDITIONS:
        if constraint not in prompt["negative_prompt"]:
            prompt["negative_prompt"].append(constraint)

    return prompt


if __name__ == "__main__":
    import json

    from backend.templates import UNTERTEIL_PROMPT

    original = json.loads(UNTERTEIL_PROMPT)
    proposed = apply_proposal(original)

    print(json.dumps(proposed, ensure_ascii=False, indent=2))
