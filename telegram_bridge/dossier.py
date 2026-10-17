"""Format dossier metadata without translating official evidence or certifying completeness."""
from telegram_bridge.contracts import AssistantResponse
from telegram_bridge.ui import TEXT


def render_dossier(result: AssistantResponse, language: str) -> str:
    ui = TEXT[language]
    report = result.report
    assessed = result.recognised is True and report is not None
    fields = report.form_fields if assessed else None
    lines = [ui['dossier_title']]
    for name, key in [('filled', 'dossier_filled'), ('missing', 'dossier_missing'),
                      ('unreadable', 'dossier_unreadable'), ('cannot_verify', 'dossier_unverifiable')]:
        values = getattr(fields, name) if fields else None
        count = str(len(values)) if values is not None else ui['dossier_unknown']
        lines.append(f'{ui[key]}: {count}')
    evidence = report.dossier if assessed else None
    requirements = evidence.official_requirements if evidence else None
    supported = ([q for q in requirements if q.status == 'supported_by_official_source']
                 if requirements is not None else None)
    lines.append(f"{ui['dossier_supported']}: " + (str(len(supported)) if supported is not None else ui['dossier_unknown']))
    lines.append(ui['dossier_unverified'] + ':')
    if evidence and evidence.requirements_not_verified is not None and requirements is not None:
        notes = [q.note or q.id for q in requirements if q.status != 'supported_by_official_source']
        notes += evidence.requirements_not_verified
        lines.extend('• ' + note for note in dict.fromkeys(notes))
        if not notes:
            lines.append(ui['dossier_none'])
    else:
        lines.append(ui['dossier_unknown'])
    # Preserve the agent's evidence, field labels and official quotations exactly.
    text = '\n'.join(lines) + '\n\n' + result.text
    if result.error:
        text += '\n\n' + ui['unreadable']
    elif result.recognised is False:
        text += '\n\n' + ui['unsupported_form']
    if report:
        for note in [report.readiness_summary, *report.limitations]:
            if note and note not in text:
                text += '\n\n' + note
    if result.form_url and result.form_url.startswith('https://') and result.form_url not in text:
        text += '\n' + result.form_url
    return text + '\n\n' + ui['dossier_disclaimer']
