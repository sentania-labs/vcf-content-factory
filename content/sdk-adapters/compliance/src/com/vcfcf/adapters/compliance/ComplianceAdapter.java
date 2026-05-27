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
					vcApi.ensureSession();

					String confDir = getAdaptersHome()
							+ "/" + ADAPTER_KIND + "/conf";
					BenchmarkProfile profile = benchmarkLoader.load(
							config.benchmarkProfile,
							config.customProfilePath,
							confDir);

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

					SimpleJson hosts = vcApi.listHosts();
					if (hosts.isNull() || !hosts.isList()) {
						logWarn("No hosts returned from vCenter");
						return result;
					}

					int totalHosts = 0;
					double scoreSum = 0;
					int belowThreshold = 0;

					for (SimpleJson hostEntry : hosts.asList()) {
						String hostId = hostEntry.get("host").asString("");
						String hostName = hostEntry.get("name").asString("");

						if (hostId.isEmpty() || hostName.isEmpty()) continue;

						logInfo("Evaluating host " + hostName
								+ " (" + hostId + ")");

						SimpleJson hostDetail = null;
						try {
							hostDetail = vcApi.getHostDetail(hostId);
						} catch (Exception e) {
							logWarn("Host detail query failed for "
									+ hostName + " (expected until SOAP "
									+ "expansion): " + e.getMessage());
						}

						ControlEvaluator.ComplianceResult cr =
								ControlEvaluator.evaluate(
										profile, hostDetail, hostName);

						totalHosts++;
						scoreSum += cr.score;
						if (cr.score < 95.0) belowThreshold++;

						logInfo("Host " + hostName + ": score="
								+ String.format("%.1f", cr.score)
								+ "% (" + cr.passCount + " pass, "
								+ cr.failCount + " fail, "
								+ cr.totalCount + " total)");

						if (stitcher != null) {
							ComplianceStitcher.HostEntry he =
									stitcher.matchHost(hostName, hostId);
							if (he != null) {
								pushComplianceData(he.resource, cr,
										config.benchmarkProfile);
								result.add(he.resource);
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
					world.addData("Summary|avg_host_score",
							totalHosts > 0 ? scoreSum / totalHosts : 0.0);
					world.addData("Summary|hosts_below_threshold",
							(double) belowThreshold);
					addProperty(world, "Summary|profile_name",
							config.benchmarkProfile);
					addProperty(world, "Summary|last_scan_timestamp",
							Instant.now().toString());
					result.add(world);

					logInfo("ComplianceAdapter collection complete: "
							+ totalHosts + " hosts evaluated");

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

	private void pushComplianceData(Resource hostRes,
			ControlEvaluator.ComplianceResult cr, String profileName) {
		String prefix = "VCF-CF Compliance|" + profileName;

		for (ControlEvaluator.ControlResult ctrl : cr.controlResults) {
			String ctrlPrefix = prefix + "|" + ctrl.scgId;
			addProperty(hostRes, ctrlPrefix + "|Actual", ctrl.actual);
			addProperty(hostRes, ctrlPrefix + "|Expected", ctrl.expected);
			hostRes.addData(ctrlPrefix + "|Compliant",
					ctrl.compliant ? 1.0 : 0.0);
			addProperty(hostRes, ctrlPrefix + "|Description", ctrl.description);
		}

		hostRes.addData("VCF-CF Compliance|score", cr.score);
		hostRes.addData("VCF-CF Compliance|pass_count", (double) cr.passCount);
		hostRes.addData("VCF-CF Compliance|fail_count", (double) cr.failCount);
		hostRes.addData("VCF-CF Compliance|total_count",
				(double) cr.totalCount);
		addProperty(hostRes, "VCF-CF Compliance|profile_name", profileName);
	}

	private Resource createResource(String kind, String name,
			String idKey, String idValue) {
		ResourceKey key = new ResourceKey(name, kind, ADAPTER_KIND);
		key.addIdentifier(new ResourceIdentifierConfig(idKey, idValue, true));
		return new Resource(key);
	}

	@Override
	public void onDiscard() {
		if (vcApi != null) {
			vcApi.logout();
		}
		super.onDiscard();
	}
}
