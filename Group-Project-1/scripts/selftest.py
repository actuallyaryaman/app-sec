"""Synthetic parser tests only; never exported as scan evidence."""
from analyze import counts, safe_secrets, trivy_summary
r = {'Target': '/usr/bin/example', 'Class': 'lang-pkgs', 'Type': 'gobinary'}
v = {'VulnerabilityID': 'CVE-TEST', 'PkgName': 'module', 'InstalledVersion': '1', 'Severity': 'HIGH'}
w = dict(v, PkgName='other')
s = counts([(r, v), (r, v), (r, w)])
assert s['raw_rows'] == 3 and s['deduplicated_occurrences'] == 2
assert s['unique_CVE_ids'] == 1 and s['occurrences_by_severity']['HIGH'] == 2
summary = trivy_summary({'Results': [dict(r, Vulnerabilities=[v, w]),
    {'Target': 'os', 'Class': 'os-pkgs', 'Type': 'alpine', 'Vulnerabilities': [v]}]})
assert summary['categories']['OS']['deduplicated_occurrences'] == 1
assert summary['categories']['application']['deduplicated_occurrences'] == 2
assert len(summary['binary_targets']) == 1
assert isinstance(summary['CVE-2018-18557'], str)
raw = {'RuleID': 'generic-api-key', 'File': 'config.php', 'StartLine': 3,
       'Secret': 'DO_NOT_EXPORT', 'Match': 'DO_NOT_EXPORT', 'Description': 'DO_NOT_EXPORT',
       'Message': 'DO_NOT_EXPORT'}
assert 'DO_NOT_EXPORT' not in str(safe_secrets([raw]))
print('Synthetic parser tests passed; these are not scan findings.')
