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

	public List<Control> vCenterControls() {
		List<Control> result = new java.util.ArrayList<>();
		for (Control c : controls) {
			if (c.isVCenterControl()) result.add(c);
		}
		return result;
	}

	public List<Control> dvsControls() {
		List<Control> result = new java.util.ArrayList<>();
		for (Control c : controls) {
			if (c.isDvsControl()) result.add(c);
		}
		return result;
	}

	public List<Control> dvpgControls() {
		List<Control> result = new java.util.ArrayList<>();
		for (Control c : controls) {
			if (c.isDvpgControl()) result.add(c);
		}
		return result;
	}

	public List<Control> clusterControls() {
		List<Control> result = new java.util.ArrayList<>();
		for (Control c : controls) {
			if (c.isClusterControl()) result.add(c);
		}
		return result;
	}

	/**
	 * Controls matching a given canonical {@code resource_kind} string.
	 * Used by the per-kind loop in {@link ComplianceAdapter} so the
	 * switch on resource kind doesn't need to know each
	 * {@code isXControl()} predicate.
	 */
	public List<Control> controlsForResourceKind(String resourceKind) {
		List<Control> result = new java.util.ArrayList<>();
		if (resourceKind == null) return result;
		for (Control c : controls) {
			if (resourceKind.equals(c.resourceKind)) result.add(c);
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
	 *
	 * <p>{@code advanced_setting} is evaluable unconditionally (the bulk
	 * {@code queryOptions(null)} read backs it). {@code vim_property} is
	 * evaluable only when the control carries a non-empty
	 * {@code read_recipe} (canonical column 13) — the recipe is the
	 * data-driven read spec the generic {@code VSphereClient.readByRecipe}
	 * reader consumes. A vim_property control with no recipe is
	 * non-evaluable / informational: it loads for traceability but is
	 * skipped by the evaluator. This is what makes a new vim_property
	 * control pure CSV data (a recipe whose style already exists scores
	 * with zero Java change) while keeping the "unreadable is not
	 * compliant" guarantee — an absent recipe is never guessed.
	 */
	private static boolean isEvaluableKind(String parameterKind,
			String readRecipe) {
		if ("advanced_setting".equals(parameterKind)) {
			return true;
		}
		// vim_property and esxcli are BOTH recipe-driven: evaluable only
		// when the control carries a non-empty read_recipe (the recipe IS
		// the read path). esxcli became evaluable in build 36 — its
		// read_recipe carries the esxcli:<namespace.command>:<Field> spec
		// consumed by VSphereClient.readEsxcliRecipe, which rides the
		// existing vCenter session (no host credentials). An esxcli
		// control with no recipe stays non-evaluable / informational,
		// exactly like a vim_property control without one — so a missing
		// recipe is a coverage gap the operator sees, never a guess.
		if ("vim_property".equals(parameterKind)
				|| "esxcli".equals(parameterKind)) {
			return readRecipe != null && !readRecipe.trim().isEmpty();
		}
		// vami_api (build 41) is recipe-driven exactly like vim_property /
		// esxcli: evaluable only when the control carries a non-empty
		// read_recipe (the vami:<appliance-path>:<json-field> spec consumed
		// by VamiApiClient over the vCenter Appliance REST session). A
		// vami_api control with no recipe stays non-evaluable / informational
		// — never a guess.
		if ("vami_api".equals(parameterKind)) {
			return readRecipe != null && !readRecipe.trim().isEmpty();
		}
		return false;
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
		// Canonical column 13. read_recipe = "<style>:<vim_path>" for a
		// vim_property control; empty for every other kind and for
		// vim_property controls whose extraction is not yet declared.
		// See CANONICAL_SCHEMA.md and VSphereClient.readByRecipe.
		public final String readRecipe;

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
				String remediationText, String readRecipe) {
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
			this.readRecipe = readRecipe != null ? readRecipe : "";

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

		public boolean isVCenterControl() {
			return "VCenterAdapterInstance".equals(resourceKind);
		}

		public boolean isDvsControl() {
			return "DistributedVirtualSwitch".equals(resourceKind);
		}

		public boolean isDvpgControl() {
			return "DistributedVirtualPortgroup".equals(resourceKind);
		}

		public boolean isClusterControl() {
			return "ClusterComputeResource".equals(resourceKind);
		}

		public boolean isEvaluable() {
			return isEvaluableKind(parameterKind, readRecipe);
		}

		/**
		 * True when this control declares a vim_property read it cannot
		 * (yet) satisfy from a recipe — i.e. a {@code vim_property}
		 * control with an empty {@code read_recipe}. Such controls are
		 * non-evaluable, but the distinction matters: a missing recipe
		 * is a profile/coverage gap the operator should see, not a pass.
		 * (Used only for diagnostics; the evaluator keys off the recipe
		 * directly.)
		 */
		public boolean isVimPropertyWithoutRecipe() {
			return "vim_property".equals(parameterKind)
					&& (readRecipe == null || readRecipe.trim().isEmpty());
		}
	}
}
