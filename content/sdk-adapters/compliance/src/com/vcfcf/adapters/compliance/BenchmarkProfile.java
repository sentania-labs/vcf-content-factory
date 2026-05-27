package com.vcfcf.adapters.compliance;

import java.util.Collections;
import java.util.List;

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

	public static final class Control {
		public final String scgId;
		public final String component;
		public final String priority;
		public final String description;
		public final String configParameter;
		public final String defaultValue;
		public final String suggestedValue;
		public final String assessmentCommand;

		public Control(String scgId, String component, String priority,
				String description, String configParameter,
				String defaultValue, String suggestedValue,
				String assessmentCommand) {
			this.scgId = scgId;
			this.component = component;
			this.priority = priority;
			this.description = description;
			this.configParameter = configParameter;
			this.defaultValue = defaultValue;
			this.suggestedValue = suggestedValue;
			this.assessmentCommand = assessmentCommand;
		}

		public boolean isHostControl() {
			if (component == null) return false;
			String c = component.toLowerCase();
			return c.contains("esxi") || c.contains("esx");
		}

		public boolean isVmControl() {
			if (component == null) return false;
			String c = component.toLowerCase();
			return c.contains("virtual machine") || c.equals("vm");
		}
	}
}
