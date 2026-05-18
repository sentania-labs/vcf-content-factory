package com.vcfcf.adapters.helloworld;

/**
 * Configuration POJO for the Hello World SDK adapter.
 *
 * <p>Populated from the adapter instance ResourceConfig by
 * {@link HelloWorldAdapter#configure}.
 */
public final class HelloWorldConfig {

	/** The greeting name (from the adapter instance identifier). */
	public String greetingName;

	public HelloWorldConfig(String greetingName) {
		this.greetingName = (greetingName != null && !greetingName.isEmpty())
				? greetingName
				: "World";
	}
}
