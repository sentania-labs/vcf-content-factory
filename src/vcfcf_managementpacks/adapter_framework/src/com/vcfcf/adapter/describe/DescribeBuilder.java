package com.vcfcf.adapter.describe;

import java.util.ArrayList;
import java.util.List;

/**
 * Typed builder for {@code describe.xml} content.
 *
 * <p>MVP coverage: CredentialKinds, ResourceKinds, ResourceIdentifiers,
 * ResourceGroups, ResourceAttributes. Sufficient for hello-world and
 * simple data-collection adapters. Extension hooks are provided for
 * future elements (Symptoms, Alerts, Capacity, etc.).
 *
 * <p>Usage:
 * <pre>{@code
 * String xml = DescribeBuilder.forAdapter("HelloWorldAdapter", 1, 1)
 *     .credentialKind("helloworld_credentials", 2)
 *         .field("username", "string", true, false)
 *         .field("password", "string", true, true)
 *     .done()
 *     .resourceKind("HelloWorldInstance", 7, 1, 3)
 *         .credentialRef("helloworld_credentials")
 *         .identifier("host", "string", true, 4)
 *     .done()
 *     .resourceKind("HelloResource", 1, 1, 10)
 *         .identifier("id", "string", true, 11)
 *         .group("Metrics", 12)
 *             .attribute("tickCount", "float", false, 13)
 *         .doneGroup()
 *         .group("Properties", 14)
 *             .attribute("greeting", "string", true, 15)
 *         .doneGroup()
 *     .done()
 *     .build();
 * }</pre>
 *
 * <p>The builder outputs the {@code describe.xml} as a string. This is
 * used by {@link com.vcfcf.adapter.VcfCfAdapter} to write the
 * {@code describe.xml} at build time.
 */
public final class DescribeBuilder {

	private final String adapterKindKey;
	private final int nameKey;
	private final int version;
	private final List<CredentialKindSpec> credentialKinds = new ArrayList<>();
	private final List<ResourceKindSpec> resourceKinds = new ArrayList<>();

	private DescribeBuilder(String adapterKindKey, int nameKey, int version) {
		this.adapterKindKey = adapterKindKey;
		this.nameKey = nameKey;
		this.version = version;
	}

	/**
	 * Start building a describe.xml for the given adapter kind.
	 *
	 * @param adapterKindKey the adapter kind key (must match adapter.properties KINDKEY)
	 * @param nameKey        the i18n key for the adapter kind display name
	 * @param version        the describe.xml version integer (not the pak semver)
	 */
	public static DescribeBuilder forAdapter(String adapterKindKey, int nameKey, int version) {
		return new DescribeBuilder(adapterKindKey, nameKey, version);
	}

	/** Begin declaring a CredentialKind. */
	public CredentialKindBuilder credentialKind(String key, int credNameKey) {
		CredentialKindSpec spec = new CredentialKindSpec(key, credNameKey);
		credentialKinds.add(spec);
		return new CredentialKindBuilder(this, spec);
	}

	/** Begin declaring a ResourceKind. */
	public ResourceKindBuilder resourceKind(String key, int type, int subType, int rkNameKey) {
		ResourceKindSpec spec = new ResourceKindSpec(key, type, subType, rkNameKey);
		resourceKinds.add(spec);
		return new ResourceKindBuilder(this, spec);
	}

	/** Build and return the describe.xml as a string. */
	public String build() {
		StringBuilder sb = new StringBuilder();
		sb.append("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n");
		sb.append("<AdapterKind xmlns=\"http://schemas.vmware.com/vcops/schema\"\n");
		sb.append("             xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\"\n");
		sb.append("             key=\"").append(escape(adapterKindKey)).append("\"\n");
		sb.append("             nameKey=\"").append(nameKey).append("\"\n");
		sb.append("             version=\"").append(version).append("\"\n");
		sb.append("             xsi:schemaLocation=\"http://schemas.vmware.com/vcops/schema describeSchema.xsd\">\n");

		if (!credentialKinds.isEmpty()) {
			sb.append("\t<CredentialKinds>\n");
			for (CredentialKindSpec ck : credentialKinds) {
				sb.append("\t\t<CredentialKind key=\"").append(escape(ck.key))
						.append("\" nameKey=\"").append(ck.nameKey).append("\">\n");
				for (FieldSpec f : ck.fields) {
					sb.append("\t\t\t<CredentialField key=\"").append(escape(f.key))
							.append("\" nameKey=\"").append(f.nameKey)
							.append("\" type=\"").append(f.type)
							.append("\" required=\"").append(f.required)
							.append("\"");
					if (f.password) sb.append(" password=\"true\"");
					if (f.dispOrder > 0) sb.append(" dispOrder=\"").append(f.dispOrder).append("\"");
					sb.append("/>\n");
				}
				sb.append("\t\t</CredentialKind>\n");
			}
			sb.append("\t</CredentialKinds>\n");
		}

		sb.append("\t<ResourceKinds>\n");
		for (ResourceKindSpec rk : resourceKinds) {
			sb.append("\t\t<ResourceKind key=\"").append(escape(rk.key))
					.append("\" nameKey=\"").append(rk.nameKey)
					.append("\" type=\"").append(rk.type)
					.append("\"");
			if (rk.subType != 1) sb.append(" subType=\"").append(rk.subType).append("\"");
			if (rk.credentialKind != null)
				sb.append(" credentialKind=\"").append(escape(rk.credentialKind)).append("\"");
			if (rk.monitoringInterval > 0)
				sb.append(" monitoringInterval=\"").append(rk.monitoringInterval).append("\"");
			sb.append(">\n");

			for (IdentifierSpec id : rk.identifiers) {
				sb.append("\t\t\t<ResourceIdentifier key=\"").append(escape(id.key))
						.append("\" nameKey=\"").append(id.nameKey)
						.append("\" type=\"").append(id.type)
						.append("\" required=\"").append(id.required)
						.append("\"");
				if (id.dispOrder > 0) sb.append(" dispOrder=\"").append(id.dispOrder).append("\"");
				if (id.identType > 0) sb.append(" identType=\"").append(id.identType).append("\"");
				sb.append("/>\n");
			}

			for (GroupSpec g : rk.groups) {
				sb.append("\t\t\t<ResourceGroup key=\"").append(escape(g.key))
						.append("\" nameKey=\"").append(g.nameKey)
						.append("\" instanced=\"false\">\n");
				for (AttributeSpec a : g.attributes) {
					sb.append("\t\t\t\t<ResourceAttribute key=\"").append(escape(a.key))
							.append("\" nameKey=\"").append(a.nameKey)
							.append("\" dataType=\"").append(a.dataType)
							.append("\" isProperty=\"").append(a.isProperty)
							.append("\"");
					if (a.defaultMonitored) sb.append(" defaultMonitored=\"true\"");
					if (a.unit != null) sb.append(" unit=\"").append(escape(a.unit)).append("\"");
					sb.append("/>\n");
				}
				sb.append("\t\t\t</ResourceGroup>\n");
			}

			sb.append("\t\t</ResourceKind>\n");
		}
		sb.append("\t</ResourceKinds>\n");

		sb.append("\t<LicenseConfig enabled=\"false\"/>\n");
		sb.append("</AdapterKind>\n");

		return sb.toString();
	}

	private static String escape(String s) {
		return s.replace("&", "&amp;").replace("\"", "&quot;").replace("<", "&lt;");
	}

	// -----------------------------------------------------------------------
	// Internal spec types
	// -----------------------------------------------------------------------

	static final class CredentialKindSpec {
		final String key;
		final int nameKey;
		final List<FieldSpec> fields = new ArrayList<>();
		CredentialKindSpec(String key, int nameKey) { this.key = key; this.nameKey = nameKey; }
	}

	static final class FieldSpec {
		final String key;
		final int nameKey;
		final String type;
		final boolean required;
		final boolean password;
		final int dispOrder;
		FieldSpec(String key, int nameKey, String type, boolean required, boolean password, int dispOrder) {
			this.key = key; this.nameKey = nameKey; this.type = type;
			this.required = required; this.password = password; this.dispOrder = dispOrder;
		}
	}

	static final class ResourceKindSpec {
		final String key;
		final int type;
		final int subType;
		final int nameKey;
		String credentialKind;
		int monitoringInterval;
		final List<IdentifierSpec> identifiers = new ArrayList<>();
		final List<GroupSpec> groups = new ArrayList<>();
		ResourceKindSpec(String key, int type, int subType, int nameKey) {
			this.key = key; this.type = type; this.subType = subType; this.nameKey = nameKey;
		}
	}

	static final class IdentifierSpec {
		final String key;
		final int nameKey;
		final String type;
		final boolean required;
		final int dispOrder;
		final int identType;
		IdentifierSpec(String key, int nameKey, String type, boolean required, int dispOrder, int identType) {
			this.key = key; this.nameKey = nameKey; this.type = type;
			this.required = required; this.dispOrder = dispOrder; this.identType = identType;
		}
	}

	static final class GroupSpec {
		final String key;
		final int nameKey;
		final List<AttributeSpec> attributes = new ArrayList<>();
		GroupSpec(String key, int nameKey) { this.key = key; this.nameKey = nameKey; }
	}

	static final class AttributeSpec {
		final String key;
		final int nameKey;
		final String dataType;
		final boolean isProperty;
		final boolean defaultMonitored;
		final String unit;
		AttributeSpec(String key, int nameKey, String dataType, boolean isProperty,
				boolean defaultMonitored, String unit) {
			this.key = key; this.nameKey = nameKey; this.dataType = dataType;
			this.isProperty = isProperty; this.defaultMonitored = defaultMonitored; this.unit = unit;
		}
	}

	// -----------------------------------------------------------------------
	// Builder inner classes
	// -----------------------------------------------------------------------

	/** Fluent builder for a CredentialKind block. */
	public final class CredentialKindBuilder {
		private final DescribeBuilder parent;
		private final CredentialKindSpec spec;
		private int fieldOrder = 0;

		private CredentialKindBuilder(DescribeBuilder parent, CredentialKindSpec spec) {
			this.parent = parent;
			this.spec = spec;
		}

		/**
		 * Add a credential field.
		 *
		 * @param key      field key
		 * @param nameKey  i18n nameKey
		 * @param type     field type: "string", "integer", "host", "ip"
		 * @param required whether the field is required
		 * @param password whether the field is masked (password)
		 */
		public CredentialKindBuilder field(String key, int nameKey, String type,
				boolean required, boolean password) {
			spec.fields.add(new FieldSpec(key, nameKey, type, required, password, ++fieldOrder));
			return this;
		}

		/** Return to the parent {@link DescribeBuilder}. */
		public DescribeBuilder done() {
			return parent;
		}
	}

	/** Fluent builder for a ResourceKind block. */
	public final class ResourceKindBuilder {
		private final DescribeBuilder parent;
		private final ResourceKindSpec spec;

		private ResourceKindBuilder(DescribeBuilder parent, ResourceKindSpec spec) {
			this.parent = parent;
			this.spec = spec;
		}

		/** Set the credential kind reference on this ResourceKind. */
		public ResourceKindBuilder credentialRef(String credKey) {
			spec.credentialKind = credKey;
			return this;
		}

		/** Set the default monitoring interval in minutes. */
		public ResourceKindBuilder monitoringInterval(int minutes) {
			spec.monitoringInterval = minutes;
			return this;
		}

		/**
		 * Add a ResourceIdentifier.
		 *
		 * @param key       identifier key
		 * @param nameKey   i18n nameKey
		 * @param type      data type ("string", "integer")
		 * @param required  whether required
		 * @param dispOrder display order (1-based)
		 */
		public ResourceKindBuilder identifier(String key, int nameKey, String type,
				boolean required, int dispOrder) {
			spec.identifiers.add(new IdentifierSpec(key, nameKey, type, required, dispOrder, 0));
			return this;
		}

		/** Begin a ResourceGroup within this ResourceKind. */
		public GroupBuilder group(String key, int groupNameKey) {
			GroupSpec g = new GroupSpec(key, groupNameKey);
			spec.groups.add(g);
			return new GroupBuilder(this, g);
		}

		/** Return to the parent {@link DescribeBuilder}. */
		public DescribeBuilder done() {
			return parent;
		}
	}

	/** Fluent builder for a ResourceGroup and its attributes. */
	public final class GroupBuilder {
		private final ResourceKindBuilder parent;
		private final GroupSpec spec;

		private GroupBuilder(ResourceKindBuilder parent, GroupSpec spec) {
			this.parent = parent;
			this.spec = spec;
		}

		/**
		 * Add a ResourceAttribute.
		 *
		 * @param key              attribute key (the metric key stem)
		 * @param nameKey          i18n nameKey
		 * @param dataType         "float", "integer", "long", "double", "string"
		 * @param isProperty       true for properties, false for metrics
		 * @param defaultMonitored true to collect by default
		 */
		public GroupBuilder attribute(String key, int nameKey, String dataType,
				boolean isProperty, boolean defaultMonitored) {
			spec.attributes.add(new AttributeSpec(key, nameKey, dataType, isProperty,
					defaultMonitored, null));
			return this;
		}

		/**
		 * Add a ResourceAttribute with a unit.
		 *
		 * @param key              attribute key
		 * @param nameKey          i18n nameKey
		 * @param dataType         data type
		 * @param isProperty       true for properties
		 * @param defaultMonitored true to collect by default
		 * @param unit             unit string (e.g. "%", "MB", "ms")
		 */
		public GroupBuilder attributeWithUnit(String key, int nameKey, String dataType,
				boolean isProperty, boolean defaultMonitored, String unit) {
			spec.attributes.add(new AttributeSpec(key, nameKey, dataType, isProperty,
					defaultMonitored, unit));
			return this;
		}

		/** Finish the group and return to the ResourceKind builder. */
		public ResourceKindBuilder doneGroup() {
			return parent;
		}
	}
}
