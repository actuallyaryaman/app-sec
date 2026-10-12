"""Offline evidence analysis; only explicit allowlisted fields leave the volume."""
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path('/lab/runs')
SEVERITIES = ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN')
BINARY_TYPES = {'gobinary', 'rustbinary'}


def counts(rows):
    # Result target + package identity/location + advisory: repeated rows deduplicated.
    seen = {}
    for result, vuln in rows:
        key = (result.get('Target'), result.get('Class'), result.get('Type'),
               vuln.get('PkgID') or vuln.get('PkgName'), vuln.get('InstalledVersion'),
               vuln.get('PkgPath'), vuln.get('VulnerabilityID'))
        seen[key] = vuln
    occurrences = collections.Counter()
    unique = collections.defaultdict(set)
    for v in seen.values():
        severity = v.get('Severity', 'UNKNOWN').upper()
        if severity not in SEVERITIES:
            severity = 'UNKNOWN'
        occurrences[severity] += 1
        unique[severity].add(v.get('VulnerabilityID'))
    ids = {v.get('VulnerabilityID') for v in seen.values()}
    return {'raw_rows': len(rows), 'deduplicated_occurrences': len(seen),
            'occurrences_by_severity': {s: occurrences[s] for s in SEVERITIES},
            'unique_advisory_ids': len(ids),
            'unique_CVE_ids': len({i for i in ids if i and i.startswith('CVE-')}),
            'unique_advisory_ids_by_severity': {s: len(unique[s]) for s in SEVERITIES}}


def trivy_summary(data):
    results = data.get('Results') or []
    groups = collections.defaultdict(list)
    binaries, categories, cve = [], [], []
    for r in results:
        cls = r.get('Class', 'unknown')
        category = {'os-pkgs': 'OS', 'lang-pkgs': 'application'}.get(cls, 'unclassified')
        rows = [(r, v) for v in (r.get('Vulnerabilities') or [])]
        groups[category].extend(rows)
        record = {'target': r.get('Target'), 'class': cls, 'type': r.get('Type'),
                  'package_inventory_count': len(r.get('Packages') or []), **counts(rows)}
        categories.append(record)
        if cls == 'lang-pkgs' and r.get('Type') in BINARY_TYPES:
            binaries.append(record)
        for _, v in rows:
            if v.get('VulnerabilityID') == 'CVE-2018-18557':
                cve.append({'target': r.get('Target'), **{k: v.get(k) for k in (
                    'VulnerabilityID', 'PkgName', 'PkgID', 'PkgPath', 'InstalledVersion',
                    'FixedVersion', 'Severity', 'Status', 'Title', 'Description',
                    'PrimaryURL', 'References', 'DataSource', 'CVSS')}})
    allrows = [row for rows in groups.values() for row in rows]
    return {'artifact': data.get('ArtifactName'), 'schema_version': data.get('SchemaVersion'),
            'all': counts(allrows),
            'categories': {k: counts(groups[k]) for k in ('OS', 'application', 'unclassified')},
            'coverage': {k: {'result_count': sum(
                {'os-pkgs': 'OS', 'lang-pkgs': 'application'}.get(r.get('Class'),
                    'unclassified') == k for r in results),
                'note': 'Zero findings may reflect missing detector coverage; inspect result inventory.'}
                for k in ('OS', 'application', 'unclassified')},
            'result_targets': categories, 'binary_targets': binaries,
            'CVE-2018-18557': cve or 'Not detected in this scan; not evidence of absence.',
            'limitations': 'Binary classification uses lang-pkgs with Type gobinary/rustbinary only. '
            'Other targets are not inferred to be binaries. No binary targets means no supported '
            'binary metadata observed. Unique severity buckets can overlap if sources disagree. '
            'Unique advisory IDs include non-CVE advisories. Inventory counts are per result, '
            'not distinct global packages. Finding counts describe scanner records, not exploitability.'}


SAFE_SECRET_FIELDS = ('RuleID', 'File', 'StartLine', 'EndLine', 'StartColumn', 'EndColumn',
                      'Commit', 'Fingerprint', 'Tags')


def safe_secrets(findings):
    return [{**{k: f[k] for k in SAFE_SECRET_FIELDS if k in f},
             'category': f.get('RuleID', 'unknown'),
             'review': 'Unclassified; manual investigation required'} for f in findings]


def latest(kind):
    runs = sorted(ROOT.glob('*-' + kind + '-*'), key=lambda r: r.stat().st_mtime_ns)
    if not runs:
        raise RuntimeError(f'No successful {kind} scan. Inspect /lab/runs error logs.')
    run = runs[-1]
    status = run / 'exit-code.txt'
    accepted = ('0', '10') if kind.startswith('gitleaks-') else ('0',)
    if not status.exists() or status.read_text().strip() not in accepted:
        raise RuntimeError(f'Latest {kind} run {run.name} failed or is incomplete; '
                           'older evidence is not silently substituted. Inspect its error.log.')
    return run


def build():
    summary = {'counting': 'Deduplicate by target/class/type/package identity/version/path/advisory. '
               'Same CVE in different packages or binaries is multiple occurrences, one unique CVE.'}
    for target in ('dvwa', 'grafana'):
        run = latest('trivy-' + target)
        summary[target] = {'evidence_run': run.name,
                           **trivy_summary(json.loads((run / 'trivy.json').read_text()))}
    for mode in ('git', 'dir'):
        run = latest('gitleaks-' + mode)
        findings = json.loads((run / 'gitleaks.json').read_text()) or []
        safe = safe_secrets(findings)
        summary['gitleaks-' + mode] = {'evidence_run': run.name,
            'commit': (run / 'commit.txt').read_text().strip(),
            'finding_occurrences': len(safe),
            'by_rule': dict(collections.Counter(f.get('RuleID', 'unknown') for f in safe)),
            'findings': safe}
    return summary


def export():
    summary = build()
    destination = pathlib.Path('/export')
    # Flat filenames avoid creating root-owned directories on the host.
    (destination / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    # Complete Trivy JSON/table and provenance are not secret-scanner data.
    for kind in ('trivy-dvwa', 'trivy-grafana', 'gitleaks-git', 'gitleaks-dir'):
        run = latest(kind)
        names = ['version.txt', 'started.txt', 'finished.txt', 'exit-code.txt', 'command.txt',
                 'commit.txt', 'config.toml']
        if kind.startswith('trivy-'):
            names += ['trivy.json', 'table.txt', 'db-metadata.json', 'java-db-metadata.json',
                      'target-inspect.json', 'archive.sha256', 'database.sha256',
                      'dvwa.digest.txt', 'grafana.digest.txt', 'dvwa.reference.txt',
                      'grafana.reference.txt', 'dvwa.resolved-reference.txt',
                      'grafana.resolved-reference.txt', 'dvwa.architecture.txt',
                      'grafana.architecture.txt']
        for name in names:
            source = run / name
            if source.exists():
                (destination / f'{run.name}-{name}').write_bytes(source.read_bytes())
        if kind.startswith('gitleaks-'):
            safe = safe_secrets(json.loads((run / 'gitleaks.json').read_text()) or [])
            (destination / f'{run.name}-sanitized.json').write_text(json.dumps(safe, indent=2) + '\n')
    print('Exported allowlisted evidence; Gitleaks raw JSON, source, and logs remain in volumes.')


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else 'summary'
    if command == 'export':
        export()
    elif command == 'table':
        target = sys.argv[2]
        if target not in ('dvwa', 'grafana'):
            raise ValueError('Use dvwa or grafana')
        print((latest('trivy-' + target) / 'table.txt').read_text())
    elif command in ('summary', 'cve', 'binaries', 'secrets'):
        if command == 'cve':
            r = latest('trivy-dvwa')
            value = trivy_summary(json.loads((r / 'trivy.json').read_text()))['CVE-2018-18557']
        elif command == 'binaries':
            r = latest('trivy-grafana')
            s = trivy_summary(json.loads((r / 'trivy.json').read_text()))
            value = {'binary_targets': s['binary_targets'], 'result_targets': s['result_targets'],
                     'limitations': s['limitations']}
        elif command == 'secrets':
            value = {}
            for mode in ('git', 'dir'):
                r = latest('gitleaks-' + mode)
                value[mode] = safe_secrets(json.loads((r / 'gitleaks.json').read_text()) or [])
        else:
            value = build()
        print(json.dumps(value, indent=2))
    else:
        raise ValueError('Use summary, table dvwa|grafana, cve, binaries, secrets, or export')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError) as error:
        print(f'Analysis failed: {error}', file=sys.stderr)
        sys.exit(1)
