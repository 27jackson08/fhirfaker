"""GENERATED FILE — do not edit by hand.

Written by carebundle/spec/codegen.py from the official FHIR R4 4.0.1
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


class PatientContact(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    relationship: list[CodeableConcept] | None = Field(default=None)
    name: HumanName | None = Field(default=None)
    telecom: list[ContactPoint] | None = Field(default=None)
    address: Address | None = Field(default=None)
    gender: str | None = Field(default=None)
    organization: Reference | None = Field(default=None)
    period: Period | None = Field(default=None)


class PatientCommunication(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    language: CodeableConcept = Field()
    preferred: bool | None = Field(default=None)


class PatientLink(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    other: Reference = Field()
    type: str = Field()


class EncounterStatusHistory(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    status: str = Field()
    period: Period = Field()


class EncounterClassHistory(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    class_: Coding = Field(alias="class")
    period: Period = Field()


class EncounterParticipant(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    type: list[CodeableConcept] | None = Field(default=None)
    period: Period | None = Field(default=None)
    individual: Reference | None = Field(default=None)


class EncounterDiagnosis(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    condition: Reference = Field()
    use: CodeableConcept | None = Field(default=None)
    rank: int | None = Field(default=None)


class EncounterHospitalization(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    preAdmissionIdentifier: Identifier | None = Field(default=None)
    origin: Reference | None = Field(default=None)
    admitSource: CodeableConcept | None = Field(default=None)
    reAdmission: CodeableConcept | None = Field(default=None)
    dietPreference: list[CodeableConcept] | None = Field(default=None)
    specialCourtesy: list[CodeableConcept] | None = Field(default=None)
    specialArrangement: list[CodeableConcept] | None = Field(default=None)
    destination: Reference | None = Field(default=None)
    dischargeDisposition: CodeableConcept | None = Field(default=None)


class EncounterLocation(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    location: Reference = Field()
    status: str | None = Field(default=None)
    physicalType: CodeableConcept | None = Field(default=None)
    period: Period | None = Field(default=None)


class ConditionStage(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    summary: CodeableConcept | None = Field(default=None)
    assessment: list[Reference] | None = Field(default=None)
    type: CodeableConcept | None = Field(default=None)


class ConditionEvidence(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    code: list[CodeableConcept] | None = Field(default=None)
    detail: list[Reference] | None = Field(default=None)


class ObservationReferenceRange(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    low: Quantity | None = Field(default=None)
    high: Quantity | None = Field(default=None)
    type: CodeableConcept | None = Field(default=None)
    appliesTo: list[CodeableConcept] | None = Field(default=None)
    age: Range | None = Field(default=None)
    text: str | None = Field(default=None)


class ObservationComponent(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    code: CodeableConcept = Field()
    valueQuantity: Quantity | None = Field(default=None)
    valueCodeableConcept: CodeableConcept | None = Field(default=None)
    valueString: str | None = Field(default=None)
    valueBoolean: bool | None = Field(default=None)
    valueInteger: int | None = Field(default=None)
    valueRange: Range | None = Field(default=None)
    valueRatio: Ratio | None = Field(default=None)
    valueSampledData: SampledData | None = Field(default=None)
    valueTime: str | None = Field(default=None)
    valueDateTime: str | None = Field(default=None)
    valuePeriod: Period | None = Field(default=None)
    dataAbsentReason: CodeableConcept | None = Field(default=None)
    interpretation: list[CodeableConcept] | None = Field(default=None)
    referenceRange: list[ObservationReferenceRange] | None = Field(default=None)


class MedicationRequestDispenseRequest(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    initialFill: MedicationRequestDispenseRequestInitialFill | None = Field(default=None)
    dispenseInterval: Duration | None = Field(default=None)
    validityPeriod: Period | None = Field(default=None)
    numberOfRepeatsAllowed: int | None = Field(default=None)
    quantity: Quantity | None = Field(default=None)
    expectedSupplyDuration: Duration | None = Field(default=None)
    performer: Reference | None = Field(default=None)


class MedicationRequestDispenseRequestInitialFill(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    quantity: Quantity | None = Field(default=None)
    duration: Duration | None = Field(default=None)


class MedicationRequestSubstitution(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    allowedBoolean: bool | None = Field(default=None)
    allowedCodeableConcept: CodeableConcept | None = Field(default=None)
    reason: CodeableConcept | None = Field(default=None)


class DiagnosticReportMedia(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    comment: str | None = Field(default=None)
    link: Reference = Field()


class AllergyIntoleranceReaction(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    substance: CodeableConcept | None = Field(default=None)
    manifestation: list[CodeableConcept] = Field()
    description: str | None = Field(default=None)
    onset: str | None = Field(default=None)
    severity: str | None = Field(default=None)
    exposureRoute: CodeableConcept | None = Field(default=None)
    note: list[Annotation] | None = Field(default=None)


class BundleLink(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    relation: str = Field()
    url: str = Field()


class BundleEntry(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    link: list[BundleLink] | None = Field(default=None)
    fullUrl: str | None = Field(default=None)
    resource: dict | None = Field(default=None)
    search: BundleEntrySearch | None = Field(default=None)
    request: BundleEntryRequest | None = Field(default=None)
    response: BundleEntryResponse | None = Field(default=None)


class BundleEntrySearch(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    mode: str | None = Field(default=None)
    score: Decimal | None = Field(default=None)


class BundleEntryRequest(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    method: str = Field()
    url: str = Field()
    ifNoneMatch: str | None = Field(default=None)
    ifModifiedSince: str | None = Field(default=None)
    ifMatch: str | None = Field(default=None)
    ifNoneExist: str | None = Field(default=None)


class BundleEntryResponse(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    status: str = Field()
    location: str | None = Field(default=None)
    etag: str | None = Field(default=None)
    lastModified: str | None = Field(default=None)
    outcome: dict | None = Field(default=None)


class PractitionerQualification(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    identifier: list[Identifier] | None = Field(default=None)
    code: CodeableConcept = Field()
    period: Period | None = Field(default=None)
    issuer: Reference | None = Field(default=None)


class Address(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    use: str | None = Field(default=None)
    type: str | None = Field(default=None)
    text: str | None = Field(default=None)
    line: list[str] | None = Field(default=None)
    city: str | None = Field(default=None)
    district: str | None = Field(default=None)
    state: str | None = Field(default=None)
    postalCode: str | None = Field(default=None)
    country: str | None = Field(default=None)
    period: Period | None = Field(default=None)


class Age(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    value: Decimal | None = Field(default=None)
    comparator: str | None = Field(default=None)
    unit: str | None = Field(default=None)
    system: str | None = Field(default=None)
    code: str | None = Field(default=None)


class Annotation(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    authorReference: Reference | None = Field(default=None)
    authorString: str | None = Field(default=None)
    time: str | None = Field(default=None)
    text: str = Field()


class Attachment(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    contentType: str | None = Field(default=None)
    language: str | None = Field(default=None)
    data: str | None = Field(default=None)
    url: str | None = Field(default=None)
    size: int | None = Field(default=None)
    hash: str | None = Field(default=None)
    title: str | None = Field(default=None)
    creation: str | None = Field(default=None)


class CodeableConcept(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    coding: list[Coding] | None = Field(default=None)
    text: str | None = Field(default=None)


class Coding(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    system: str | None = Field(default=None)
    version: str | None = Field(default=None)
    code: str | None = Field(default=None)
    display: str | None = Field(default=None)
    userSelected: bool | None = Field(default=None)


class ContactPoint(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    system: str | None = Field(default=None)
    value: str | None = Field(default=None)
    use: str | None = Field(default=None)
    rank: int | None = Field(default=None)
    period: Period | None = Field(default=None)


class Dosage(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    sequence: int | None = Field(default=None)
    text: str | None = Field(default=None)
    additionalInstruction: list[CodeableConcept] | None = Field(default=None)
    patientInstruction: str | None = Field(default=None)
    timing: Timing | None = Field(default=None)
    asNeededBoolean: bool | None = Field(default=None)
    asNeededCodeableConcept: CodeableConcept | None = Field(default=None)
    site: CodeableConcept | None = Field(default=None)
    route: CodeableConcept | None = Field(default=None)
    method: CodeableConcept | None = Field(default=None)
    doseAndRate: list[DosageDoseAndRate] | None = Field(default=None)
    maxDosePerPeriod: Ratio | None = Field(default=None)
    maxDosePerAdministration: Quantity | None = Field(default=None)
    maxDosePerLifetime: Quantity | None = Field(default=None)


class DosageDoseAndRate(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    type: CodeableConcept | None = Field(default=None)
    doseRange: Range | None = Field(default=None)
    doseQuantity: Quantity | None = Field(default=None)
    rateRatio: Ratio | None = Field(default=None)
    rateRange: Range | None = Field(default=None)
    rateQuantity: Quantity | None = Field(default=None)


class Duration(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    value: Decimal | None = Field(default=None)
    comparator: str | None = Field(default=None)
    unit: str | None = Field(default=None)
    system: str | None = Field(default=None)
    code: str | None = Field(default=None)


class Extension(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    url: str = Field()
    valueBase64Binary: str | None = Field(default=None)
    valueBoolean: bool | None = Field(default=None)
    valueCanonical: str | None = Field(default=None)
    valueCode: str | None = Field(default=None)
    valueDate: str | None = Field(default=None)
    valueDateTime: str | None = Field(default=None)
    valueDecimal: Decimal | None = Field(default=None)
    valueId: str | None = Field(default=None)
    valueInstant: str | None = Field(default=None)
    valueInteger: int | None = Field(default=None)
    valueMarkdown: str | None = Field(default=None)
    valueOid: str | None = Field(default=None)
    valuePositiveInt: int | None = Field(default=None)
    valueString: str | None = Field(default=None)
    valueTime: str | None = Field(default=None)
    valueUnsignedInt: int | None = Field(default=None)
    valueUri: str | None = Field(default=None)
    valueUrl: str | None = Field(default=None)
    valueUuid: str | None = Field(default=None)
    valueAddress: Address | None = Field(default=None)
    valueAge: Age | None = Field(default=None)
    valueAnnotation: Annotation | None = Field(default=None)
    valueAttachment: Attachment | None = Field(default=None)
    valueCodeableConcept: CodeableConcept | None = Field(default=None)
    valueCoding: Coding | None = Field(default=None)
    valueContactPoint: ContactPoint | None = Field(default=None)
    valueCount: Count | None = Field(default=None)
    valueDistance: Distance | None = Field(default=None)
    valueDuration: Duration | None = Field(default=None)
    valueHumanName: HumanName | None = Field(default=None)
    valueIdentifier: Identifier | None = Field(default=None)
    valueMoney: Money | None = Field(default=None)
    valuePeriod: Period | None = Field(default=None)
    valueQuantity: Quantity | None = Field(default=None)
    valueRange: Range | None = Field(default=None)
    valueRatio: Ratio | None = Field(default=None)
    valueReference: Reference | None = Field(default=None)
    valueSampledData: SampledData | None = Field(default=None)
    valueSignature: Signature | None = Field(default=None)
    valueTiming: Timing | None = Field(default=None)
    valueContactDetail: ContactDetail | None = Field(default=None)
    valueContributor: Contributor | None = Field(default=None)
    valueDataRequirement: DataRequirement | None = Field(default=None)
    valueExpression: Expression | None = Field(default=None)
    valueParameterDefinition: ParameterDefinition | None = Field(default=None)
    valueRelatedArtifact: RelatedArtifact | None = Field(default=None)
    valueTriggerDefinition: TriggerDefinition | None = Field(default=None)
    valueUsageContext: UsageContext | None = Field(default=None)
    valueDosage: Dosage | None = Field(default=None)
    valueMeta: Meta | None = Field(default=None)


class HumanName(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    use: str | None = Field(default=None)
    text: str | None = Field(default=None)
    family: str | None = Field(default=None)
    given: list[str] | None = Field(default=None)
    prefix: list[str] | None = Field(default=None)
    suffix: list[str] | None = Field(default=None)
    period: Period | None = Field(default=None)


class Identifier(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    use: str | None = Field(default=None)
    type: CodeableConcept | None = Field(default=None)
    system: str | None = Field(default=None)
    value: str | None = Field(default=None)
    period: Period | None = Field(default=None)
    assigner: Reference | None = Field(default=None)


class Meta(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    versionId: str | None = Field(default=None)
    lastUpdated: str | None = Field(default=None)
    source: str | None = Field(default=None)
    profile: list[str] | None = Field(default=None)
    security: list[Coding] | None = Field(default=None)
    tag: list[Coding] | None = Field(default=None)


class Narrative(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    status: str = Field()
    div: str = Field()


class Period(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    start: str | None = Field(default=None)
    end: str | None = Field(default=None)


class Quantity(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    value: Decimal | None = Field(default=None)
    comparator: str | None = Field(default=None)
    unit: str | None = Field(default=None)
    system: str | None = Field(default=None)
    code: str | None = Field(default=None)


class Range(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    low: Quantity | None = Field(default=None)
    high: Quantity | None = Field(default=None)


class Ratio(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    numerator: Quantity | None = Field(default=None)
    denominator: Quantity | None = Field(default=None)


class Reference(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    reference: str | None = Field(default=None)
    type: str | None = Field(default=None)
    identifier: Identifier | None = Field(default=None)
    display: str | None = Field(default=None)


class SampledData(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    origin: Quantity = Field()
    period: Decimal = Field()
    factor: Decimal | None = Field(default=None)
    lowerLimit: Decimal | None = Field(default=None)
    upperLimit: Decimal | None = Field(default=None)
    dimensions: int = Field()
    data: str | None = Field(default=None)


class Signature(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    type: list[Coding] = Field()
    when: str = Field()
    who: Reference = Field()
    onBehalfOf: Reference | None = Field(default=None)
    targetFormat: str | None = Field(default=None)
    sigFormat: str | None = Field(default=None)
    data: str | None = Field(default=None)


class Timing(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    event: list[str] | None = Field(default=None)
    repeat: TimingRepeat | None = Field(default=None)
    code: CodeableConcept | None = Field(default=None)


class TimingRepeat(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    boundsDuration: Duration | None = Field(default=None)
    boundsRange: Range | None = Field(default=None)
    boundsPeriod: Period | None = Field(default=None)
    count: int | None = Field(default=None)
    countMax: int | None = Field(default=None)
    duration: Decimal | None = Field(default=None)
    durationMax: Decimal | None = Field(default=None)
    durationUnit: str | None = Field(default=None)
    frequency: int | None = Field(default=None)
    frequencyMax: int | None = Field(default=None)
    period: Decimal | None = Field(default=None)
    periodMax: Decimal | None = Field(default=None)
    periodUnit: str | None = Field(default=None)
    dayOfWeek: list[str] | None = Field(default=None)
    timeOfDay: list[str] | None = Field(default=None)
    when: list[str] | None = Field(default=None)
    offset: int | None = Field(default=None)


class ContactDetail(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    name: str | None = Field(default=None)
    telecom: list[ContactPoint] | None = Field(default=None)


class Contributor(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    type: str = Field()
    name: str = Field()
    contact: list[ContactDetail] | None = Field(default=None)


class Count(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    value: Decimal | None = Field(default=None)
    comparator: str | None = Field(default=None)
    unit: str | None = Field(default=None)
    system: str | None = Field(default=None)
    code: str | None = Field(default=None)


class DataRequirement(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    type: str = Field()
    profile: list[str] | None = Field(default=None)
    subjectCodeableConcept: CodeableConcept | None = Field(default=None)
    subjectReference: Reference | None = Field(default=None)
    mustSupport: list[str] | None = Field(default=None)
    codeFilter: list[DataRequirementCodeFilter] | None = Field(default=None)
    dateFilter: list[DataRequirementDateFilter] | None = Field(default=None)
    limit: int | None = Field(default=None)
    sort: list[DataRequirementSort] | None = Field(default=None)


class DataRequirementCodeFilter(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    path: str | None = Field(default=None)
    searchParam: str | None = Field(default=None)
    valueSet: str | None = Field(default=None)
    code: list[Coding] | None = Field(default=None)


class DataRequirementDateFilter(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    path: str | None = Field(default=None)
    searchParam: str | None = Field(default=None)
    valueDateTime: str | None = Field(default=None)
    valuePeriod: Period | None = Field(default=None)
    valueDuration: Duration | None = Field(default=None)


class DataRequirementSort(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    path: str = Field()
    direction: str = Field()


class Distance(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    value: Decimal | None = Field(default=None)
    comparator: str | None = Field(default=None)
    unit: str | None = Field(default=None)
    system: str | None = Field(default=None)
    code: str | None = Field(default=None)


class Expression(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    description: str | None = Field(default=None)
    name: str | None = Field(default=None)
    language: str = Field()
    expression: str | None = Field(default=None)
    reference: str | None = Field(default=None)


class Money(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    value: Decimal | None = Field(default=None)
    currency: str | None = Field(default=None)


class ParameterDefinition(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    name: str | None = Field(default=None)
    use: str = Field()
    min: int | None = Field(default=None)
    max: str | None = Field(default=None)
    documentation: str | None = Field(default=None)
    type: str = Field()
    profile: str | None = Field(default=None)


class RelatedArtifact(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    type: str = Field()
    label: str | None = Field(default=None)
    display: str | None = Field(default=None)
    citation: str | None = Field(default=None)
    url: str | None = Field(default=None)
    document: Attachment | None = Field(default=None)
    resource: str | None = Field(default=None)


class TriggerDefinition(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    type: str = Field()
    name: str | None = Field(default=None)
    timingTiming: Timing | None = Field(default=None)
    timingReference: Reference | None = Field(default=None)
    timingDate: str | None = Field(default=None)
    timingDateTime: str | None = Field(default=None)
    data: list[DataRequirement] | None = Field(default=None)
    condition: Expression | None = Field(default=None)


class UsageContext(FHIRBase):
    id: str | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    code: Coding = Field()
    valueCodeableConcept: CodeableConcept | None = Field(default=None)
    valueQuantity: Quantity | None = Field(default=None)
    valueRange: Range | None = Field(default=None)
    valueReference: Reference | None = Field(default=None)


class Patient(FHIRBase):
    resourceType: Literal["Patient"] = "Patient"
    id: str | None = Field(default=None)
    meta: Meta | None = Field(default=None)
    implicitRules: str | None = Field(default=None)
    language: str | None = Field(default=None)
    text: Narrative | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    identifier: list[Identifier] | None = Field(default=None)
    active: bool | None = Field(default=None)
    name: list[HumanName] | None = Field(default=None)
    telecom: list[ContactPoint] | None = Field(default=None)
    gender: str | None = Field(default=None)
    birthDate: str | None = Field(default=None)
    deceasedBoolean: bool | None = Field(default=None)
    deceasedDateTime: str | None = Field(default=None)
    address: list[Address] | None = Field(default=None)
    maritalStatus: CodeableConcept | None = Field(default=None)
    multipleBirthBoolean: bool | None = Field(default=None)
    multipleBirthInteger: int | None = Field(default=None)
    photo: list[Attachment] | None = Field(default=None)
    contact: list[PatientContact] | None = Field(default=None)
    communication: list[PatientCommunication] | None = Field(default=None)
    generalPractitioner: list[Reference] | None = Field(default=None)
    managingOrganization: Reference | None = Field(default=None)
    link: list[PatientLink] | None = Field(default=None)


class Encounter(FHIRBase):
    resourceType: Literal["Encounter"] = "Encounter"
    id: str | None = Field(default=None)
    meta: Meta | None = Field(default=None)
    implicitRules: str | None = Field(default=None)
    language: str | None = Field(default=None)
    text: Narrative | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    identifier: list[Identifier] | None = Field(default=None)
    status: str = Field()
    statusHistory: list[EncounterStatusHistory] | None = Field(default=None)
    class_: Coding = Field(alias="class")
    classHistory: list[EncounterClassHistory] | None = Field(default=None)
    type: list[CodeableConcept] | None = Field(default=None)
    serviceType: CodeableConcept | None = Field(default=None)
    priority: CodeableConcept | None = Field(default=None)
    subject: Reference | None = Field(default=None)
    episodeOfCare: list[Reference] | None = Field(default=None)
    basedOn: list[Reference] | None = Field(default=None)
    participant: list[EncounterParticipant] | None = Field(default=None)
    appointment: list[Reference] | None = Field(default=None)
    period: Period | None = Field(default=None)
    length: Duration | None = Field(default=None)
    reasonCode: list[CodeableConcept] | None = Field(default=None)
    reasonReference: list[Reference] | None = Field(default=None)
    diagnosis: list[EncounterDiagnosis] | None = Field(default=None)
    account: list[Reference] | None = Field(default=None)
    hospitalization: EncounterHospitalization | None = Field(default=None)
    location: list[EncounterLocation] | None = Field(default=None)
    serviceProvider: Reference | None = Field(default=None)
    partOf: Reference | None = Field(default=None)


class Condition(FHIRBase):
    resourceType: Literal["Condition"] = "Condition"
    id: str | None = Field(default=None)
    meta: Meta | None = Field(default=None)
    implicitRules: str | None = Field(default=None)
    language: str | None = Field(default=None)
    text: Narrative | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    identifier: list[Identifier] | None = Field(default=None)
    clinicalStatus: CodeableConcept | None = Field(default=None)
    verificationStatus: CodeableConcept | None = Field(default=None)
    category: list[CodeableConcept] | None = Field(default=None)
    severity: CodeableConcept | None = Field(default=None)
    code: CodeableConcept | None = Field(default=None)
    bodySite: list[CodeableConcept] | None = Field(default=None)
    subject: Reference = Field()
    encounter: Reference | None = Field(default=None)
    onsetDateTime: str | None = Field(default=None)
    onsetAge: Age | None = Field(default=None)
    onsetPeriod: Period | None = Field(default=None)
    onsetRange: Range | None = Field(default=None)
    onsetString: str | None = Field(default=None)
    abatementDateTime: str | None = Field(default=None)
    abatementAge: Age | None = Field(default=None)
    abatementPeriod: Period | None = Field(default=None)
    abatementRange: Range | None = Field(default=None)
    abatementString: str | None = Field(default=None)
    recordedDate: str | None = Field(default=None)
    recorder: Reference | None = Field(default=None)
    asserter: Reference | None = Field(default=None)
    stage: list[ConditionStage] | None = Field(default=None)
    evidence: list[ConditionEvidence] | None = Field(default=None)
    note: list[Annotation] | None = Field(default=None)


class Observation(FHIRBase):
    resourceType: Literal["Observation"] = "Observation"
    id: str | None = Field(default=None)
    meta: Meta | None = Field(default=None)
    implicitRules: str | None = Field(default=None)
    language: str | None = Field(default=None)
    text: Narrative | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    identifier: list[Identifier] | None = Field(default=None)
    basedOn: list[Reference] | None = Field(default=None)
    partOf: list[Reference] | None = Field(default=None)
    status: str = Field()
    category: list[CodeableConcept] | None = Field(default=None)
    code: CodeableConcept = Field()
    subject: Reference | None = Field(default=None)
    focus: list[Reference] | None = Field(default=None)
    encounter: Reference | None = Field(default=None)
    effectiveDateTime: str | None = Field(default=None)
    effectivePeriod: Period | None = Field(default=None)
    effectiveTiming: Timing | None = Field(default=None)
    effectiveInstant: str | None = Field(default=None)
    issued: str | None = Field(default=None)
    performer: list[Reference] | None = Field(default=None)
    valueQuantity: Quantity | None = Field(default=None)
    valueCodeableConcept: CodeableConcept | None = Field(default=None)
    valueString: str | None = Field(default=None)
    valueBoolean: bool | None = Field(default=None)
    valueInteger: int | None = Field(default=None)
    valueRange: Range | None = Field(default=None)
    valueRatio: Ratio | None = Field(default=None)
    valueSampledData: SampledData | None = Field(default=None)
    valueTime: str | None = Field(default=None)
    valueDateTime: str | None = Field(default=None)
    valuePeriod: Period | None = Field(default=None)
    dataAbsentReason: CodeableConcept | None = Field(default=None)
    interpretation: list[CodeableConcept] | None = Field(default=None)
    note: list[Annotation] | None = Field(default=None)
    bodySite: CodeableConcept | None = Field(default=None)
    method: CodeableConcept | None = Field(default=None)
    specimen: Reference | None = Field(default=None)
    device: Reference | None = Field(default=None)
    referenceRange: list[ObservationReferenceRange] | None = Field(default=None)
    hasMember: list[Reference] | None = Field(default=None)
    derivedFrom: list[Reference] | None = Field(default=None)
    component: list[ObservationComponent] | None = Field(default=None)


class MedicationRequest(FHIRBase):
    resourceType: Literal["MedicationRequest"] = "MedicationRequest"
    id: str | None = Field(default=None)
    meta: Meta | None = Field(default=None)
    implicitRules: str | None = Field(default=None)
    language: str | None = Field(default=None)
    text: Narrative | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    identifier: list[Identifier] | None = Field(default=None)
    status: str = Field()
    statusReason: CodeableConcept | None = Field(default=None)
    intent: str = Field()
    category: list[CodeableConcept] | None = Field(default=None)
    priority: str | None = Field(default=None)
    doNotPerform: bool | None = Field(default=None)
    reportedBoolean: bool | None = Field(default=None)
    reportedReference: Reference | None = Field(default=None)
    medicationCodeableConcept: CodeableConcept | None = Field(default=None)
    medicationReference: Reference | None = Field(default=None)
    subject: Reference = Field()
    encounter: Reference | None = Field(default=None)
    supportingInformation: list[Reference] | None = Field(default=None)
    authoredOn: str | None = Field(default=None)
    requester: Reference | None = Field(default=None)
    performer: Reference | None = Field(default=None)
    performerType: CodeableConcept | None = Field(default=None)
    recorder: Reference | None = Field(default=None)
    reasonCode: list[CodeableConcept] | None = Field(default=None)
    reasonReference: list[Reference] | None = Field(default=None)
    instantiatesCanonical: list[str] | None = Field(default=None)
    instantiatesUri: list[str] | None = Field(default=None)
    basedOn: list[Reference] | None = Field(default=None)
    groupIdentifier: Identifier | None = Field(default=None)
    courseOfTherapyType: CodeableConcept | None = Field(default=None)
    insurance: list[Reference] | None = Field(default=None)
    note: list[Annotation] | None = Field(default=None)
    dosageInstruction: list[Dosage] | None = Field(default=None)
    dispenseRequest: MedicationRequestDispenseRequest | None = Field(default=None)
    substitution: MedicationRequestSubstitution | None = Field(default=None)
    priorPrescription: Reference | None = Field(default=None)
    detectedIssue: list[Reference] | None = Field(default=None)
    eventHistory: list[Reference] | None = Field(default=None)


class DiagnosticReport(FHIRBase):
    resourceType: Literal["DiagnosticReport"] = "DiagnosticReport"
    id: str | None = Field(default=None)
    meta: Meta | None = Field(default=None)
    implicitRules: str | None = Field(default=None)
    language: str | None = Field(default=None)
    text: Narrative | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    identifier: list[Identifier] | None = Field(default=None)
    basedOn: list[Reference] | None = Field(default=None)
    status: str = Field()
    category: list[CodeableConcept] | None = Field(default=None)
    code: CodeableConcept = Field()
    subject: Reference | None = Field(default=None)
    encounter: Reference | None = Field(default=None)
    effectiveDateTime: str | None = Field(default=None)
    effectivePeriod: Period | None = Field(default=None)
    issued: str | None = Field(default=None)
    performer: list[Reference] | None = Field(default=None)
    resultsInterpreter: list[Reference] | None = Field(default=None)
    specimen: list[Reference] | None = Field(default=None)
    result: list[Reference] | None = Field(default=None)
    imagingStudy: list[Reference] | None = Field(default=None)
    media: list[DiagnosticReportMedia] | None = Field(default=None)
    conclusion: str | None = Field(default=None)
    conclusionCode: list[CodeableConcept] | None = Field(default=None)
    presentedForm: list[Attachment] | None = Field(default=None)


class AllergyIntolerance(FHIRBase):
    resourceType: Literal["AllergyIntolerance"] = "AllergyIntolerance"
    id: str | None = Field(default=None)
    meta: Meta | None = Field(default=None)
    implicitRules: str | None = Field(default=None)
    language: str | None = Field(default=None)
    text: Narrative | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    identifier: list[Identifier] | None = Field(default=None)
    clinicalStatus: CodeableConcept | None = Field(default=None)
    verificationStatus: CodeableConcept | None = Field(default=None)
    type: str | None = Field(default=None)
    category: list[str] | None = Field(default=None)
    criticality: str | None = Field(default=None)
    code: CodeableConcept | None = Field(default=None)
    patient: Reference = Field()
    encounter: Reference | None = Field(default=None)
    onsetDateTime: str | None = Field(default=None)
    onsetAge: Age | None = Field(default=None)
    onsetPeriod: Period | None = Field(default=None)
    onsetRange: Range | None = Field(default=None)
    onsetString: str | None = Field(default=None)
    recordedDate: str | None = Field(default=None)
    recorder: Reference | None = Field(default=None)
    asserter: Reference | None = Field(default=None)
    lastOccurrence: str | None = Field(default=None)
    note: list[Annotation] | None = Field(default=None)
    reaction: list[AllergyIntoleranceReaction] | None = Field(default=None)


class Bundle(FHIRBase):
    resourceType: Literal["Bundle"] = "Bundle"
    id: str | None = Field(default=None)
    meta: Meta | None = Field(default=None)
    implicitRules: str | None = Field(default=None)
    language: str | None = Field(default=None)
    identifier: Identifier | None = Field(default=None)
    type: str = Field()
    timestamp: str | None = Field(default=None)
    total: int | None = Field(default=None)
    link: list[BundleLink] | None = Field(default=None)
    entry: list[BundleEntry] | None = Field(default=None)
    signature: Signature | None = Field(default=None)


class Practitioner(FHIRBase):
    resourceType: Literal["Practitioner"] = "Practitioner"
    id: str | None = Field(default=None)
    meta: Meta | None = Field(default=None)
    implicitRules: str | None = Field(default=None)
    language: str | None = Field(default=None)
    text: Narrative | None = Field(default=None)
    extension: list[Extension] | None = Field(default=None)
    identifier: list[Identifier] | None = Field(default=None)
    active: bool | None = Field(default=None)
    name: list[HumanName] | None = Field(default=None)
    telecom: list[ContactPoint] | None = Field(default=None)
    address: list[Address] | None = Field(default=None)
    gender: str | None = Field(default=None)
    birthDate: str | None = Field(default=None)
    photo: list[Attachment] | None = Field(default=None)
    qualification: list[PractitionerQualification] | None = Field(default=None)
    communication: list[CodeableConcept] | None = Field(default=None)


PatientContact.model_rebuild()
PatientCommunication.model_rebuild()
PatientLink.model_rebuild()
EncounterStatusHistory.model_rebuild()
EncounterClassHistory.model_rebuild()
EncounterParticipant.model_rebuild()
EncounterDiagnosis.model_rebuild()
EncounterHospitalization.model_rebuild()
EncounterLocation.model_rebuild()
ConditionStage.model_rebuild()
ConditionEvidence.model_rebuild()
ObservationReferenceRange.model_rebuild()
ObservationComponent.model_rebuild()
MedicationRequestDispenseRequest.model_rebuild()
MedicationRequestDispenseRequestInitialFill.model_rebuild()
MedicationRequestSubstitution.model_rebuild()
DiagnosticReportMedia.model_rebuild()
AllergyIntoleranceReaction.model_rebuild()
BundleLink.model_rebuild()
BundleEntry.model_rebuild()
BundleEntrySearch.model_rebuild()
BundleEntryRequest.model_rebuild()
BundleEntryResponse.model_rebuild()
PractitionerQualification.model_rebuild()
Address.model_rebuild()
Age.model_rebuild()
Annotation.model_rebuild()
Attachment.model_rebuild()
CodeableConcept.model_rebuild()
Coding.model_rebuild()
ContactPoint.model_rebuild()
Dosage.model_rebuild()
DosageDoseAndRate.model_rebuild()
Duration.model_rebuild()
Extension.model_rebuild()
HumanName.model_rebuild()
Identifier.model_rebuild()
Meta.model_rebuild()
Narrative.model_rebuild()
Period.model_rebuild()
Quantity.model_rebuild()
Range.model_rebuild()
Ratio.model_rebuild()
Reference.model_rebuild()
SampledData.model_rebuild()
Signature.model_rebuild()
Timing.model_rebuild()
TimingRepeat.model_rebuild()
ContactDetail.model_rebuild()
Contributor.model_rebuild()
Count.model_rebuild()
DataRequirement.model_rebuild()
DataRequirementCodeFilter.model_rebuild()
DataRequirementDateFilter.model_rebuild()
DataRequirementSort.model_rebuild()
Distance.model_rebuild()
Expression.model_rebuild()
Money.model_rebuild()
ParameterDefinition.model_rebuild()
RelatedArtifact.model_rebuild()
TriggerDefinition.model_rebuild()
UsageContext.model_rebuild()
Patient.model_rebuild()
Encounter.model_rebuild()
Condition.model_rebuild()
Observation.model_rebuild()
MedicationRequest.model_rebuild()
DiagnosticReport.model_rebuild()
AllergyIntolerance.model_rebuild()
Bundle.model_rebuild()
Practitioner.model_rebuild()
