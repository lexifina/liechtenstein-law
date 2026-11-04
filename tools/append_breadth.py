"""Append current Lilex texts and retain cumulative repository metadata."""
import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
if (HERE / 'append_current.py').exists():
    sys.path.insert(0, str(HERE))
else:
    sys.path.insert(0, str(HERE.parents[2] / 'liechtenstein-law'))
import append_current as engine

def message(record):
    act = record['act']
    lines = [f"{act['title']} (LR {act['lr']}): oldest version available", '',
             'Current consolidated text; earlier versions are not included.', '',
             'Kind: baseline', 'First-law: none', f"Act-path: {act['slug']}",
             f"In-force: {record['in_force']}",
             'In-force-basis: Lilex current-version start and matching official chronology row',
             f"Text-as-of: {record['as_of']}",
             f"Version-laws: {', '.join(record['source_laws'])}",
             f"Source: {act['source_url']}", f"Text-source: {record['source_url']}",
             f"Current-text: {record['source_url']}"]
    lines.extend(f"Published: {item['published']} ({engine.lgbl_label(item['law'])})"
                 for item in record['source_law_details'])
    return '\n'.join(lines) + '\n'

original_docs = engine.update_docs

def clean_reproduce(text):
    text = re.sub(r'The data was retrieved on 2026-10-28, one request at a time.*?the session\.',
                  'The original selected historical source texts were retrieved on 2026-10-28.', text, flags=re.S)
    text = text.replace('It reads Lilex (or its own cache, `.cache/` next to\nthe script)', 'It uses official Lilex texts')
    text = text.replace("in Lexifina's own repository fetched the data\n   into its cache and wrote this repository.",
                        "read official Lilex texts and wrote the original selected histories.")
    text = text.replace('afresh from the cached HTML', 'afresh from the official source HTML')
    text = text.replace('same cache', 'same recorded source input')
    text = re.sub(r'  a Lilex scraper\. From it we took three facts about the site, checked against it:.*?  was copied\.',
                  '  documents Lilex version URLs and law-title locations. These source facts were checked against Lilex; no code was copied.',
                  text, flags=re.S)
    return text

def update_docs(repo, part, base):
    previous_path = repo / 'data/current-acts.json'
    previous = json.loads(previous_path.read_text(encoding='utf-8')) if previous_path.exists() else {'acts': []}
    old_input = repo / 'data/breadth-input.json'
    prior_input = old_input.read_bytes() if old_input.exists() else None
    original_docs(repo, part, base)
    newest = json.loads(previous_path.read_text(encoding='utf-8'))
    manifests = previous['acts'] + newest['acts']
    if len({a['slug'] for a in manifests}) != len(manifests):
        raise ValueError('Duplicate cumulative act metadata')
    newest['acts'] = manifests
    newest['append_acts'] = len(part['acts'])
    previous_path.write_text(json.dumps(newest, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    if prior_input:
        prior = json.loads(prior_input)
        inputs = repo / 'data/inputs'
        inputs.mkdir(exist_ok=True)
        (inputs / (prior['as_of'] + '-' + prior['sha256'][:12] + '.json')).write_bytes(prior_input)
    descriptor_path = repo / 'corpus.json'
    descriptor = json.loads(descriptor_path.read_text(encoding='utf-8'))
    total = len(manifests) + 3
    earliest = min([descriptor.get('history_from', part['as_of'])] + [a['in_force'] for a in manifests])
    descriptor.update({'path':'liechtenstein/national/acts', 'language':'de', 'history':'in-force',
                       'history_from':earliest,
                       'scope':'all-acts' if total == part['official_listing'] else 'selected-acts', 'acts':total, 'publisher':'Rechtsdienst der Regierung (Lilex)',
                       'future_branch':None,
                       'record_note':f'{len(manifests)} source-dated current texts and three selected dated histories. Earlier versions of breadth acts are not included.'})
    descriptor['breadth_current'].update({'acts':len(manifests), 'append_acts':len(part['acts']),
                                          'official_listing':part['official_listing']})
    descriptor_path.write_text(json.dumps(descriptor, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    jurisdiction = {'name':'Liechtenstein', 'code':'LI', 'level':'national', 'iso_path':'li/national/acts',
                    'path':'liechtenstein/national/acts', 'language':'de',
                    'build':{'status':'partial' if total < part['official_listing'] else 'complete',
                             'acts':total, 'listed_acts':part['official_listing'], 'as_of':part['as_of']}}
    (repo / 'jurisdiction.json').write_text(json.dumps(jurisdiction, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    readme_path = repo / 'README.md'
    readme = readme_path.read_text(encoding='utf-8').split('## Current-text breadth append', 1)[0].rstrip()
    readme = readme.replace('# Liechtenstein law, change by change', '# Liechtenstein law: current texts and selected histories', 1)
    readme = readme.replace('Three acts of the Principality of Liechtenstein as a git repository:', 'Selected full histories of three acts of the Principality of Liechtenstein:', 1)
    readme = readme.replace('- Any act beyond these three. The same build works for any act in Lilex: add it to `ACTS` in `tools/build.py`.\n', '')
    readme += f'\n\n## Current-text breadth append\n\nThe repository records {len(manifests)} further source-dated current texts, alongside three selected full histories. Coverage is {total} of {part["official_listing"]} officially listed current records as at {part["as_of"]}. Every breadth act has one version, labelled “oldest version available”; earlier history is not included. Dates are the official version start and matching gazette chronology dates. Complete single-file texts retain acts whose structure cannot safely be split. Official images remain in place as original SHA-256-named binary assets.\n\n| Record | Acts |\n|---|---:|\n| Selected dated histories | 3 |\n| Current-text breadth acts | {len(manifests)} |\n| Official current listing | {part["official_listing"]} |\n\nAct metadata is in `data/current-acts.json`; the latest append input is in `data/breadth-input.json`, and earlier append inputs are retained under `data/inputs/`.\n'
    readme_path.write_text(readme, encoding='utf-8')
    reproduce = repo / 'REPRODUCE.md'
    text = reproduce.read_text(encoding='utf-8')
    text = text.replace('tools/append_current.py --part data/breadth-input.json', 'tools/append_breadth.py --part data/breadth-input.json')
    text = text.replace('tools/check_current.py --part data/breadth-input.json', 'tools/check_breadth.py --part data/breadth-input.json')
    reproduce.write_text(clean_reproduce(text), encoding='utf-8')
    shutil.copy2(Path(__file__), repo / 'tools/append_breadth.py')
    check_script = HERE / 'check_breadth.py'
    if check_script.exists():
        shutil.copy2(check_script, repo / 'tools/check_breadth.py')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--part', type=Path, required=True)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--expected-base', required=True)
    args = parser.parse_args()
    part = json.loads(args.part.read_text(encoding='utf-8'))
    repo = args.repo.resolve()
    if engine.run(repo, 'rev-parse', 'HEAD') != args.expected_base:
        raise ValueError('Unexpected scratch base')
    if engine.run(repo, 'status', '--porcelain'):
        raise ValueError('Scratch worktree is dirty')
    if part['sha256'] != engine.digest(part['acts']):
        raise ValueError('Input digest mismatch')
    for record in part['acts']:
        engine.validate_record(record)
        if (repo / record['act']['slug']).exists():
            raise ValueError('An appended act already exists')
    engine.message = message
    engine.law_author = lambda record: ('Rechtsdienst der Regierung (Lilex)', 'rdr@gesetze-li.invalid')
    engine.fast_import_records(repo, part['acts'], args.expected_base, args.part)
    update_docs(repo, part, args.expected_base)
    engine.run(repo, 'add', '--', 'README.md', 'REPRODUCE.md', 'corpus.json', 'jurisdiction.json', '.gitattributes', 'data', 'tools')
    env = os.environ.copy()
    env.update(engine.IDENTITY)
    env['GIT_AUTHOR_DATE'] = env['GIT_COMMITTER_DATE'] = part['as_of'] + 'T12:00:00+0100'
    msg = f'Document {len(part["acts"])} additional current-text acts\n\nKind: documentation\n'
    subprocess.run(['git','-c','gc.auto=0','commit','-q','--cleanup=verbatim','-F','-'],
                   cwd=repo, env=env, input=msg, text=True, encoding='utf-8', check=True)
    print(json.dumps({'base':args.expected_base, 'head':engine.run(repo,'rev-parse','HEAD'),
                      'acts':len(part['acts']), 'commits':len(part['acts'])+1}))

if __name__ == '__main__':
    main()
