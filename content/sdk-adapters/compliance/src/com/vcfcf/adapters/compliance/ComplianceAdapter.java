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

	// Fix #2 (Task #17): track the profile that was active in the
	// PREVIOUS collection cycle. When the operator switches profiles
	// (e.g. VMware_SCG_8.0 -> VMware_SCG_9.0) the OLD profile's
	// per-control properties (VCF-CF Compliance|VMware_SCG_8.0|...)
	// linger on each resource until VCF Ops retention ages them out.
	// Detecting the change here lets us either:
	//   (a) emit a clear operator warning so the lingering keys aren't
	//       mistaken for the new profile's signal, and / or
	//   (b) push a NotExisting state on the OLD per-control properties
	//       so VCF Ops cleans them up immediately.
	// Path (b) is a TOOLSET GAP today — see the comment block in
	// detectProfileChange() for the API surface analysis. Path (a) is
	// always emitted on change.
	// In-memory only: a restart resets to null and we skip cleanup
	// on the first post-restart cycle (there is no signal that a
	// change occurred during the gap). Persisting to the work
	// directory would be a future enhancement; in-memory is the v1
	// contract called out in the Fix #2 brief.
	private volatile String previousProfileName;

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
						loadStitcherResources();
					}

					// Fix #2: detect profile change BEFORE the per-kind
					// collectors run so the warning lands in the same
					// cycle log as the (now obsolete) old-profile
					// properties — operator sees both signals together.
					// The actual NotExisting push is a TOOLSET GAP today;
					// see detectProfileChange() for the analysis.
					detectProfileChange(profile.name, confDir);

					// Phase 2: HostSystem (Phase 1, green path),
					// VirtualMachine, VMwareAdapter Instance,
					// VmwareDistributedVirtualSwitch, and
					// DistributedVirtualPortgroup. Each loop reads
					// resources from vSphere SOAP, evaluates its slice
					// of the profile, and pushes per-resource rollups
					// + per-control raw onto the matched Ops resource.
					HostStats hostStats = collectHosts(profile);
					VmStats vmStats = collectVms(profile);
					VCenterStats vcStats = collectVCenter(profile);
					DvsStats dvsStats = collectDvs(profile);
					DvpgStats dvpgStats = collectDvpg(profile);
					ClusterStats clusterStats = collectClusters(profile);

					Resource world = createResource("ComplianceWorld",
							"Compliance World",
							"world_id", "compliance_world");
					world.addData("Summary|total_hosts",
							(double) hostStats.total);
					// Skip avg_host_score and hosts_below_threshold entirely
					// when no host produced real data — publishing a sentinel
					// (0.0 or 100.0) is indistinguishable from a real result.
					// Operators will see the metric gap on the dashboard and
					// know to investigate. profile_name + total_hosts still
					// publish so they know the adapter ran.
					if (hostStats.scored > 0) {
						world.addData("Summary|avg_host_score",
								hostStats.scoreSum / hostStats.scored);
						world.addData("Summary|hosts_below_threshold",
								(double) hostStats.belowThreshold);
					} else {
						logWarn("No hosts produced real compliance signal "
								+ "(all totalCount==0); skipping "
								+ "Summary|avg_host_score and "
								+ "Summary|hosts_below_threshold so the "
								+ "scoreboard reads 'no data' rather than "
								+ "a sentinel value");
					}
					// VirtualMachine fleet rollups (Phase 2). Same
					// no-sentinel contract: only publish averages when
					// at least one VM produced real signal.
					world.addData("Summary|total_vms",
							(double) vmStats.total);
					if (vmStats.scored > 0) {
						world.addData("Summary|avg_vm_score",
								vmStats.scoreSum / vmStats.scored);
						world.addData("Summary|vms_below_threshold",
								(double) vmStats.belowThreshold);
					}
					// vCenter fleet rollups (Fix #1, world symmetry).
					// Same no-sentinel contract as host/vm: only publish
					// averages and below_threshold when at least one
					// vCenter produced real signal. total_vcenters always
					// publishes so operators see the adapter ran. Today
					// a ComplianceAdapter targets exactly one vCenter, so
					// total_vcenters will be 0 or 1, but emit them as
					// fleet stats anyway so the world contract is
					// uniform with hosts/vms (and a future multi-vCenter
					// posture won't have to retrofit the keys).
					world.addData("Summary|total_vcenters",
							(double) vcStats.total);
					if (vcStats.scored > 0) {
						world.addData("Summary|avg_vcenter_score",
								vcStats.scoreSum / vcStats.scored);
						world.addData("Summary|vcenters_below_threshold",
								(double) vcStats.belowThreshold);
					}
					addProperty(world, "Summary|profile_name",
							profile.name);
					addProperty(world, "Summary|last_scan_timestamp",
							Instant.now().toString());
					result.add(world);

					logInfo("ComplianceAdapter collection complete: "
							+ hostStats.total + " hosts, "
							+ vmStats.total + " VMs, "
							+ (vcStats.matched ? "1" : "0")
							+ " vCenter, "
							+ dvsStats.total + " DVS, "
							+ dvpgStats.total + " DVPG, "
							+ clusterStats.total + " ClusterComputeResource");

					// Fix #2: commit the current profile as "previous"
					// at end-of-cycle so the next cycle's
					// detectProfileChange() compares against what we
					// just finished publishing. Only update on the
					// success path — if collection threw earlier, the
					// catch below re-throws and we deliberately leave
					// previousProfileName unchanged so the next cycle
					// re-tries the detection.
					previousProfileName = profile.name;

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

	// ----- Phase 2 per-kind collectors --------------------------------
	//
	// Each collector follows the same shape:
	//   1. list resources from vSphere SOAP for that kind
	//   2. read the kind's advanced-setting source (per-host, vmx
	//      extraConfig, vCenter OptionManager)
	//   3. evaluate the matching slice of the profile via
	//      ControlEvaluator.evaluateControls
	//   4. push rollups + per-control raw onto the matched Ops resource
	//      via the stitcher
	//
	// Don't fold a per-resource score into world aggregates unless that
	// resource produced REAL signal (totalCount > 0). See the
	// zero-divisor-contract comment block in collectHosts for the
	// rationale — it's the same fix #1 sentinel concern Phase 1 found.

	private void loadStitcherResources() {
		try {
			stitcher.loadHostResources();
			logInfo("Stitcher loaded: " + stitcher.size() + " hosts");
		} catch (Exception e) {
			logError("Stitcher loadHostResources failed: "
					+ e.getClass().getName() + ": " + e.getMessage(), e);
		}
		try {
			stitcher.loadVmResources();
			logInfo("Stitcher loaded: "
					+ stitcher.countOfKind("VirtualMachine") + " VMs");
		} catch (Exception e) {
			logWarn("Stitcher loadVmResources failed: " + e.getMessage());
		}
		try {
			stitcher.loadVCenterAdapterInstance();
			logInfo("Stitcher loaded: "
					+ stitcher.countOfKind("VMwareAdapter Instance")
					+ " VMwareAdapter Instance(s)");
		} catch (Exception e) {
			logWarn("Stitcher loadVCenterAdapterInstance failed: "
					+ e.getMessage());
		}
		try {
			stitcher.loadDvsResources();
			logInfo("Stitcher loaded: "
					+ stitcher.countOfKind(
							"VmwareDistributedVirtualSwitch")
					+ " DVS");
		} catch (Exception e) {
			logWarn("Stitcher loadDvsResources failed: " + e.getMessage());
		}
		try {
			stitcher.loadDvpgResources();
			logInfo("Stitcher loaded: "
					+ stitcher.countOfKind("DistributedVirtualPortgroup")
					+ " DVPG");
		} catch (Exception e) {
			logWarn("Stitcher loadDvpgResources failed: " + e.getMessage());
		}
		try {
			stitcher.loadClusterResources();
			logInfo("Stitcher loaded: "
					+ stitcher.countOfKind("ClusterComputeResource")
					+ " ClusterComputeResource");
		} catch (Exception e) {
			logWarn("Stitcher loadClusterResources failed: "
					+ e.getMessage());
		}
	}

	/**
	 * Fix #2 (Task #17): on the first cycle after a profile switch,
	 * detect the change and emit a clear operator warning that the
	 * OLD profile's per-control properties (under namespace
	 * {@code VCF-CF Compliance|<old_profile>|...}) will linger on
	 * every stitched resource until VCF Ops retention ages them out.
	 *
	 * <p><b>TOOLSET GAP — cannot push state=NotExisting today.</b><br>
	 * The Fix #2 brief specifies pushing each old per-control property
	 * key with {@code state=NotExisting} so VCF Ops cleans them on the
	 * next retention pass. The public Suite API {@code PropertyContent}
	 * schema ({@code docs/operations-api.json}) defines only
	 * {@code statKey} / {@code timestamps} / {@code data} / {@code values}
	 * — there is no per-property state field. The {@code NOT_EXISTING}
	 * value in {@code resource-state} applies to whole resources, not
	 * to individual property keys. Without a property-level state
	 * field on the addProperties payload, there is no Suite API call
	 * that signals "this property no longer exists" without doing the
	 * invasive thing the brief forbids (Suite API DELETE on the
	 * property key).
	 *
	 * <p>Path forward: either teach the adapter SDK to flag stale keys
	 * via the property-collection contract (so the platform's stale-
	 * data sweep picks them up), or surface a Suite API endpoint that
	 * accepts a property-level state. Until then, this method:
	 * <ol>
	 *   <li>Detects the change.</li>
	 *   <li>Loads the OLD profile to enumerate the control keys that
	 *       are about to go stale (proof we COULD enumerate the
	 *       NotExisting set when the API gains the capability).</li>
	 *   <li>Logs a single operator-facing warning that lists the
	 *       affected namespace and resource count, so the lingering
	 *       keys aren't mistaken for new-profile signal during the
	 *       retention window.</li>
	 * </ol>
	 *
	 * <p>The previousProfileName update happens at end-of-cycle so
	 * this detect runs at most once per real change. If the OLD
	 * profile CSV cannot be loaded (e.g. it was a Custom profile
	 * whose custom_profile_path is no longer accessible), we log the
	 * warning anyway with the key set unknown rather than failing
	 * the cycle.
	 */
	private void detectProfileChange(String currentProfileName,
			String confDir) {
		if (previousProfileName == null) {
			// First cycle after install or restart — there is no
			// "previous" profile from which to clean up. Quietly
			// initialize the tracking state.
			return;
		}
		if (previousProfileName.equals(currentProfileName)) {
			// No change. Most cycles take this branch.
			return;
		}

		// Real change detected. Try to enumerate the old profile's
		// per-control keys so the warning is specific.
		java.util.List<String> oldControlKeys =
				enumerateOldProfileControlKeys(previousProfileName,
						confDir);

		int stitchedResources = stitcher == null ? 0
				: stitcher.countOfKind("HostSystem")
				+ stitcher.countOfKind("VirtualMachine")
				+ stitcher.countOfKind("VMwareAdapter Instance")
				+ stitcher.countOfKind("VmwareDistributedVirtualSwitch")
				+ stitcher.countOfKind("DistributedVirtualPortgroup");

		logWarn("Profile change detected: previous='"
				+ previousProfileName + "' current='"
				+ currentProfileName + "'. "
				+ oldControlKeys.size() + " per-control property key(s) "
				+ "under namespace 'VCF-CF Compliance|"
				+ previousProfileName + "|*' will linger on each of "
				+ stitchedResources + " stitched resource(s) until VCF "
				+ "Ops retention ages them out. TOOLSET GAP: the public "
				+ "Suite API PropertyContent schema has no per-property "
				+ "state field, so this adapter cannot signal "
				+ "state=NotExisting on the old keys to trigger an "
				+ "immediate cleanup. See detectProfileChange() in "
				+ "ComplianceAdapter for the API-surface analysis and "
				+ "path forward.");
	}

	/**
	 * Best-effort enumeration of the per-control property keys that
	 * the OLD profile pushed in its last cycle. Reads the canonical
	 * CSV for {@code oldProfileName} from the same conf path the live
	 * loader uses; returns an empty list when the OLD CSV can't be
	 * located (e.g. Custom profile whose source moved).
	 *
	 * <p>The returned list is the set of stat keys this adapter would
	 * mark as NotExisting if the Suite API supported per-property
	 * state — that capability is the TOOLSET GAP called out by
	 * {@link #detectProfileChange}.
	 */
	private java.util.List<String> enumerateOldProfileControlKeys(
			String oldProfileName, String confDir) {
		java.util.List<String> keys = new java.util.ArrayList<>();
		if (oldProfileName == null || oldProfileName.isEmpty()) {
			return keys;
		}
		if ("Custom".equalsIgnoreCase(oldProfileName)) {
			// We don't have the OLD custom_profile_path — only the
			// current config. Log and bail.
			logInfo("Skipping old-profile key enumeration: previous "
					+ "profile was 'Custom' and the old custom CSV path "
					+ "is not retained across config changes");
			return keys;
		}
		try {
			BenchmarkLoader tmpLoader = new BenchmarkLoader();
			BenchmarkProfile oldProfile = tmpLoader.load(oldProfileName,
					null, confDir);
			String prefix = "VCF-CF Compliance|" + oldProfile.name + "|";
			for (BenchmarkProfile.Control c : oldProfile.controls) {
				String ctrlPrefix = prefix + c.controlId;
				// Mirror the four leaves pushComplianceViaClient
				// emits per control: Actual / Expected / Description
				// (properties) and Compliant (stat).
				keys.add(ctrlPrefix + "|Actual");
				keys.add(ctrlPrefix + "|Expected");
				keys.add(ctrlPrefix + "|Description");
				keys.add(ctrlPrefix + "|Compliant");
			}
		} catch (RuntimeException e) {
			logWarn("Could not load old profile '" + oldProfileName
					+ "' to enumerate stale keys: " + e.getMessage()
					+ " — operator warning will list 0 keys");
		}
		return keys;
	}

	private HostStats collectHosts(BenchmarkProfile profile) throws Exception {
		HostStats stats = new HostStats();
		java.util.List<VSphereClient.HostInfo> hosts = vsphere.getHosts();
		if (hosts.isEmpty()) {
			logWarn("No hosts returned from vCenter SOAP");
			return stats;
		}
		logInfo("vSphere SOAP: " + hosts.size() + " hosts");

		java.util.List<BenchmarkProfile.Control> hostControls =
				profile.hostControls();

		for (VSphereClient.HostInfo hostInfo : hosts) {
			String hostId = hostInfo.moid;
			String hostName = hostInfo.name;

			logInfo("Evaluating host " + hostName + " (" + hostId + ")");

			java.util.Map<String, String> advSettings;
			try {
				advSettings = vsphere.getAdvancedSettings(hostInfo.moRef);
				logInfo("Host " + hostName + ": "
						+ advSettings.size() + " advanced settings");
			} catch (Exception e) {
				logWarn("Failed to read settings for "
						+ hostName + ": " + e.getMessage());
				advSettings = new java.util.HashMap<>();
			}

			ControlEvaluator.ComplianceResult cr =
					ControlEvaluator.evaluateControls(
							hostControls, advSettings, hostName);

			stats.total++;
			// Only fold a host into the world average if its
			// per-host score is REAL data (totalCount > 0).
			// ControlEvaluator returns score=100.0 as a
			// zero-divisor sentinel when no profile controls
			// were evaluable — folding that in produces a bogus
			// 100 average. Hosts with no signal are still counted
			// in total_hosts so operators see them, but they
			// don't move the score needle.
			if (cr.totalCount > 0) {
				stats.scored++;
				stats.scoreSum += cr.score;
				if (cr.score < 95.0) stats.belowThreshold++;
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
					pushComplianceViaClient(he.resourceId, cr,
							profile.name);
					logInfo("Pushed compliance data to " + hostName
							+ " (resource=" + he.resourceId + ")");
				}
			}
		}
		return stats;
	}

	private VmStats collectVms(BenchmarkProfile profile) {
		VmStats stats = new VmStats();
		java.util.List<VSphereClient.VmInfo> vms;
		try {
			vms = vsphere.getVms();
		} catch (Exception e) {
			logWarn("Failed to enumerate VMs: " + e.getMessage());
			return stats;
		}
		if (vms.isEmpty()) {
			logInfo("No VMs returned from vCenter SOAP");
			return stats;
		}
		logInfo("vSphere SOAP: " + vms.size() + " VMs");

		java.util.List<BenchmarkProfile.Control> vmControls =
				profile.vmControls();

		for (VSphereClient.VmInfo vm : vms) {
			java.util.Map<String, String> extra;
			try {
				extra = vsphere.getVmExtraConfig(vm.moRef);
			} catch (Exception e) {
				logWarn("Failed to read extraConfig for "
						+ vm.name + ": " + e.getMessage());
				extra = new java.util.HashMap<>();
			}

			ControlEvaluator.ComplianceResult cr =
					ControlEvaluator.evaluateControls(
							vmControls, extra, vm.name);

			stats.total++;
			if (cr.totalCount > 0) {
				stats.scored++;
				stats.scoreSum += cr.score;
				if (cr.score < 95.0) stats.belowThreshold++;
			}

			if (stitcher != null) {
				ComplianceStitcher.HostEntry he =
						stitcher.matchVm(vm.name, vm.moid);
				if (he != null) {
					pushComplianceViaClient(he.resourceId, cr,
							profile.name);
				}
			}
		}
		logInfo("VM compliance: " + stats.total + " VMs seen, "
				+ stats.scored + " with real signal");
		return stats;
	}

	private VCenterStats collectVCenter(BenchmarkProfile profile) {
		VCenterStats stats = new VCenterStats();
		java.util.Map<String, String> vcSettings;
		try {
			vcSettings = vsphere.getVCenterAdvancedSettings();
		} catch (Exception e) {
			logWarn("Failed to read vCenter advanced settings: "
					+ e.getMessage());
			return stats;
		}
		logInfo("vCenter advanced settings: " + vcSettings.size()
				+ " entries");

		java.util.List<BenchmarkProfile.Control> vcControls =
				profile.vCenterControls();
		String resourceName = config.vcenterHost;

		ControlEvaluator.ComplianceResult cr =
				ControlEvaluator.evaluateControls(
						vcControls, vcSettings, resourceName);
		logInfo("vCenter " + resourceName + ": score="
				+ String.format("%.1f", cr.score)
				+ "% (" + cr.passCount + " pass, "
				+ cr.failCount + " fail, "
				+ cr.totalCount + " total)");

		// Fix #1: fold this vCenter into the world aggregate using the
		// same totalCount>0 contract as host/vm — sentinel scores
		// (score=100 from a zero-divisor) must not pollute the fleet
		// average. total counts every vCenter the adapter evaluated;
		// scored / scoreSum / belowThreshold gate on real signal.
		stats.total++;
		if (cr.totalCount > 0) {
			stats.scored++;
			stats.scoreSum += cr.score;
			if (cr.score < 95.0) stats.belowThreshold++;
		}

		if (stitcher != null) {
			// VMwareAdapter Instance has no vim25 MoRef — the matcher
			// resolves it by either the configured vCenter FQDN
			// (against the VCURL identifier) or the vCenter Instance
			// UUID (against VMEntityVCID). Pull the instance UUID from
			// the live SOAP session so the lookup is FQDN-rename safe.
			String vcInstanceUuid = null;
			try {
				vcInstanceUuid = vsphere.getVCenterInstanceUuid();
			} catch (Exception e) {
				logWarn("Could not read vCenter instance UUID for "
						+ "stitcher lookup: " + e.getMessage()
						+ " — will rely on hostname match only");
			}
			ComplianceStitcher.HostEntry he =
					stitcher.matchVCenterAdapterInstance(
							resourceName, vcInstanceUuid);
			if (he != null) {
				pushComplianceViaClient(he.resourceId, cr, profile.name);
				stats.matched = true;
				logInfo("Pushed vCenter compliance data to "
						+ he.hostName + " (resource=" + he.resourceId
						+ ", VCURL=" + he.moid
						+ ", vcInstanceUuid=" + vcInstanceUuid + ")");
			} else {
				logWarn("Could not resolve VMwareAdapter Instance for "
						+ resourceName + " (vcInstanceUuid="
						+ vcInstanceUuid + ") — vCenter compliance "
						+ "rollups will NOT appear");
			}
		}
		return stats;
	}

	private DvsStats collectDvs(BenchmarkProfile profile) {
		DvsStats stats = new DvsStats();

		// Phase 3 / Batch 3b — DVS controls are now partially evaluable.
		// SCG 9.0 emits 3 vim_property security-policy controls per DVS
		// (securityPolicy.{forgedTransmits,macChanges,allowPromiscuous})
		// backed by VSphereClient.getDvsSecurityPolicy + the
		// ControlEvaluator.evaluateVimProperties dispatcher. Remaining
		// DVS controls (network-reset-port, network-restrict-discovery-
		// protocol, network-restrict-port-mirroring, etc.) stay
		// powercli_only / manual_audit and are skipped by the
		// evaluator. When no controls evaluate (e.g. a profile that
		// only ships powercli rows for DVS), we still walk DVS
		// inventory and push profile_name so the resource appears
		// under VCF-CF Compliance in the metric browser.
		java.util.List<VSphereClient.DvsInfo> switches;
		try {
			switches = vsphere.getDvSwitches();
		} catch (Exception e) {
			logWarn("Failed to enumerate DVS: " + e.getMessage());
			return stats;
		}
		if (switches.isEmpty()) {
			logInfo("No DVS returned from vCenter SOAP");
			return stats;
		}
		logInfo("vSphere SOAP: " + switches.size() + " DVS");

		java.util.List<BenchmarkProfile.Control> dvsControls =
				profile.dvsControls();
		int evaluableCount = countEvaluable(dvsControls, "vim_property");

		for (VSphereClient.DvsInfo dvs : switches) {
			stats.total++;

			if (stitcher == null) continue;
			ComplianceStitcher.HostEntry he =
					stitcher.matchDvs(dvs.name, dvs.moid);
			if (he == null) continue;

			if (evaluableCount == 0) {
				// No vim_property controls in this profile slice —
				// keep the v30 profile-name-only push so the resource
				// still appears under VCF-CF Compliance without
				// polluting per-resource rollups with a sentinel
				// score=100.
				logInfo("DVS " + dvs.name + " (" + dvs.moid
						+ ") matched -> resource=" + he.resourceId
						+ "; no evaluable controls, pushing profile_name");
				pushProfileNamePropertyOnly(he.resourceId,
						profile.name);
				continue;
			}

			java.util.Map<String, Object> secPol;
			try {
				java.util.Map<String, Boolean> raw =
						vsphere.getDvsSecurityPolicy(dvs.moRef);
				secPol = qualifySecurityPolicy(raw);
			} catch (Exception e) {
				logWarn("Failed to read security policy for DVS "
						+ dvs.name + ": " + e.getMessage());
				// Fall back to profile_name-only on read failure so
				// the resource still surfaces and the operator log
				// has the failure breadcrumb. Don't push sentinels.
				pushProfileNamePropertyOnly(he.resourceId,
						profile.name);
				continue;
			}

			ControlEvaluator.ComplianceResult cr =
					ControlEvaluator.evaluateVimProperties(
							dvsControls, secPol, dvs.name);

			logInfo("DVS " + dvs.name + " (" + dvs.moid
					+ ") matched -> resource=" + he.resourceId
					+ "; score=" + String.format("%.1f", cr.score)
					+ "% (" + cr.passCount + " pass, "
					+ cr.failCount + " fail, "
					+ cr.totalCount + " total)");

			if (cr.totalCount > 0) {
				pushComplianceViaClient(he.resourceId, cr, profile.name);
			} else {
				// totalCount=0 means the read happened but the profile
				// slice scored nothing (e.g. all expected_values were
				// unparseable). Treat as no-signal — profile_name only.
				pushProfileNamePropertyOnly(he.resourceId,
						profile.name);
			}
		}
		return stats;
	}

	private DvpgStats collectDvpg(BenchmarkProfile profile) {
		DvpgStats stats = new DvpgStats();

		// Phase 3 / Batch 3b — DVPG controls are now partially
		// evaluable in the same way as DVS. SCG 9.0 emits 3
		// vim_property security-policy controls per DVPG with the
		// same canonical parameter keys as DVS; the read path is
		// VSphereClient.getDvpgSecurityPolicy and the dispatcher is
		// shared with DVS via ControlEvaluator.evaluateVimProperties.
		java.util.List<VSphereClient.DvpgInfo> pgs;
		try {
			pgs = vsphere.getDvPortgroups();
		} catch (Exception e) {
			logWarn("Failed to enumerate DVPG: " + e.getMessage());
			return stats;
		}
		if (pgs.isEmpty()) {
			logInfo("No DVPG returned from vCenter SOAP");
			return stats;
		}
		logInfo("vSphere SOAP: " + pgs.size() + " DVPG");

		java.util.List<BenchmarkProfile.Control> dvpgControls =
				profile.dvpgControls();
		int evaluableCount = countEvaluable(dvpgControls, "vim_property");

		for (VSphereClient.DvpgInfo pg : pgs) {
			stats.total++;

			if (stitcher == null) continue;
			ComplianceStitcher.HostEntry he =
					stitcher.matchDvpg(pg.name, pg.moid);
			if (he == null) continue;

			if (evaluableCount == 0) {
				logInfo("DVPG " + pg.name + " (" + pg.moid
						+ ") matched -> resource=" + he.resourceId
						+ "; no evaluable controls, pushing profile_name");
				pushProfileNamePropertyOnly(he.resourceId,
						profile.name);
				continue;
			}

			java.util.Map<String, Object> secPol;
			try {
				java.util.Map<String, Boolean> raw =
						vsphere.getDvpgSecurityPolicy(pg.moRef);
				secPol = qualifySecurityPolicy(raw);
			} catch (Exception e) {
				logWarn("Failed to read security policy for DVPG "
						+ pg.name + ": " + e.getMessage());
				pushProfileNamePropertyOnly(he.resourceId,
						profile.name);
				continue;
			}

			ControlEvaluator.ComplianceResult cr =
					ControlEvaluator.evaluateVimProperties(
							dvpgControls, secPol, pg.name);

			logInfo("DVPG " + pg.name + " (" + pg.moid
					+ ") matched -> resource=" + he.resourceId
					+ "; score=" + String.format("%.1f", cr.score)
					+ "% (" + cr.passCount + " pass, "
					+ cr.failCount + " fail, "
					+ cr.totalCount + " total)");

			if (cr.totalCount > 0) {
				pushComplianceViaClient(he.resourceId, cr, profile.name);
			} else {
				pushProfileNamePropertyOnly(he.resourceId,
						profile.name);
			}
		}
		return stats;
	}

	/**
	 * Phase 3 — ClusterComputeResource (vSAN) collector. Walks every
	 * cluster in inventory, reads the small slice of vSAN configuration
	 * the bundled vim25 jar exposes
	 * ({@link VSphereClient#getClusterVsanConfig}), and evaluates the
	 * cluster-level vim_property controls. Identical shape to
	 * {@link #collectDvs} and {@link #collectDvpg}.
	 *
	 * <p>TOOLSET GAP — the bulk of SCG's ClusterComputeResource controls
	 * (vSAN data-at-rest encryption, data-in-transit encryption, iSCSI
	 * mutual CHAP, File Services NFS/SMB, network isolation, operations
	 * reserve, automatic rebalance, auto-policy-management, vSAN Max
	 * isolation) live on the vSAN Management SDK
	 * ({@code com.vmware.vim.vsan.binding}) which is NOT on this
	 * adapter's classpath. Those controls remain
	 * {@code parameter_kind=manual_audit} in the canonical CSV and are
	 * skipped by {@link ControlEvaluator#evaluateVimProperties}. The
	 * controls that DO land via plain vim25 today are
	 * {@code cluster.managed-disk-claim}
	 * ({@code vsanConfig.autoClaimStorage}) and
	 * {@code cluster.object-checksum}
	 * ({@code vsanConfig.objectChecksumEnabled}). Clusters with no vSAN
	 * surface an empty config map and get the profile-name-only push so
	 * they still appear under VCF-CF Compliance in the metric browser.
	 */
	private ClusterStats collectClusters(BenchmarkProfile profile) {
		ClusterStats stats = new ClusterStats();

		java.util.List<VSphereClient.ClusterInfo> clusters;
		try {
			clusters = vsphere.getClusters();
		} catch (Exception e) {
			logWarn("Failed to enumerate ClusterComputeResource: "
					+ e.getMessage());
			return stats;
		}
		if (clusters.isEmpty()) {
			logInfo("No ClusterComputeResource returned from vCenter SOAP");
			return stats;
		}
		logInfo("vSphere SOAP: " + clusters.size()
				+ " ClusterComputeResource");

		java.util.List<BenchmarkProfile.Control> clusterControls =
				profile.clusterControls();
		int evaluableCount = countEvaluable(clusterControls, "vim_property");

		for (VSphereClient.ClusterInfo cluster : clusters) {
			stats.total++;

			if (stitcher == null) continue;
			ComplianceStitcher.HostEntry he =
					stitcher.matchCluster(cluster.name, cluster.moid);
			if (he == null) continue;

			if (evaluableCount == 0) {
				logInfo("Cluster " + cluster.name + " (" + cluster.moid
						+ ") matched -> resource=" + he.resourceId
						+ "; no evaluable controls, pushing profile_name");
				pushProfileNamePropertyOnly(he.resourceId,
						profile.name);
				continue;
			}

			java.util.Map<String, Object> vsanCfg;
			try {
				vsanCfg = vsphere.getClusterVsanConfig(cluster.moRef);
			} catch (Exception e) {
				logWarn("Failed to read vSAN config for cluster "
						+ cluster.name + ": " + e.getMessage());
				pushProfileNamePropertyOnly(he.resourceId,
						profile.name);
				continue;
			}

			if (vsanCfg.isEmpty()) {
				// No vSAN on this cluster — empty config map. Push
				// profile_name only so the cluster still appears in the
				// metric browser without polluting per-resource rollups
				// with a sentinel score=100.
				logInfo("Cluster " + cluster.name + " (" + cluster.moid
						+ ") has no vsanConfigInfo (non-vSAN cluster), "
						+ "pushing profile_name only");
				pushProfileNamePropertyOnly(he.resourceId,
						profile.name);
				continue;
			}

			ControlEvaluator.ComplianceResult cr =
					ControlEvaluator.evaluateVimProperties(
							clusterControls, vsanCfg, cluster.name);

			logInfo("Cluster " + cluster.name + " (" + cluster.moid
					+ ") matched -> resource=" + he.resourceId
					+ "; score=" + String.format("%.1f", cr.score)
					+ "% (" + cr.passCount + " pass, "
					+ cr.failCount + " fail, "
					+ cr.totalCount + " total)");

			if (cr.totalCount > 0) {
				pushComplianceViaClient(he.resourceId, cr, profile.name);
			} else {
				pushProfileNamePropertyOnly(he.resourceId,
						profile.name);
			}
		}
		return stats;
	}

	/**
	 * Translate the bare-field-name map returned by
	 * {@link VSphereClient#getDvsSecurityPolicy(com.vmware.vim25.ManagedObjectReference)}
	 * / {@link VSphereClient#getDvpgSecurityPolicy(com.vmware.vim25.ManagedObjectReference)}
	 * ({@code allowPromiscuous}, {@code macChanges},
	 * {@code forgedTransmits}) into the fully-qualified canonical
	 * parameter keys the evaluator looks up
	 * ({@code securityPolicy.allowPromiscuous} etc.). Keeping the
	 * vSphere client's contract bare and qualifying here keeps the
	 * client unaware of the canonical schema.
	 */
	private static java.util.Map<String, Object> qualifySecurityPolicy(
			java.util.Map<String, Boolean> raw) {
		java.util.Map<String, Object> qualified =
				new java.util.HashMap<>();
		if (raw == null) return qualified;
		for (java.util.Map.Entry<String, Boolean> e : raw.entrySet()) {
			qualified.put("securityPolicy." + e.getKey(), e.getValue());
		}
		return qualified;
	}

	/**
	 * Count controls in {@code slice} whose parameter_kind matches
	 * {@code kind}. Used by collectDvs / collectDvpg to decide
	 * whether to take the full evaluation path or fall back to the
	 * profile-name-only push.
	 */
	private static int countEvaluable(
			java.util.List<BenchmarkProfile.Control> slice, String kind) {
		int n = 0;
		for (BenchmarkProfile.Control c : slice) {
			if (kind.equals(c.parameterKind)) n++;
		}
		return n;
	}

	/**
	 * Push ONLY the profile_name property onto a resource — no per-
	 * control raw, no first-class rollup stats. Used for DVS / DVPG
	 * which the adapter enumerates but cannot evaluate yet (all
	 * controls are powercli_only). Calling the full
	 * {@link #pushComplianceViaClient} would emit
	 * {@code VCF-CF Compliance|score = 100.0} as a zero-divisor
	 * sentinel onto the resource, which dashboards then average into
	 * a misleading fleet score. Stripping back to the property alone
	 * keeps the resource visible in the metric browser without
	 * publishing fake compliance data.
	 *
	 * <p>Fix #3: previous code path called pushComplianceViaClient and
	 * relied on the empty control list to suppress per-control
	 * properties — but it still pushed the score=100 stat and the
	 * three count=0 stats. v27 verification reported no
	 * {@code profile_name} on DVS/DVPG, so this path also emits an
	 * explicit log line per push so the operator log distinguishes
	 * match-failure (warned by the stitcher) from push-failure.
	 */
	private void pushProfileNamePropertyOnly(String resourceId,
			String profileName) {
		long ts = System.currentTimeMillis();
		java.util.LinkedHashMap<String, String> props =
				new java.util.LinkedHashMap<>();
		props.put("VCF-CF Compliance|profile_name", profileName);
		stitcher.pushProperties(resourceId, props, ts);
		logInfo("Pushed profile_name='" + profileName
				+ "' to resource=" + resourceId);
	}

	private static final class HostStats {
		int total;
		int scored;
		double scoreSum;
		int belowThreshold;
	}

	private static final class VmStats {
		int total;
		int scored;
		double scoreSum;
		int belowThreshold;
	}

	private static final class VCenterStats {
		// matched stays for backward compatibility with the collection-
		// complete log line. Fix #1 adds the same (total, scored,
		// scoreSum, belowThreshold) fleet stats hosts and VMs publish,
		// so the world aggregate emits total_vcenters / avg_vcenter_score
		// / vcenters_below_threshold under the same no-sentinel contract.
		boolean matched;
		int total;
		int scored;
		double scoreSum;
		int belowThreshold;
	}

	private static final class DvsStats {
		int total;
	}

	private static final class DvpgStats {
		int total;
	}

	private static final class ClusterStats {
		int total;
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
