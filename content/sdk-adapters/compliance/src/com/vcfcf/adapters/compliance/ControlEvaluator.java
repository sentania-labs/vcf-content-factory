package com.vcfcf.adapters.compliance;

import com.vcfcf.adapter.json.SimpleJson;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public final class ControlEvaluator {

	/**
	 * Sentinel value the {@code VSphereClient} recipe reader places in
	 * the property-value map when a control declared a {@code read_recipe}
	 * but the read produced nothing (null / style couldn't extract /
	 * unknown style). Mirrors {@code VSphereClient.UNREADABLE}; compared
	 * by reference. An unreadable control is NEVER compliant and is
	 * excluded from pass / fail / the score denominator — it is surfaced
	 * via {@code unreadableCount} as a profile/coverage signal instead.
	 *
	 * <p>Held as an {@code Object} the caller passes in (so this class
	 * has no compile dependency on VSphereClient) — see
	 * {@link #evaluateVimProperties(java.util.List, java.util.Map,
	 * String, Object)}.
	 */

	public static ComplianceResult evaluate(BenchmarkProfile profile,
			SimpleJson hostDetail, String hostname) {
		if (hostDetail == null || hostDetail.isNull()) {
			return new ComplianceResult(hostname, 0, 0, 0, 0, 100.0,
					new ArrayList<>());
		}
		Map<String, String> settings = new java.util.HashMap<>();
		return evaluateAdvancedSettings(profile, settings, hostname);
	}

	public static ComplianceResult evaluateAdvancedSettings(
			BenchmarkProfile profile,
			Map<String, String> advancedSettings, String hostname) {
		return evaluateControls(profile.hostControls(), advancedSettings,
				hostname);
	}

	/**
	 * Phase 2 entry point — score an arbitrary subset of profile
	 * controls (typically pre-filtered by {@code resource_kind}) against
	 * a key/value map of advanced settings. Used by VirtualMachine
	 * (extraConfig), VCenterAdapterInstance (vCenter setting
	 * OptionManager), and HostSystem (per-host advanced options).
	 *
	 * <p>Same zero-divisor contract as the original — when no profile
	 * controls were evaluable against the resource, score=100.0 rather
	 * than NaN. Operators distinguish "perfect" from "nothing evaluated"
	 * by total_count=0 on the rollup.
	 *
	 * <p>Phase 3 / Batch 3b: this entry point handles
	 * {@code advanced_setting} controls only. Controls with
	 * {@code parameter_kind=vim_property} are skipped here even though
	 * they pass {@link BenchmarkProfile.Control#isEvaluable()} — they
	 * need a typed value map and go through
	 * {@link #evaluateVimProperties(java.util.List, java.util.Map,
	 * String)} instead. Mixing the two against a single
	 * {@code Map<String,String>} would silently mis-score boolean
	 * fields (every "true"/"false" string compare would coerce
	 * through string equality instead of the Accept/Reject -> boolean
	 * mapping).
	 */
	public static ComplianceResult evaluateControls(
			List<BenchmarkProfile.Control> controls,
			Map<String, String> advancedSettings, String resourceName) {
		List<ControlResult> results = new ArrayList<>();
		int pass = 0;
		int fail = 0;

		for (BenchmarkProfile.Control control : controls) {
			// Skip controls whose parameter_kind is not in the
			// advanced_setting evaluable set. vim_property controls
			// also report isEvaluable=true (BenchmarkProfile expanded
			// the evaluable set in batch 3b) but they need a typed
			// value map; this loop only handles string-keyed
			// advanced-setting reads. See evaluateVimProperties for
			// the vim_property dispatcher.
			if (!"advanced_setting".equals(control.parameterKind)) {
				continue;
			}
			String param = control.configParameter;
			if (param == null || param.isEmpty() || "N/A".equals(param)) {
				continue;
			}
			if (param.contains("\n")) continue;

			String actual = advancedSettings.get(param);
			String expected = control.suggestedValue;

			// SCG 'or Undefined' / 'Not Present' semantics. When the
			// VMX/host advanced setting key isn't carried in the
			// extraConfig / OptionManager output for this resource,
			// the SCG expected_value tells us whether absence is the
			// compliant state. ~15 of 16 SCG 9.0 VM advanced_setting
			// controls qualify the expected as 'X or Undefined' /
			// 'Not Present' — i.e. the platform default IS the
			// hardened state. Without this branch every unset key got
			// silently skipped and total_count came out at 1 (only
			// vm.vmrc-lock, which is the one VM control that requires
			// explicit configuration).
			if (actual == null || actual.isEmpty()) {
				if (allowsUndefined(expected)) {
					results.add(new ControlResult(
							control.scgId,
							"(undefined)",
							expected,
							true,
							control.description
					));
					pass++;
				}
				continue;
			}

			// Bare 'Not Present' (without 'X or' prefix) means the key
			// must be absent — its presence at any value is non-compliant.
			boolean compliant;
			if (requiresAbsence(expected)) {
				compliant = false;
			} else {
				compliant = valuesMatch(actual, expected);
			}

			results.add(new ControlResult(
					control.scgId,
					actual,
					expected,
					compliant,
					control.description
			));

			if (compliant) {
				pass++;
			} else {
				fail++;
			}
		}

		int total = pass + fail;
		double score = total > 0 ? ((double) pass / total) * 100.0 : 100.0;

		// advanced_setting controls have no unreadable outcome: an absent
		// key is handled by the allowsUndefined / requiresAbsence
		// semantics above, never an unreadable signal. unreadableCount=0.
		return new ComplianceResult(resourceName, pass, fail, total, 0,
				score, results);
	}

	/**
	 * True when the SCG expected_value qualifies "key is unset/absent"
	 * as a compliant state. Matches two idioms in Bob's SCG CSVs:
	 *
	 * <ul>
	 *   <li>{@code "X or Undefined"} / {@code "X or Not Present"} —
	 *       the key may either be missing or equal to X.</li>
	 *   <li>Bare {@code "Not Present"} — the key MUST be missing
	 *       (presence at any value is non-compliant).</li>
	 * </ul>
	 */
	static boolean allowsUndefined(String expected) {
		if (expected == null) return false;
		String e = expected.trim().toLowerCase();
		if (e.isEmpty()) return false;
		if (e.equals("not present")) return true;
		if (e.endsWith(" or undefined")) return true;
		if (e.endsWith(" or not present")) return true;
		return false;
	}

	/**
	 * True when the SCG expected_value is bare {@code "Not Present"} —
	 * the only compliant state is absence. Presence at any value
	 * (the actual is non-null) is non-compliant.
	 */
	static boolean requiresAbsence(String expected) {
		if (expected == null) return false;
		return "not present".equals(expected.trim().toLowerCase());
	}

	/**
	 * Phase 3 / Batch 3b — score the {@code vim_property} controls in
	 * a profile slice against a typed property-value map.
	 *
	 * <p>The map key is the canonical {@code parameter} dot-path
	 * ({@code securityPolicy.forgedTransmits} etc.) and the value is
	 * the raw Java value read from vim25 (today: {@code Boolean} for
	 * the three security-policy fields; future kinds can extend the
	 * dispatcher). For each evaluable {@code vim_property} control,
	 * the dispatcher:
	 *
	 * <ol>
	 *   <li>Parses the parameter dot-path and looks the canonical key
	 *       up in {@code propertyValues}. Null/missing -> skip.</li>
	 *   <li>Coerces the expected_value string into the value's typed
	 *       form ({@code "Accept"/"true"/"True"} -> Boolean.TRUE,
	 *       {@code "Reject"/"false"/"False"} -> Boolean.FALSE) so a
	 *       row written by Bob's CSV with {@code expected_value=Reject}
	 *       compares correctly against a JVM boolean false.</li>
	 *   <li>Records a {@link ControlResult} with the actual value
	 *       stringified for the per-control raw push.</li>
	 * </ol>
	 *
	 * <p>Zero-divisor contract matches
	 * {@link #evaluateControls(java.util.List, java.util.Map, String)}:
	 * no evaluable vim_property controls -> score=100.0, totalCount=0
	 * so the caller can refuse to fold a sentinel into a fleet average.
	 *
	 * <p><b>Unreadable outcome.</b> A value equal (by reference) to
	 * {@code unreadableSentinel} means the control declared a recipe but
	 * the read produced nothing. Such controls are counted in
	 * {@code unreadableCount}, are NEVER compliant, and are EXCLUDED from
	 * pass, fail, and the score denominator (total). They are recorded as
	 * a {@link ControlResult} with {@code compliant=false} and
	 * {@code actual="(unreadable)"} so the per-control raw push surfaces
	 * them in the metric browser, but they do not move the score.
	 */
	public static ComplianceResult evaluateVimProperties(
			List<BenchmarkProfile.Control> controls,
			Map<String, Object> propertyValues, String resourceName) {
		return evaluateVimProperties(controls, propertyValues, resourceName,
				null);
	}

	/**
	 * Recipe-aware overload — {@code unreadableSentinel} is the object
	 * {@code VSphereClient.UNREADABLE} the reader stored in
	 * {@code propertyValues} for declared-but-unreadable controls.
	 * Passing {@code null} disables the unreadable path (a value of
	 * {@code null} in the map is then treated as "skip", preserving the
	 * legacy two-arg behavior).
	 */
	public static ComplianceResult evaluateVimProperties(
			List<BenchmarkProfile.Control> controls,
			Map<String, Object> propertyValues, String resourceName,
			Object unreadableSentinel) {
		List<ControlResult> results = new ArrayList<>();
		int pass = 0;
		int fail = 0;
		int unreadable = 0;

		for (BenchmarkProfile.Control control : controls) {
			if (!"vim_property".equals(control.parameterKind)) {
				continue;
			}
			// A vim_property control with no read_recipe is
			// non-evaluable / informational — skip it entirely (it is
			// not unreadable; we never declared we could read it).
			if (!control.isEvaluable()) {
				continue;
			}
			String param = control.configParameter;
			if (param == null || param.isEmpty() || "N/A".equals(param)) {
				continue;
			}
			if (param.contains("\n")) continue;

			Object actualObj = propertyValues.get(param);

			// Declared-but-unreadable: recipe present but the read found
			// nothing. Never compliant, excluded from pass/fail/total,
			// surfaced via unreadableCount + a (unreadable) ControlResult.
			if (unreadableSentinel != null && actualObj == unreadableSentinel) {
				unreadable++;
				results.add(new ControlResult(
						control.scgId,
						"(unreadable)",
						control.suggestedValue,
						false,
						control.description
				));
				continue;
			}

			if (actualObj == null) {
				continue;
			}
			String expected = control.suggestedValue;
			boolean compliant = vimPropertyMatches(actualObj, expected);
			String actualStr = String.valueOf(actualObj);

			results.add(new ControlResult(
					control.scgId,
					actualStr,
					expected,
					compliant,
					control.description
			));

			if (compliant) {
				pass++;
			} else {
				fail++;
			}
		}

		int total = pass + fail;
		double score = total > 0 ? ((double) pass / total) * 100.0 : 100.0;

		return new ComplianceResult(resourceName, pass, fail, total,
				unreadable, score, results);
	}

	/**
	 * Compare a vim_property actual value (typed — Boolean for the
	 * security-policy fields today) against the canonical
	 * expected_value string.
	 *
	 * <p>Boolean handling — Bob's SCG CSV expresses the
	 * {@code Baseline Suggested Value} for security-policy controls
	 * in DVS / DVPG vocabulary ({@code Accept} / {@code Reject}),
	 * which we translate:
	 * <ul>
	 *   <li>{@code "Reject"} (security policy denies the action) -> false</li>
	 *   <li>{@code "Accept"} (security policy allows the action) -> true</li>
	 * </ul>
	 * Plus the standard {@code true/false} / {@code TRUE/FALSE} forms
	 * (some SCG rows write {@code expected_value} as a JS boolean
	 * literal rather than the security-policy verb) and the
	 * {@code Enabled/Disabled} pair (defensive — same mapping as
	 * Accept/Reject for "policy permits"). Anything else falls back
	 * to the string-equality path of
	 * {@link #valuesMatch(String, String)} so non-Boolean
	 * vim_property kinds added later don't silently mis-score.
	 */
	static boolean vimPropertyMatches(Object actual, String expected) {
		if (actual == null || expected == null) return false;
		String e = stripQuotes(expected.trim());
		if (actual instanceof Boolean) {
			Boolean a = (Boolean) actual;
			Boolean expectedBool = expectedAsBoolean(e);
			if (expectedBool == null) {
				// Unknown expected_value vocabulary for a boolean
				// actual — fall back to string equality on the
				// stringified boolean. Same behavior as the host
				// path so an operator who writes a custom profile
				// with a literal "true" still gets a sensible match.
				return valuesMatch(String.valueOf(a), expected);
			}
			return a.equals(expectedBool);
		}
		// Non-boolean actuals (future vim_property kinds — e.g. integer
		// reads): fall through to the generic string/number matcher.
		return valuesMatch(String.valueOf(actual), expected);
	}

	/**
	 * Map an SCG-vocabulary expected_value to a Boolean. Returns null
	 * when the string is not in a recognized boolean dialect — the
	 * caller treats null as "fall back to string equality".
	 */
	static Boolean expectedAsBoolean(String expected) {
		if (expected == null) return null;
		String e = expected.trim();
		if (e.isEmpty()) return null;
		String lower = e.toLowerCase();
		// Security-policy verbs (the most common form in SCG rows for
		// these controls). "Reject" denies the action -> the underlying
		// vim25 boolean is false; "Accept" permits it -> true.
		if ("reject".equals(lower)) return Boolean.FALSE;
		if ("accept".equals(lower)) return Boolean.TRUE;
		if ("disabled".equals(lower) || "deactivated".equals(lower)) {
			return Boolean.FALSE;
		}
		if ("enabled".equals(lower) || "activated".equals(lower)) {
			return Boolean.TRUE;
		}
		// JS-style literals — some custom profiles write "true"/"false"
		// directly.
		if ("true".equals(lower)) return Boolean.TRUE;
		if ("false".equals(lower)) return Boolean.FALSE;
		return null;
	}

	static boolean valuesMatch(String actual, String expected) {
		if (actual == null || expected == null) return false;
		String a = stripQuotes(actual.trim());
		String e = stripQuotes(stripUndefinedSuffix(expected.trim()));
		if (a.equalsIgnoreCase(e)) return true;

		try {
			double av = Double.parseDouble(a);
			double ev = Double.parseDouble(e);
			return Math.abs(av - ev) < 0.001;
		} catch (NumberFormatException ignored) {}

		return false;
	}

	/**
	 * Strip Bob's SCG "X or Undefined" / "X or Not Present" qualifier
	 * so the case-insensitive equality compare in {@link #valuesMatch}
	 * sees a clean expected value when the key IS present in
	 * extraConfig. The {@link #allowsUndefined} path handles the
	 * actual-absent half of the OR.
	 */
	static String stripUndefinedSuffix(String expected) {
		if (expected == null) return null;
		String e = expected.trim();
		String lower = e.toLowerCase();
		if (lower.endsWith(" or undefined")) {
			return e.substring(0, e.length() - " or undefined".length()).trim();
		}
		if (lower.endsWith(" or not present")) {
			return e.substring(0, e.length() - " or not present".length()).trim();
		}
		return e;
	}

	private static String stripQuotes(String s) {
		if (s.length() >= 2 && s.charAt(0) == '"'
				&& s.charAt(s.length() - 1) == '"') {
			return s.substring(1, s.length() - 1);
		}
		return s;
	}

	public static final class ComplianceResult {
		public final String hostname;
		public final int passCount;
		public final int failCount;
		public final int totalCount;
		// Declared-but-unreadable controls — recipe present but the read
		// produced nothing. Excluded from pass/fail/totalCount; surfaced
		// as a coverage signal (VCF-CF Compliance|unreadable_count).
		public final int unreadableCount;
		public final double score;
		public final List<ControlResult> controlResults;

		public ComplianceResult(String hostname, int passCount, int failCount,
				int totalCount, int unreadableCount, double score,
				List<ControlResult> controlResults) {
			this.hostname = hostname;
			this.passCount = passCount;
			this.failCount = failCount;
			this.totalCount = totalCount;
			this.unreadableCount = unreadableCount;
			this.score = score;
			this.controlResults = controlResults;
		}
	}

	public static final class ControlResult {
		public final String scgId;
		public final String actual;
		public final String expected;
		public final boolean compliant;
		public final String description;

		public ControlResult(String scgId, String actual, String expected,
				boolean compliant, String description) {
			this.scgId = scgId;
			this.actual = actual;
			this.expected = expected;
			this.compliant = compliant;
			this.description = description;
		}
	}
}
