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
		List<ControlResult> results = new ArrayList<>();
		int pass = 0;
		int fail = 0;

		for (BenchmarkProfile.Control control : profile.hostControls()) {
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

		return new ComplianceResult(hostname, pass, fail, total, score, results);
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
