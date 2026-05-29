package com.vcfcf.adapters.compliance;

import com.vcfcf.adapter.json.SimpleJson;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public final class ControlEvaluator {

	public static ComplianceResult evaluate(BenchmarkProfile profile,
			SimpleJson hostDetail, String hostname) {
		if (hostDetail == null || hostDetail.isNull()) {
			return new ComplianceResult(hostname, 0, 0, 0, 100.0,
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
			if (actual == null) {
				continue;
			}

			String expected = control.suggestedValue;
			boolean compliant = valuesMatch(actual, expected);

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

		return new ComplianceResult(resourceName, pass, fail, total, score,
				results);
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
	 */
	public static ComplianceResult evaluateVimProperties(
			List<BenchmarkProfile.Control> controls,
			Map<String, Object> propertyValues, String resourceName) {
		List<ControlResult> results = new ArrayList<>();
		int pass = 0;
		int fail = 0;

		for (BenchmarkProfile.Control control : controls) {
			if (!"vim_property".equals(control.parameterKind)) {
				continue;
			}
			String param = control.configParameter;
			if (param == null || param.isEmpty() || "N/A".equals(param)) {
				continue;
			}
			if (param.contains("\n")) continue;

			Object actualObj = propertyValues.get(param);
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

		return new ComplianceResult(resourceName, pass, fail, total, score,
				results);
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
		String e = stripQuotes(expected.trim());
		if (a.equalsIgnoreCase(e)) return true;

		try {
			double av = Double.parseDouble(a);
			double ev = Double.parseDouble(e);
			return Math.abs(av - ev) < 0.001;
		} catch (NumberFormatException ignored) {}

		return false;
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
		public final double score;
		public final List<ControlResult> controlResults;

		public ComplianceResult(String hostname, int passCount, int failCount,
				int totalCount, double score, List<ControlResult> controlResults) {
			this.hostname = hostname;
			this.passCount = passCount;
			this.failCount = failCount;
			this.totalCount = totalCount;
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
