"""Generate write-side pydantic v2 models from official FHIR R4 4.0.1 StructureDefinitions.

We emit FHIR; we do not parse arbitrary FHIR. That asymmetry is what keeps this
codegen small enough to own outright (see build doc Section 4) instead of taking a
dependency on `fhir.resources`, which dropped R4 4.0.1 at v7.0.0.

Run:  python -m carebundle.spec.codegen
"""

from __future__ import annotations

import json
import keyword
from collections import OrderedDict
from pathlib import Path

SPEC_DIR = Path(__file__).resolve().parents[2] / ".tools" / "spec"
MODELS_DIR = Path(__file__).resolve().parents[1] / "models"

FHIR_VERSION = "4.0.1"

# Resources in v1 scope (build doc Section 5).
TARGET_RESOURCES = [
    "Patient",
    "Encounter",
    "Condition",
    "Observation",
    "MedicationRequest",
    "DiagnosticReport",
    "AllergyIntolerance",
    "Bundle",
    # Not in the build doc's original scope list. US Core pulls it in: the
    # MedicationRequest profile requires a requester, and a dangling reference is not
    # conformant. Discovered by the Phase 1 validator run, not by reading the IG.
    "Practitioner",
]

# FHIR primitive -> Python annotation. Dates and decimals stay strings/Decimal so we
# keep byte-exact control over serialization; float would break both the determinism
# contract (Section 9) and lab-value precision.
PRIMITIVES = {
    "boolean": "bool",
    "integer": "int",
    "positiveInt": "int",
    "unsignedInt": "int",
    "decimal": "Decimal",
    "string": "str",
    "code": "str",
    "id": "str",
    "uri": "str",
    "url": "str",
    "canonical": "str",
    "oid": "str",
    "uuid": "str",
    "markdown": "str",
    "base64Binary": "str",
    "xhtml": "str",
    "date": "str",
    "dateTime": "str",
    "instant": "str",
    "time": "str",
    "http://hl7.org/fhirpath/System.String": "str",
}

# Elements we deliberately do not generate on the write side.
SKIP_ELEMENTS = {"contained", "modifierExtension"}

# Abstract/recursive types we represent loosely rather than modelling.
OPAQUE_TYPES = {"Resource", "Element", "BackboneElement"}


def load_structure_definitions() -> dict[str, dict]:
    """Index every StructureDefinition in the R4 spec bundles by type name."""
    sds: dict[str, dict] = {}
    for filename in ("profiles-types.json", "profiles-resources.json"):
        bundle = json.loads((SPEC_DIR / filename).read_text(encoding="utf-8"))
        for entry in bundle["entry"]:
            resource = entry["resource"]
            if resource.get("resourceType") != "StructureDefinition":
                continue
            if resource.get("kind") in ("complex-type", "resource"):
                sds[resource["id"]] = resource
    return sds


def field_name_for(path: str, element: dict) -> tuple[str, str]:
    """Return (python_name, fhir_wire_name) for an element path.

    Choice elements (`value[x]`) are expanded by the caller; this handles the
    keyword collisions FHIR produces, e.g. Encounter.class -> class_.
    """
    wire = path.rsplit(".", 1)[-1]
    py = wire
    if keyword.iskeyword(py) or py in ("class", "global", "import", "from"):
        py = py + "_"
    return py, wire


def class_name_for(path: str) -> str:
    """BackboneElement path -> class name. Patient.contact -> PatientContact."""
    return "".join(part[:1].upper() + part[1:] for part in path.split("."))


class Generator:
    def __init__(self, sds: dict[str, dict]):
        self.sds = sds
        self.emitted: OrderedDict[str, str] = OrderedDict()
        self.needed_complex: set[str] = set()

    def annotation_for(self, type_code: str, path: str) -> str:
        if type_code in PRIMITIVES:
            return PRIMITIVES[type_code]
        if type_code in OPAQUE_TYPES:
            return "dict"
        self.needed_complex.add(type_code)
        # No quotes needed: `from __future__ import annotations` makes every
        # annotation lazy, so forward refs resolve at model_rebuild() time.
        return type_code

    def children_of(self, elements: list[dict], parent_path: str) -> list[dict]:
        depth = parent_path.count(".") + 1
        return [
            e
            for e in elements
            if e["path"].startswith(parent_path + ".")
            and e["path"].count(".") == depth
        ]

    def emit_class(self, sd: dict, root_path: str, class_name: str) -> None:
        """Emit one pydantic class, recursing into BackboneElements first."""
        if class_name in self.emitted:
            return
        self.emitted[class_name] = ""  # reserve slot to stop recursion

        elements = sd["snapshot"]["element"]
        lines: list[str] = [f"class {class_name}(FHIRBase):"]
        is_resource = sd.get("kind") == "resource" and root_path == sd["id"]
        if is_resource:
            lines.append(
                f'    resourceType: Literal["{sd["id"]}"] = "{sd["id"]}"'
            )

        body: list[str] = []
        nested: list[tuple[dict, str, str]] = []

        for element in self.children_of(elements, root_path):
            path = element["path"]
            wire_base = path.rsplit(".", 1)[-1]
            if wire_base in SKIP_ELEMENTS:
                continue

            max_card = element.get("max", "1")
            is_list = max_card == "*" or (max_card.isdigit() and int(max_card) > 1)
            required = element.get("min", 0) >= 1

            types = element.get("type", [])
            if not types and "contentReference" in element:
                # e.g. Questionnaire.item.item -> "#Questionnaire.item"
                ref_path = element["contentReference"].lstrip("#")
                ref_class = class_name_for(ref_path)
                ref_sd = self.sds.get(ref_path.split(".")[0])
                if ref_sd:
                    nested.append((ref_sd, ref_path, ref_class))
                body.append(
                    self.render_field(
                        *field_name_for(path, element),
                        ref_class,
                        is_list,
                        required,
                    )
                )
                continue
            if not types:
                continue

            # BackboneElement / Element -> nested class
            if types[0].get("code") in ("BackboneElement", "Element") and any(
                e["path"].startswith(path + ".") for e in elements
            ):
                nested_class = class_name_for(path)
                nested.append((sd, path, nested_class))
                body.append(
                    self.render_field(
                        *field_name_for(path, element),
                        nested_class,
                        is_list,
                        required,
                    )
                )
                continue

            if path.endswith("[x]"):
                # Choice type: expand to one field per permitted type.
                base = wire_base[: -len("[x]")]
                for t in types:
                    code = t.get("code")
                    suffix = code[:1].upper() + code[1:]
                    wire = f"{base}{suffix}"
                    py = wire
                    if keyword.iskeyword(py):
                        py += "_"
                    body.append(
                        self.render_field(
                            py,
                            wire,
                            self.annotation_for(code, path),
                            is_list,
                            False,  # a choice member is never individually required
                        )
                    )
                continue

            annotation = self.annotation_for(types[0].get("code"), path)
            body.append(
                self.render_field(
                    *field_name_for(path, element), annotation, is_list, required
                )
            )

        for nested_sd, nested_path, nested_name in nested:
            self.emit_class(nested_sd, nested_path, nested_name)

        if not body and not is_resource:
            body.append("    pass")
        lines.extend(body)
        self.emitted[class_name] = "\n".join(lines) + "\n"

    @staticmethod
    def render_field(
        py_name: str, wire_name: str, annotation: str, is_list: bool, required: bool
    ) -> str:
        if is_list:
            annotation = f"list[{annotation}]"
        alias = "" if py_name == wire_name else f'alias="{wire_name}", '
        if required:
            default = f"Field({alias.rstrip(', ')})" if alias else "Field()"
            return f"    {py_name}: {annotation} = {default}"
        return f"    {py_name}: {annotation} | None = Field({alias}default=None)"

    def run(self) -> str:
        # Seed with the target resources, then close over every datatype they reach.
        for name in TARGET_RESOURCES:
            self.emit_class(self.sds[name], name, name)

        processed: set[str] = set()
        while True:
            pending = self.needed_complex - processed - set(self.emitted)
            if not pending:
                break
            for type_name in sorted(pending):
                processed.add(type_name)
                sd = self.sds.get(type_name)
                if sd is None:
                    continue
                self.emit_class(sd, type_name, type_name)

        header = f'''"""GENERATED FILE — do not edit by hand.

Written by carebundle/spec/codegen.py from the official FHIR R4 {FHIR_VERSION}
StructureDefinitions. Regenerate with:  python -m carebundle.spec.codegen
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FHIRBase(BaseModel):
    """Write-side base. Aliases carry FHIR wire names for keyword-clashing fields."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        ser_json_inf_nan="strings",
    )


'''
        # Datatypes first so forward refs resolve predictably, then resources.
        datatype_classes = [
            name for name in self.emitted if name not in TARGET_RESOURCES
        ]
        ordered = datatype_classes + [
            n for n in TARGET_RESOURCES if n in self.emitted
        ]
        body = "\n\n".join(self.emitted[name] for name in ordered)

        rebuilds = "\n".join(f"{name}.model_rebuild()" for name in ordered)
        return header + body + "\n\n" + rebuilds + "\n"


def main() -> None:
    sds = load_structure_definitions()
    generator = Generator(sds)
    source = generator.run()
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    out = MODELS_DIR / "r4.py"
    out.write_text(source, encoding="utf-8")
    classes = len(generator.emitted)
    print(f"generated {classes} classes -> {out.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
