package com.vcfcf.adapters.compliance;

import com.vcfcf.adapter.VcfCfAdapter;
import com.vcfcf.adapter.json.SimpleJson;

import com.integrien.alive.common.adapter3.DiscoveryParam;
import com.integrien.alive.common.adapter3.ResourceKey;
import com.integrien.alive.common.adapter3.ResourceStatus;
import com.integrien.alive.common.adapter3.TestParam;
import com.integrien.alive.common.adapter3.config.ResourceConfig;
import com.integrien.alive.common.adapter3.config.ResourceIdentifierConfig;
import com.vmware.tvs.vrealize.adapter.core.collection.CollectionException;
import com.vmware.tvs.vrealize.adapter.core.collection.live.LiveCollector;
import com.vmware.tvs.vrealize.adapter.core.data.Resource;
import com.vmware.tvs.vrealize.adapter.core.data.ResourceCollection;
import com.vmware.tvs.vrealize.adapter.core.discovery.Discoverer;
import com.vmware.tvs.vrealize.adapter.core.test.TestException;
import com.vmware.tvs.vrealize.adapter.core.test.Tester;

import java.time.Instant;
import java.util.Map;

public final class ComplianceAdapter extends VcfCfAdapter<ComplianceConfig> {

	private static final String ADAPTER_KIND = "vcfcf_compliance";

	private volatile VCenterApiClient vcApi;
	private volatile VSphereClient vsphere;
	private volatile BenchmarkLoader benchmarkLoader;
	private volatile ComplianceStitcher stitcher;

	public ComplianceAdapter() {
		super();
	}

	public ComplianceAdapter(String adapterDir, Integer adapterInstanceId) {
		super(adapterDir, adapterInstanceId);
	}

	@Override
	protected String getAdapterDirectory() {
		return ADAPTER_KIND;
	}

	@Override
	public boolean isDynamicMetricsAllowed() {
		return true;
	}

	@Override
	public void configure(ResourceStatus status, ResourceConfig resourceConfig) {
		String vcenterHost = getIdentifier(resourceConfig, "vcenter_host");
		String profile = getIdentifier(resourceConfig, "benchmark_profile");
		String customPath = getIdentifier(resourceConfig, "custom_profile_path");
		String allowInsecure = getIdentifier(resourceConfig, "allowInsecure");
		String username = getCredentialField(resourceConfig, "username");
		String password = getCredentialField(resourceConfig, "password");

		this.config = new ComplianceConfig(
				vcenterHost, username, password,
				profile, customPath, allowInsecure);

		this.vcApi = new VCenterApiClient(
				config.baseUrl(), config.username, config.password,
				config.allowInsecure);

		this.vsphere = new VSphereClient(
				config.vcenterHost, config.username, config.password);

		this.benchmarkLoader = new BenchmarkLoader();

		if (this.suiteAPIClient != null) {
			this.stitcher = new ComplianceStitcher(
					this.suiteAPIClient, this.logger);
		}

		logInfo("ComplianceAdapter configured: vcenter=" + config.vcenterHost
				+ " profile=" + config.benchmarkProfile
				+ " stitcher=" + (stitcher != null));
	}

	@Override
	public Tester getTester(ResourceStatus status, ResourceConfig resourceConfig) {
		return (TestParam param) -> {
			try {
				vcApi.login();
				SimpleJson hosts = vcApi.listHosts();
				int count = 0;
				if (!hosts.isNull() && hosts.isList()) {
					count = hosts.asList().size();
				}
				logInfo("Test OK: connected to " + config.vcenterHost
						+ ", " + count + " host(s) visible");
			} catch (Exception e) {
				throw new TestException("vCenter connection test failed: "
						+ e.getMessage(), e);
			}
		};
	}

	@Override
	public Discoverer getDiscoverer(ResourceStatus status,
			ResourceConfig resourceConfig) {
		return (DiscoveryParam param) -> {
			logInfo("ComplianceAdapter discover: creating ComplianceWorld");
			ResourceCollection collection = new ResourceCollection();

			Resource world = createResource("ComplianceWorld",
					"Compliance World", "world_id", "compliance_world");
			collection.add(world);

			return collection;
		};
	}

	@Override
	public LiveCollector getLiveDataCollector(ResourceStatus status,
			ResourceConfig resourceConfig) {
		return new LiveCollector() {
			@Override
			public ResourceCollection getCurrentMetrics(ResourceConfig rc,
					ResourceCollection acc)
					throws CollectionException, InterruptedException {
				ResourceCollection result = new ResourceCollection();

				try {
					vsphere.ensureConnected();

					String confDir = getAdaptersHome()
							+ "/" + ADAPTER_KIND + "/conf";
					BenchmarkProfile profile = benchmarkLoader.load(
							config.benchmarkProfile,
							config.customProfilePath,
							confDir);
					// Fix #2: metric-tree subnamespace and profile_name
					// must agree. Always derive both from the resolved
					// profile (profile.name), not from the requested
					// config.benchmarkProfile. If the loader fell back
					// (e.g. unknown profile name), surface it.
					if (!profile.name.equals(config.benchmarkProfile)) {
						logWarn("Profile load divergence: requested='"
								+ config.benchmarkProfile + "' resolved='"
								+ profile.name + "' — metric tree and "
								+ "profile_name will use the resolved name");
					}

					logInfo("suiteAPIClient=" + (suiteAPIClient != null)
							+ " stitcher=" + (stitcher != null));
					if (stitcher != null) {
						try {
							stitcher.loadHostResources();
							logInfo("Stitcher loaded: "
									+ stitcher.size() + " hosts");
						} catch (Exception e) {
							logError("Stitcher loadHostResources failed: "
									+ e.getClass().getName()
									+ ": " + e.getMessage(), e);
						}
					}

					java.util.List<VSphereClient.HostInfo> hosts =
							vsphere.getHosts();
					if (hosts.isEmpty()) {
						logWarn("No hosts returned from vCenter SOAP");
						return result;
					}
					logInfo("vSphere SOAP: " + hosts.size() + " hosts");

					int totalHosts = 0;
					int scoredHosts = 0;
					double scoreSum = 0;
					int belowThreshold = 0;

					for (VSphereClient.HostInfo hostInfo : hosts) {
						String hostId = hostInfo.moid;
						String hostName = hostInfo.name;

						logInfo("Evaluating host " + hostName
								+ " (" + hostId + ")");

						java.util.Map<String, String> advSettings;
						try {
							advSettings = vsphere.getAdvancedSettings(
									hostInfo.moRef);
							logInfo("Host " + hostName + ": "
									+ advSettings.size()
									+ " advanced settings");
						} catch (Exception e) {
							logWarn("Failed to read settings for "
									+ hostName + ": " + e.getMessage());
							advSettings = new java.util.HashMap<>();
						}

						ControlEvaluator.ComplianceResult cr =
								ControlEvaluator.evaluateAdvancedSettings(
										profile, advSettings, hostName);

						totalHosts++;
						// Only fold a host into the world average if its
						// per-host score is REAL data (totalCount > 0).
						// ControlEvaluator returns score=100.0 as a
						// zero-divisor sentinel when no profile controls
						// were evaluable against the host — folding that
						// in produces a bogus 100 average (this is what
						// devel showed pre-fix: avg=100 despite per-control
						// failures). Hosts with no signal are still counted
						// in total_hosts so operators see them, but they
						// don't move the score needle.
						if (cr.totalCount > 0) {
							scoredHosts++;
							scoreSum += cr.score;
							if (cr.score < 95.0) belowThreshold++;
						}

						logInfo("Host " + hostName + ": score="
								+ String.format("%.1f", cr.score)
								+ "% (" + cr.passCount + " pass, "
								+ cr.failCount + " fail, "
								+ cr.totalCount + " total)");

						if (stitcher != null) {
							ComplianceStitcher.HostEntry he =
									stitcher.matchHost(hostName, hostId);
							if (he != null) {
								pushComplianceViaClient(he.resourceId,
										cr, profile.name);
								logInfo("Pushed compliance data to "
										+ hostName
										+ " (resource=" + he.resourceId
										+ ")");
							}
						}
					}

					Resource world = createResource("ComplianceWorld",
							"Compliance World",
							"world_id", "compliance_world");
					world.addData("Summary|total_hosts", (double) totalHosts);
					// Skip avg_host_score and hosts_below_threshold entirely
					// when no host produced real data — publishing a sentinel
					// (0.0 or 100.0) is indistinguishable from a real result.
					// Operators will see the metric gap on the dashboard and
					// know to investigate. profile_name + total_hosts still
					// publish so they know the adapter ran.
					if (scoredHosts > 0) {
						world.addData("Summary|avg_host_score",
								scoreSum / scoredHosts);
						world.addData("Summary|hosts_below_threshold",
								(double) belowThreshold);
					} else {
						logWarn("No hosts produced real compliance signal "
								+ "(all totalCount==0); skipping "
								+ "Summary|avg_host_score and "
								+ "Summary|hosts_below_threshold so the "
								+ "scoreboard reads 'no data' rather than "
								+ "a sentinel value");
					}
					addProperty(world, "Summary|profile_name",
							profile.name);
					addProperty(world, "Summary|last_scan_timestamp",
							Instant.now().toString());
					result.add(world);

					logInfo("ComplianceAdapter collection complete: "
							+ totalHosts + " hosts seen, "
							+ scoredHosts + " produced real signal");

				} catch (InterruptedException ie) {
					throw ie;
				} catch (Exception e) {
					logError("Collection failed: " + e.getMessage(), e);
					throw new CollectionException(
							"Compliance collection failed: " + e.getMessage(), e);
				}

				return result;
			}

			@Override
			public ResourceCollection getEvents(ResourceConfig rc,
					ResourceCollection acc)
					throws CollectionException, InterruptedException {
				return new ResourceCollection();
			}

			@Override
			public ResourceCollection getRelationships(ResourceConfig rc,
					ResourceCollection acc)
					throws CollectionException, InterruptedException {
				return new ResourceCollection();
			}

			@Override
			public boolean shouldForceUpdateRelationships() {
				return false;
			}
		};
	}

	// pushComplianceViaClient — publishes two layers of compliance data
	// onto the matched VMWARE HostSystem resource:
	//
	//   First-class rollups (fix #1, profile-agnostic — alerts target
	//   these so the alert pipeline survives profile changes):
	//     VCF-CF Compliance|score          (numeric, percentage 0..100)
	//     VCF-CF Compliance|pass_count     (numeric)
	//     VCF-CF Compliance|fail_count     (numeric)
	//     VCF-CF Compliance|total_count    (numeric)
	//     VCF-CF Compliance|profile_name   (string property)
	//
	//   Per-control raw data (profile-versioned subtree, for the
	//   metric browser and drill-down views):
	//     VCF-CF Compliance|<profile>|<control_id>|Actual       (string)
	//     VCF-CF Compliance|<profile>|<control_id>|Expected     (string)
	//     VCF-CF Compliance|<profile>|<control_id>|Description  (string)
	//     VCF-CF Compliance|<profile>|<control_id>|Compliant    (numeric 0/1)
	//
	// The <profile> segment uses the RESOLVED profile name (see fix #2
	// in BenchmarkLoader) so the subtree path and the profile_name
	// rollup always agree.
	private void pushComplianceViaClient(String resourceId,
			ControlEvaluator.ComplianceResult cr, String profileName) {
		long ts = System.currentTimeMillis();
		String prefix = "VCF-CF Compliance|" + profileName;

		java.util.LinkedHashMap<String, String> props =
				new java.util.LinkedHashMap<>();
		for (ControlEvaluator.ControlResult ctrl : cr.controlResults) {
			String ctrlPrefix = prefix + "|" + ctrl.scgId;
			props.put(ctrlPrefix + "|Actual", ctrl.actual);
			props.put(ctrlPrefix + "|Expected", ctrl.expected);
			props.put(ctrlPrefix + "|Description", ctrl.description);
		}
		props.put("VCF-CF Compliance|profile_name", profileName);

		java.util.LinkedHashMap<String, Double> stats =
				new java.util.LinkedHashMap<>();
		for (ControlEvaluator.ControlResult ctrl : cr.controlResults) {
			String ctrlPrefix = prefix + "|" + ctrl.scgId;
			stats.put(ctrlPrefix + "|Compliant",
					ctrl.compliant ? 1.0 : 0.0);
		}
		stats.put("VCF-CF Compliance|score", cr.score);
		stats.put("VCF-CF Compliance|pass_count", (double) cr.passCount);
		stats.put("VCF-CF Compliance|fail_count", (double) cr.failCount);
		stats.put("VCF-CF Compliance|total_count", (double) cr.totalCount);

		stitcher.pushProperties(resourceId, props, ts);
		stitcher.pushStats(resourceId, stats, ts);
	}

	private Resource createResource(String kind, String name,
			String idKey, String idValue) {
		ResourceKey key = new ResourceKey(name, kind, ADAPTER_KIND);
		key.addIdentifier(new ResourceIdentifierConfig(idKey, idValue, true));
		return new Resource(key);
	}

	@Override
	public void onDiscard() {
		if (vcApi != null) vcApi.logout();
		if (vsphere != null) vsphere.disconnect();
		super.onDiscard();
	}
}
