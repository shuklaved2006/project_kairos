import json
from copy import deepcopy
from .contracts import Interpretation, Tradeoff
from ..schemas import Entry
from ..capacity import calculate

class OutputRejected(ValueError):
    pass

def validate_output(raw, source):
    if not isinstance(raw,str) or len(raw.encode('utf-8')) > 48000:
        raise OutputRejected('output_size')
    try:
        value = Interpretation.model_validate_json(raw)
    except ValueError:
        raise OutputRejected('invalid_schema') from None
    identifiers = [item.temp_id for item in value.items]
    if len(set(identifiers)) != len(identifiers):
        raise OutputRejected('duplicate_item_id')
    for item_index, item in enumerate(value.items):
        if item.source_quote not in source:
            raise OutputRejected('unsupported_source_quote')
        evidence = {e.field:e for e in item.evidence}
        if len(evidence) != len(item.evidence):
            raise OutputRejected('duplicate_evidence')
        for field in ('title','kind','deadline','start','end','estimated_minutes','priority','recurrence','category','anchor_date'):
            field_value = getattr(item,field)
            proof = evidence.get(field)
            if field_value is not None and (proof is None or proof.origin == 'unknown'):
                raise OutputRejected(f'missing_evidence:items[{item_index}].{field}')
            if field_value is None and proof and proof.origin != 'unknown':
                raise OutputRejected(f'contradictory_evidence:items[{item_index}].{field}')
            if proof and proof.quote and proof.quote not in source:
                raise OutputRejected('invented_evidence_quote')
            if proof and proof.origin in ('explicit','derived') and not proof.quote:
                raise OutputRejected(f'missing_evidence_quote:items[{item_index}].{field}')
        for field, default in (('quantity',1),('estimate_qualifier','unspecified'),('estimate_basis','total')):
            if getattr(item,field) != default:
                proof=evidence.get(field)
                if proof is None or proof.origin == 'unknown' or not proof.quote or proof.quote not in source:
                    raise OutputRejected(f'missing_quantity_or_estimate_evidence:items[{item_index}].{field}')
        if item.estimated_minutes is None and item.estimate_qualifier != 'unspecified':
            raise OutputRejected('qualifier_without_estimate')
        if any(getattr(item,field) is not None for field in item.missing_fields):
            raise OutputRejected('contradictory_missing_field')
    amendment_ids = [a.amendment_id for a in value.amendments]
    if len(set(amendment_ids)) != len(amendment_ids) or set(amendment_ids) & set(identifiers):
        raise OutputRejected('duplicate_amendment_id')
    for amendment in value.amendments:
        if amendment.source_quote not in source:
            raise OutputRejected('unsupported_amendment_quote')
    for question in value.questions:
        if question.item_id is not None and question.item_id not in identifiers:
            raise OutputRejected('unknown_question_target')
    if any(part.source_quote not in source for part in value.unfiled):
        raise OutputRejected('unsupported_unfiled_quote')
    return value

def needs_review(value):
    return any(e.origin in ('derived','suggested') for item in value.items for e in item.evidence)

def review_requirements(value):
    reasons = []
    for item in value.items:
        missing = set(item.missing_fields)
        if item.kind == 'TASK' and item.estimated_minutes is None:
            missing.add('estimated_minutes')
        if item.kind == 'CALENDAR_EVENT':
            if item.start is None: missing.add('start')
            if item.end is None: missing.add('end')
        if item.kind == 'RECURRING_HABIT' and item.recurrence is None:
            missing.add('recurrence')
        reasons.append({'item_id':item.temp_id,'missing_fields':sorted(missing),
                        'confirm_fields':[e.field for e in item.evidence if e.origin in ('derived','suggested')]})
    return reasons

def preview_tradeoff(raw, current_records, capacity):
    proposal = Tradeoff.model_validate(raw)
    snapshots = {r['id']:deepcopy(r) for r in current_records}
    touched = set()
    for change in proposal.changes:
        if change.entry_id in touched or change.entry_id not in snapshots:
            raise OutputRejected('unknown_or_duplicate_reference')
        touched.add(change.entry_id)
        record = snapshots[change.entry_id]
        entry = Entry.model_validate(record['data'])
        if record['version'] != change.version:
            raise OutputRejected('stale_version')
        if entry.status != 'accepted' or entry.kind != 'TASK':
            raise OutputRejected('fixed_or_inactive_commitment')
        if change.operation == 'defer':
            if any(v is not None for v in (change.start,change.end,change.estimated_minutes,change.scope_description)):
                raise OutputRejected('unexpected_change_fields')
            record['data']['status'] = 'deferred'
        elif change.operation == 'move':
            if not change.start or not change.end or change.estimated_minutes is not None or change.scope_description is not None:
                raise OutputRejected('invalid_move')
            if not capacity.start <= change.start < change.end <= capacity.end:
                raise OutputRejected('move_outside_horizon')
            if entry.estimated_minutes is None or (change.end-change.start).total_seconds()/60 < entry.estimated_minutes:
                raise OutputRejected('insufficient_or_unknown_block_duration')
            record['data'].update(start=change.start.isoformat(),end=change.end.isoformat())
        else:
            if not change.scope_description or not change.scope_description.strip() or change.estimated_minutes is None or change.start or change.end:
                raise OutputRejected('scope_change_required')
            if entry.estimated_minutes is None or change.estimated_minutes >= entry.estimated_minutes:
                raise OutputRejected('not_a_scope_reduction')
            record['data']['estimated_minutes'] = change.estimated_minutes
        Entry.model_validate(record['data'])
    assessment = calculate(list(snapshots.values()),capacity)
    return {'assessment':assessment,'resolves':assessment['state']=='fits_estimates',
            'requires_user_approval':True,'applied':False}
