package com.vcfcf.adapters.compliance;

import java.util.Collections;
import java.util.List;

/**
 * In-memory representation of a normalized benchmark profile.
 *
 * The profile is built from a canonical CSV (see
 * CANONICAL_SCHEMA.md). Each {@link Control} carries the
 * full canonical row plus convenience predicates the evaluator uses
 * to filter the profile to controls it can evaluate against the
 * resource kind in front of it.
 *
 * <p>Field naming: the canonical schema field names are reproduced as
 * {@code controlId} / {@code resourceKind} / {@code parameter} / etc.
 * The legacy field names {@code scgId}, {@code configParameter},
 * {@code suggestedValue}, and {@code description} are retained as
 * aliases so {@link ControlEvaluator} and
 * {@link ComplianceAdapter#pushComplianceViaClient} keep compiling
 * without touching their loops.
 */
public final class BenchmarkProfile {

	public final String name;
	public final List<Control> controls;

	public BenchmarkProfile(String name, List<Control> controls) {
		this.name = name;
		this.controls = Collections.unmodifiableList(controls);
	}

	public List<Control> hostControls() {
		List<Control> result = new java.util.ArrayList<>();
		for (Control c : controls) {
			if (c.isHostControl()) result.add(c);
		}
		return result;
	}

	public List<Control> vmControls() {
		List<Control> result = new java.util.ArrayList<>();
		for (Control c : controls) {
			if (c.isVmControl()) result.add(c);
		}
		return result;
	}

	/**
	 * Subset of controls that the adapter can actually evaluate today.
	 * Derived from {@code parameter_kind}: only {@code advanced_setting}
	 * is evaluable (vSphere SOAP {@code OptionManager.QueryOptions} is
	 * the only assessment path implemented). The rest ship in the
	 * profile for traceability and future expansion.
	 */
	public List<Control> evaluableControls() {
		List<Control> result = new java.util.ArrayList<>();
		for (Control c : controls) {
			if (c.isEvaluable()) result.add(c);
		}
		return result;
	}

	/**
	 * Canonical-schema kinds that the evaluator can actually score
	 * against vSphere SOAP-collected data. Keep this set tight — adding
	 * a kind here without backing it with a real assessment path
	 * reintroduces the "garbage in, score=100" failure mode that
	 * positional indexing produced on SCG 9.0.
	 */
	private static boolean isEvaluableKind(String parameterKind) {
		return "advanced_setting".equals(parameterKind);
	}

	public static final class Control {
		// Canonical schema fields (CANONICAL_SCHEMA.md).
		public final String controlId;
		public final String priority;
		public final String resourceKind;
		public final String adapterKind;
		public final String parameter;
		public final String parameterKind;
		public final String valueType;
		public final String expectedValue;
		public final String title;
		public final String descriptionText;
		public final String sourceRef;
		public final String remediationText;

		// Legacy aliases (kept so ControlEvaluator + the adapter's
		// push loop keep compiling without churn). New code should
		// prefer the canonical-schema names above.
		public final String scgId;
		public final String configParameter;
		public final String suggestedValue;
		public final String description;
		// component is no longer in the canonical schema; legacy
		// callers that referenced it should switch to resourceKind.
		// Kept as a derived alias for one release to ease the
		// transition: filled with the value of resourceKind.
		public final String component;
		// Old "assessmentCommand" is dropped — the remediation/
		// assessment text now lives in remediationText (single field).

		public Control(String controlId, String priority, String resourceKind,
				String adapterKind, String parameter, String parameterKind,
				String valueType, String expectedValue, String title,
				String descriptionText, String sourceRef,
				String remediationText) {
			this.controlId = controlId != null ? controlId : "";
			this.priority = priority != null ? priority : "P2";
			this.resourceKind = resourceKind != null ? resourceKind : "";
			this.adapterKind = adapterKind != null ? adapterKind : "";
			this.parameter = parameter != null ? parameter : "";
			this.parameterKind = parameterKind != null ? parameterKind
					: "manual_audit";
			this.valueType = valueType != null ? valueType : "string";
			this.expectedValue = expectedValue != null ? expectedValue : "";
			this.title = title != null ? title : "";
			this.descriptionText = descriptionText != null ? descriptionText : "";
			this.sourceRef = sourceRef != null ? sourceRef : "";
			this.remediationText = remediationText != null
					? remediationText : "";

			// Mirror canonical fields onto legacy aliases.
			this.scgId = this.controlId;
			this.configParameter = this.parameter;
			this.suggestedValue = this.expectedValue;
			this.description = this.descriptionText;
			this.component = this.resourceKind;
		}

		public boolean isHostControl() {
			return "HostSystem".equals(resourceKind);
		}

		public boolean isVmControl() {
			return "VirtualMachine".equals(resourceKind);
		}

		public boolean isEvaluable() {
			return isEvaluableKind(parameterKind);
		}
	}
}
