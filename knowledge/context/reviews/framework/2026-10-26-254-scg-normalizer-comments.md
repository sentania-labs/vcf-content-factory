# Framework review: SCG normalizer drops PowerShell comments before the join (#254)

- Branch: `fix/254-scg-normalizer-comment-lines` @ 656bbc5, diffed against `main`
- Files: `scripts/_compliance_normalize.py` (`_strip_ps_comment`, `collapse_remediation`), `tests/test_scg_remediation_comments.py` (new)
- Reviewer: framework-reviewer, 2026-10-26
- Verdict: **APPROVE** (0 BLOCKING / 4 WARNING / 3 NIT). Per delegation rule 9, every finding below still gets fixed or ticketed before the PR opens.

## What I re-ran

| Check | Result |
|---|---|
| Regen of all 5 SCG canonicals (6.7, 7.0, 8.0, 9.0, 9.1) with `main`'s `scripts/` and with the branch's `scripts/`, through the compliance-repo drivers (`run_regen.py`), to scratch only | `main` output is byte-identical to the committed canonicals in `content/sdk-adapters/compliance/profiles/canonical/`, so the baseline is sound |
| Field diff, old vs new | **Exactly 38 rows change, all in `remediation_text`.** No other column changes, row count and order are the same, and no text without a cut changes. Per version: 6.7 25, 7.0 2, 8.0 2, 9.0 3, 9.1 6. The control list matches tooling's |
| `vm.virtual-hardware` (8.0/9.0/9.1) | Unchanged in the canonicals, because the factory output now equals what the compliance repo's W3 workaround (`_adapter_deltas.py`) already writes |
| Rendered alert recommendations (`generate_compliance_alerts.collect()` + `recommendation_text()`, old vs new canonicals) | 3 of 136 shipped recommendations change: `esx.time`, `vc.time`, `vm.minimize-console-vnc-use` |
| New test against `main`'s normalizer | 5 of 10 fail, including the end-to-end row test. On the branch, 10 of 10 pass |
| Fixture vs real CSV | All 10 fixture cells match `vmware_scg_9.0.csv` row `vm-9.virtual-hardware` verbatim. The fixture is a column subset, which is fine because the source CSV lives in a gitignored adapter repo and embedding it keeps the test portable |
| Full test suite | 2632 passed, 6 failed, 9 skipped. The 6 failures are the known `main` ones (`test_release_naming_phase_v2_item1.py` x5, `test_validator_phase2.py` x1) |
| Validate chain (7 packages) | All exit 0. The chain does not cover `scripts/`, so it proves nothing about this change |
| pak-compare / render regression | n/a. No template, builder or renderer is touched. The compliance pak is built by its own repo's CI |

## Tokenizer audit

**Current corpus.** I scanned every remediation cell with a `#` in all 5 vendor CSVs. None contains a here-string (`@"`, `@'`), a block comment (`<#`), `#requires`, a backtick line continuation, smart quotes, or a `#` directly after `;`, `{` or `(`. The only `#>` hits are inside the string `"<New VLAN#>"`, which is correctly kept. The cells that still hold a `#` after the change are:

- the comment-only cells kept on purpose: 6.7 `ESXi.disable-cim` and `ESXi.disable-slp`, 7.0 `iscsi-mutual-chap`;
- the in-string `#` in 7.0 `network-vgt`;
- the ESXi Shell and vCLI columns, which the drivers do not read.

On today's data the tokenizer is correct.

**Synthetic probes** (scratch `probe.py`). Correct: single and double quotes, backtick-escaped `"`, doubled `''` and `""`, a quote carried across lines, tab and NBSP before `#`, CRLF, `-match '#x'`, a `#` inside a hashtable string, `--value=#abc`. Wrong, but nothing in the corpus triggers it today (see W2):

| Input | Output | Problem |
|---|---|---|
| `<# inline #> Set-A` | `<# inline` | **Cuts real code**, because the `#>` after a space is read as a line comment |
| `<#` / text / `#>` / `Set-A` | `<# ; text ; Set-A` | Leaves an unclosed block comment that swallows everything |
| `Set-A;# c` + `Set-B` | `Set-A;# c ; Set-B` | `#` after `;`, `{` or `(` starts a PowerShell comment but is not recognized, so the swallow stays |
| `$x = @"` + `He said "hi` + `# x` + `"@` | quote state flips inside the here-string, so later comments are not cut | Here-strings cannot be single-lined in any case |
| `Use the host's UI` + `# c` | apostrophe in prose opens a fake `'` string, so nothing after it is cut | Safe direction, but the bug remains |
| `Configure item #3 in the UI` | `Configure item` | **Cuts prose** |
| `Write-Host “a # b”` | `Write-Host “a` | PowerShell accepts smart quotes as string delimiters; the tokenizer does not |

## Before and after review of the 38 rows

I read each one by eye. In all 38, everything removed is either a `#` comment or the empty `;` segments that comments or blank lines left behind. No code token was cut. The cases that matter:

- **`esx.ssh-configuration` (9.0), `esx.vib-acceptance-level-supported` (7.0 to 9.1), `esx.firewall-restrict-access` (7.0 to 9.1), `esx.enable-strict-lockdown-mode`, `vds.network-restrict-netflow-usage`, `esx.iscsi-mutual-chap` (6.7), `esx.tpm-recovery-key-backup`, `cluster.encryption-rest` (9.1).** Each had a comment in the middle or at the end that silently swallowed the statements after it. These are now real fixes, beyond the one control the issue names. `esx.ssh-configuration` went from 1 executed statement to all 25 settings.
- **Rows whose text was inert and is now executable**, and broken by vendor defects or by the existing ` ; ` join (N2). All are 6.7, and none reaches a rendered recommendation:
  - `esx.timekeeping-sources`: `"pool2.ntp.org"Get-VMHost`, a newline missing in the vendor text.
  - `vm.transparentpagesharing-inter-vm-enabled`: `$ vmsaltvalue`.
  - `vds.network-restrict-netflow-usage`: unquoted `<name of portgroup>`; the function is called before it is defined; `[CmdletBinding()] ; Param ( ; ... ; )` does not parse.
  - `esx.enable-strict-lockdown-mode`: `foreach (...) ; {`, a missing statement body.
- **`esx.updates` (6.7)** is now a bare URL. The only meaningful content was the prose comment (W1). Not scored.

## Findings

### WARNING

**W1. Operator guidance is dropped silently, including caveats in shipped recommendations.**
- Location: `scripts/_compliance_normalize.py:1658-1686`.
- Authorities: `CANONICAL_SCHEMA.md` §`remediation_text` format (single-line, "suitable for embedding in symptom messages"), and the doctrine's "unreadable is not compliant" analog (dimension 8).
- Lost text:
  - In 2 rendered recommendations, `esx.time` and `vc.time` (SCG 9.1, scored, newest guide): *"Replace the example servers with your organization's authoritative NTP sources"*. Before, the command was inert. Now it is a runnable paste that sets `ntp1..4.example.com` on every host or vCenter, and the one sentence telling the operator to change that is gone.
  - In the canonicals (not scored today, but the canonicals are data and get scored as read recipes land):
    - `esx.firewall-restrict-access`: "This is an example which you will want to customize!" and "Deactivate firewall temporarily...". The script now really disables the ESXi firewall and pins SSH to `192.168.0.0/16`.
    - `esx.tpm-recovery-key-backup`: "Do NOT write the key to a plaintext file the host can reach". The script prints recovery keys.
    - `esx.updates`: reduced to a bare URL.
    - `vib-acceptance`: the list of valid levels.
    - `vds.network-restrict-netflow-usage`: the virtu-al.net attribution URL.
- Judgement: removing the comments is right, because a comment that swallows the command is worse. Deleting the prose is not.
- Recommended fix: **turn each dropped line or trailing comment into an inline block comment `<# ... #>`**, placed where the comment stood or gathered at the front, rather than deleting it. A `<# ... #>` block is valid PowerShell on one line. It keeps the paste runnable, keeps the warning next to the code, and fits the single-line schema. Escape any `#>` inside the comment text. The rendered recommendation already carries `<...>` placeholders, and `xml_attr` escapes `<` and `>`, so the alert path handles it.
- I advise against a plain-prose `Note: ...;` prefix: pasted, it is a parse error, so it breaks the paste-ability the fix exists for.
- If the block-comment form is rejected, at minimum keep the comment-only remediation `esx.updates` as it was, by applying the existing "only comments" rule when the remaining text has no code, not just when nothing remains.

**W2. The tokenizer has no guard for the PowerShell constructs it does not model.**
- Location: `scripts/_compliance_normalize.py:1630-1655`.
- Authority: the doctrine's skeptic default. The table above shows `<# ... #>` cutting live code, `;#`, `{#` and `(#` not recognized, here-strings, prose `#3` cut, and smart quotes. None is in today's corpus, but the shared normalizer will meet the next vendor CSV, and every one of these fails silently.
- Fix:
  - Count `;`, `{`, `(` and `|` as a valid token start alongside whitespace.
  - When the text contains `<#`, `@"`, `@'` or smart quotes, leave it unchanged (the old behaviour) and `log()` a warning that names the control.
  - Add parametrized cases for each, so the bail-out is pinned.
  - If W1 is fixed with `<# #>` emission, the `<#` guard matters doubly.

**W3. Cross-repo: landing this makes the compliance drivers fail on their next regen.**
- Location: compliance repo `scripts/_adapter_deltas.py:213-266` and `normalize_scg_v80/v90/v91.py`.
- Observed: with the branch's normalizer, all three drivers now `SystemExit` with `unexpected build-98 delta counts {... 'comments': 0}`. They write the canonical first, but exit non-zero.
- This is by design, since the workaround says "REMOVE once factory #254 lands". The failure is loud, which is correct. It is still a required companion change outside this branch:
  - drop the W3 delta and its call sites;
  - regenerate the 5 canonicals (38 rows);
  - regenerate the alerts (3 recommendations).
- Fix: open the compliance-repo follow-up issue and name it, with the 38-row list, in the PR body.

**W4. The `normalize_cis_vsphere.py` caller is changed but was not regenerated.**
- Location: `scripts/normalize_cis_vsphere.py:166`.
- `collapse_remediation` is shared with the CIS normalizer. "Exactly 38 across 5 canonicals" covers SCG only. No CIS source CSV is in the tree. The last shipped `cis_vsphere_8.csv` (in a `tmp/cmp52` pak extract) has 0 non-empty remediations out of 106, so the change is inert there today, but that is inference, not a re-run.
- Fix: one sentence in the PR body that the CIS path shares the function and is inert on the current sample.

### NIT

- **N1.** `scripts/_compliance_normalize.py:1630`: annotate the return as `Tuple[str, Optional[str], bool]` rather than a bare `tuple`. `Tuple` is already importable from `typing` beside `Optional`.
- **N2.** The pre-existing ` ; ` join does not preserve meaning for multi-line blocks: `foreach (...) ; {`, and `[CmdletBinding()] ; Param ( ; ... ; )`. This branch makes those rows look runnable (strict-lockdown, netflow). They are not rendered today, since newer guides supersede them. This is a follow-up issue against the join, not this branch. One option: join a line that ends with `)` and is followed by a line starting `{` with a space, and join inside `( ... )` with a space.
- **N3.** `#requires` lines are dropped as comments. That is harmless in a pasted one-liner and absent from the corpus. A one-line note in the docstring would stop a future reader from treating it as a bug.

## Global / standalone path

Not applicable in the dashboard-import sense. The equivalent check is "every consumer of `collapse_remediation`":

- SCG v8, v9 and v67 drivers: covered by the regen.
- CIS: W4.
- The alert generator: covered by the recommendation diff.
- `BenchmarkLoader.java` loads the field but never surfaces it beyond the profile object.

## Stale-zip / version stamp (dimension 9)

Not triggered. No file under `src/vcfcf_packaging/templates/`, the builders, `assembly.py`, or `render.py` is touched.

## If shipped as-is

The factory canonicals stop shipping comment-swallowed scripts, which is a real fix for about 10 controls. The compliance repo's next regen fails until its W3 delta is removed. After that regen, the shipped `esx.time` and `vc.time` recommendations become pasteable commands that point time sync at `example.com`, with the "replace these" warning gone.
