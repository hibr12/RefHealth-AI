"""Deterministic execution of hospital-supplied, clinically approved protocols.

No built-in medical thresholds, LLM, operational predictions, patient identifiers,
or automatic LOW fallback. Approval is an operator attestation, not validation by
this software. Free text is retained by the platform for human review, not parsed
as clinical evidence (negation and context require clinical judgment).
"""
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import Field, AwareDatetime, model_validator
from corecare.schemas import StrictModel
from corecare.integration import authenticated_bridge

Priority = Literal['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
RANK = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
FIELD = r'^(urgency|requiredService|requiredSpecialty|symptoms|riskIndicators|vitals\.[a-zA-Z][a-zA-Z0-9_]{0,39})$'


class Vital(StrictModel):
    value: float
    unit: str = Field(min_length=1, max_length=40)


class Observations(StrictModel):
    symptoms: list[str] = Field(default_factory=list, max_length=50)
    riskIndicators: list[str] = Field(default_factory=list, max_length=50)
    vitals: dict[str, Vital] = Field(default_factory=dict, max_length=30)


class Condition(StrictModel):
    field: str = Field(pattern=FIELD)
    operator: Literal['equals', 'contains', 'gte', 'lte']
    value: str | float
    unit: str | None = Field(default=None, max_length=40)

    @model_validator(mode='after')
    def safe_types(self):
        if self.field.startswith('vitals.'):
            if not self.unit or not isinstance(self.value, (int, float)) or self.operator == 'contains':
                raise ValueError('Vital conditions require a numeric value and exact unit.')
        elif not isinstance(self.value, str) or self.operator not in ('equals', 'contains'):
            raise ValueError('Categorical conditions require string comparisons.')
        if (self.field in ('symptoms', 'riskIndicators')) != (self.operator == 'contains'):
            raise ValueError('contains is reserved for structured symptom/risk lists.')
        return self


class Rule(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    priority: Priority
    explanation: str = Field(min_length=5, max_length=1000)
    conditions: list[Condition] = Field(min_length=1, max_length=20)


class Protocol(StrictModel):
    name: str = Field(min_length=3, max_length=200)
    version: str = Field(min_length=1, max_length=100)
    reference: str = Field(min_length=5, max_length=1000)
    clinicalValidationReference: str = Field(min_length=5, max_length=1000)
    approvedBy: str = Field(min_length=3, max_length=200)
    approvedAt: AwareDatetime
    approvalAttested: Literal[True]
    requiredFields: list[str] = Field(min_length=1, max_length=40)
    rules: list[Rule] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def approval(self):
        import re
        if self.approvedAt > datetime.now(timezone.utc):
            raise ValueError('Clinical approval cannot be in the future.')
        if any(not re.fullmatch(FIELD, field) for field in self.requiredFields):
            raise ValueError('Invalid required field.')
        if len({rule.id for rule in self.rules}) != len(self.rules):
            raise ValueError('Duplicate rule IDs.')
        return self


class ClinicalRequest(StrictModel):
    urgency: Literal['Routine', 'Urgent', 'Emergency']
    requiredService: str = Field(min_length=1, max_length=200)
    requiredSpecialty: str | None = Field(default=None, max_length=200)
    observations: Observations = Field(default_factory=Observations)
    protocol: Protocol | None = None


def recommend_priority(request: ClinicalRequest):
    protocol = request.protocol
    result = {'priority': None, 'requires_review': True, 'protocol_version': None,
              'matched_rules': [], 'factors': [], 'missing_fields': [],
              'explanation': 'No approved clinical protocol is configured. Clinical review is required.'}
    if not protocol:
        return result
    result['protocol_version'] = protocol.version

    def value(field):
        if field.startswith('vitals.'):
            return request.observations.vitals.get(field.split('.', 1)[1])
        if field in ('symptoms', 'riskIndicators'):
            return getattr(request.observations, field)
        return getattr(request, field, None)

    fields = set(protocol.requiredFields) | {c.field for rule in protocol.rules for c in rule.conditions}
    missing = [field for field in fields if value(field) is None or value(field) == '' or value(field) == []]
    # Unit mismatches must never be interpreted as a low-risk observation.
    for rule in protocol.rules:
        for condition in rule.conditions:
            observed = value(condition.field)
            if isinstance(observed, Vital) and observed.unit != condition.unit:
                missing.append(condition.field + ' (unit mismatch)')
    if missing:
        result.update(missing_fields=sorted(set(missing)), explanation='Insufficient or incompatible structured clinical information. Clinical review is required.')
        return result

    def matches(condition):
        observed = value(condition.field)
        if observed is None:
            return False
        if isinstance(observed, Vital):
            observed = observed.value
        if condition.operator == 'contains':
            return condition.value.casefold() in [item.casefold() for item in observed]
        if condition.operator == 'equals':
            return observed.casefold() == condition.value.casefold() if isinstance(observed, str) else observed == condition.value
        return observed >= condition.value if condition.operator == 'gte' else observed <= condition.value

    matched = [rule for rule in protocol.rules if all(matches(c) for c in rule.conditions)]
    if not matched:
        result['explanation'] = 'No approved rule matched the available information. Clinical review is required; no LOW default was assigned.'
        return result
    selected = min(matched, key=lambda rule: RANK.index(rule.priority))
    result.update(priority=selected.priority, matched_rules=[rule.id for rule in matched],
                  factors=[{'field': c.field, 'operator': c.operator, 'value': c.value, 'unit': c.unit} for c in selected.conditions],
                  explanation=selected.explanation + ' Clinician confirmation is required.')
    return result


router = APIRouter(prefix='/integration', tags=['clinical priority'], dependencies=[Depends(authenticated_bridge)])


@router.post('/clinical-priority')
def clinical_priority(request: ClinicalRequest):
    return {'success': True, 'engine': 'approved-protocol-rules-v1', 'data': recommend_priority(request)}
