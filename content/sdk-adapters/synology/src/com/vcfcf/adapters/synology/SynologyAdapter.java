package com.vcfcf.adapters.synology;

import com.vcfcf.adapter.VcfCfAdapter;
import com.vcfcf.adapter.http.HttpClientBuilder;
import com.vcfcf.adapter.json.SimpleJson;
import com.vcfcf.adapter.retry.RetryPolicy;
import com.vcfcf.adapter.stitch.ForeignResourceResolver;

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

import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class SynologyAdapter extends VcfCfAdapter<SynologyConfig> {

	private static final String ADAPTER_KIND = "synology_diskstation";

	private volatile SynologyApiClient api;
	private volatile ForeignResourceResolver datastoreResolver;

	public SynologyAdapter() {
		super();
	}

	public SynologyAdapter(String adapterDir, Integer adapterInstanceId) {
		super(adapterDir, adapterInstanceId);
	}

	@Override
	protected String getAdapterDirectory() {
		return ADAPTER_KIND;
	}

	@Override
	public void configure(ResourceStatus status, ResourceConfig resourceConfig) {
		String host = getIdentifier(resourceConfig, "host");
		String port = getIdentifier(resourceConfig, "port");
		String allowInsecure = getIdentifier(resourceConfig, "allowInsecure");
		String username = getCredentialField(resourceConfig, "username");
		String password = getCredentialField(resourceConfig, "password");

		this.config = new SynologyConfig(host, port, username, password, allowInsecure);

		this.httpClient = HttpClientBuilder.builder()
				.baseUrl(config.baseUrl())
				.allowInsecure(config.allowInsecure)
				.retryPolicy(RetryPolicy.builder()
						.maxAttempts(3)
						.baseDelayMs(1000)
						.build())
				.timeout(Duration.ofSeconds(30))
				.build();

		this.api = new SynologyApiClient(httpClient, config.username, config.password);

		if (this.suiteAPIClient != null) {
			this.datastoreResolver = new ForeignResourceResolver(this.suiteAPIClient, this.logger);
		}

		logInfo("SynologyAdapter configured: host=" + config.host + " port=" + config.port);
	}

	@Override
	public Tester getTester(ResourceStatus status, ResourceConfig resourceConfig) {
		return (TestParam param) -> {
			try {
				api.login();
				SimpleJson info = api.dsmInfo();
				String model = info.data().get("model").asString("unknown");
				logInfo("Test OK: connected to " + model);
			} catch (Exception e) {
				throw new TestException("Connection test failed: " + e.getMessage(), e);
			}
		};
	}

	@Override
	public Discoverer getDiscoverer(ResourceStatus status, ResourceConfig resourceConfig) {
		return (DiscoveryParam param) -> {
			logInfo("SynologyAdapter discover: starting resource enumeration");
			ResourceCollection collection = new ResourceCollection();

			try {
				api.ensureSession();

				// --- Global World singleton (shared across all adapter instances) ---
				Resource world = createResource("SynologyWorld", "Synology World",
						"world_id", "synology_world");
				collection.add(world);

				// --- Diskstation singleton ---
				SimpleJson dsmInfo = api.dsmInfo();
				String serial = dsmInfo.data().get("serial").asString("unknown");
				String model = dsmInfo.data().get("model").asString("");
				String dsName = model.isEmpty() ? serial : model + " " + serial;
				Resource diskstation = createResource("SynologyDiskstation", dsName, "serial", serial);
				collection.add(diskstation);

				// --- Storage topology (one call returns pools, volumes, disks) ---
				SimpleJson storage = api.storageLoadInfo();

				for (SimpleJson pool : storage.data().get("storagePools").asList()) {
					String poolId = pool.get("id").asString();
					String poolName = poolDisplayName(pool);
					Resource r = createResource("SynologyStoragePool", poolName, "pool_id", poolId);
					collection.add(r);
				}

				for (SimpleJson vol : storage.data().get("volumes").asList()) {
					String volPath = vol.get("vol_path").asString();
					String volId = vol.get("volume_id").asString(volPath);
					String volName = volumeDisplayName(vol);
					Resource r = createResource("SynologyVolume", volName, "volume_id", volId);
					collection.add(r);
				}

				for (SimpleJson disk : storage.data().get("disks").asList()) {
					String diskId = disk.get("id").asString();
					String diskName = disk.get("name").asString(diskId);
					Resource r = createResource("SynologyDisk", diskName, "disk_id", diskId);
					collection.add(r);
				}

				// --- SSD Caches ---
				SimpleJson ssdCaches = storage.data().get("ssdCaches");
				if (!ssdCaches.isNull()) {
					for (SimpleJson cache : ssdCaches.asList()) {
						String cacheId = cache.get("id").asString();
						String cacheName = cacheDisplayName(cache, storage);
						Resource r = createResource("SynologySsdCache", cacheName, "cache_id", cacheId);
						collection.add(r);
					}
				}

				// --- iSCSI LUNs ---
				SimpleJson luns = api.iscsiLunList();
				for (SimpleJson lun : luns.data().get("luns").asList()) {
					String uuid = lun.get("uuid").asString();
					String lunName = lun.get("name").asString(uuid);
					Resource r = createResource("SynologyIscsiLun", lunName, "lun_uuid", uuid);
					collection.add(r);
				}

				// --- NFS Exports (shares with NFS rules) ---
				SimpleJson shares = api.shareList();
				for (SimpleJson share : shares.data().get("shares").asList()) {
					String name = share.get("name").asString();
					try {
						SimpleJson rules = api.nfsSharePrivilege(name);
						if (rules.data().get("rule").size() > 0) {
							Resource r = createResource("SynologyNfsExport", name, "share_name", name);
							collection.add(r);
						}
					} catch (Exception e) {
						logWarn("Failed to check NFS rules for share " + name + ": " + e.getMessage());
					}
				}

				// --- UPS ---
				try {
					SimpleJson ups = api.upsGet();
					boolean connected = ups.data().get("usb_ups_connect").asBoolean();
					if (connected) {
						String upsModel = ups.data().get("model").asString("UPS");
						Resource r = createResource("SynologyUps", upsModel, "ups_model", upsModel);
						collection.add(r);
					}
				} catch (Exception e) {
					logInfo("UPS not available: " + e.getMessage());
				}

				logInfo("SynologyAdapter discover: resource enumeration complete");
			} catch (Exception e) {
				logError("Discovery failed", e);
			}

			return collection;
		};
	}

	@Override
	public LiveCollector getLiveDataCollector(ResourceStatus status, ResourceConfig resourceConfig) {
		return new LiveCollector() {
			@Override
			public ResourceCollection getCurrentMetrics(ResourceConfig rc,
					ResourceCollection acc)
					throws CollectionException, InterruptedException {
				ResourceCollection result = new ResourceCollection();
				try {
					api.ensureSession();
					collectWorld(result);
					collectDiskstation(result);
					SimpleJson storage = collectStorageTopology(result);
					collectSsdCache(result, storage);
					collectIscsiLuns(result);
					collectNfsExports(result);
					collectUps(result);
				} catch (Exception e) {
					logError("Collection failed", e);
					throw new CollectionException("Synology collection failed: " + e.getMessage(), e);
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
				ResourceCollection rel = new ResourceCollection();
				try {
					api.ensureSession();
					buildRelationships(rel);
				} catch (Exception e) {
					logWarn("Relationship build failed: " + e.getMessage());
				}
				return rel;
			}

			@Override
			public boolean shouldForceUpdateRelationships() {
				return true;
			}
		};
	}

	// -----------------------------------------------------------------------
	// Collection: Diskstation
	// -----------------------------------------------------------------------

	private void collectDiskstation(ResourceCollection result) throws Exception {
		SimpleJson dsmInfo = api.dsmInfo();
		SimpleJson sysInfo = api.systemInfo();
		SimpleJson util = api.utilization();
		SimpleJson fan = api.fanSpeed();
		SimpleJson nfs = api.nfsServiceGet();

		String serial = dsmInfo.data().get("serial").asString("unknown");
		String dsModel = dsmInfo.data().get("model").asString("");
		String dsName = dsModel.isEmpty() ? serial : dsModel + " " + serial;
		Resource ds = findOrCreate(result, "SynologyDiskstation", dsName, "serial", serial);

		// System properties
		addProperty(ds, "System|model", dsmInfo.data().get("model").asString(""));
		addProperty(ds, "System|hostname", sysInfo.data().get("sys_name").asString(""));
		addProperty(ds, "System|firmware_version", sysInfo.data().get("firmware_ver").asString(""));
		addProperty(ds, "System|firmware_date", sysInfo.data().get("firmware_date").asString(""));

		// System metrics
		ds.addData("System|system_temp", dsmInfo.data().get("temperature").asDouble());
		ds.addData("System|uptime", (double) dsmInfo.data().get("uptime").asLong());

		// CPU metrics
		SimpleJson cpu = util.data().get("cpu");
		ds.addData("CPU|cpu_load_1m", cpu.get("1min_load").asDouble());
		ds.addData("CPU|cpu_load_5m", cpu.get("5min_load").asDouble());
		ds.addData("CPU|cpu_load_15m", cpu.get("15min_load").asDouble());
		ds.addData("CPU|cpu_user_pct", cpu.get("user_load").asDouble());
		ds.addData("CPU|cpu_system_pct", cpu.get("system_load").asDouble());
		ds.addData("CPU|cpu_total_load", cpu.get("user_load").asDouble() + cpu.get("system_load").asDouble());

		// Memory metrics
		SimpleJson mem = util.data().get("memory");
		ds.addData("Memory|memory_available", mem.get("avail_real").asDouble());
		ds.addData("Memory|memory_total", mem.get("total_real").asDouble());
		ds.addData("Memory|memory_usage_pct", mem.get("real_usage").asDouble());
		ds.addData("Memory|memory_cached", mem.get("cached").asDouble());
		ds.addData("Memory|swap_usage", mem.get("total_swap").asDouble() - mem.get("avail_swap").asDouble());
		ds.addData("Memory|swap_total", mem.get("total_swap").asDouble());

		// Network metrics (sum across all NICs)
		double rxTotal = 0, txTotal = 0;
		for (SimpleJson nic : util.data().get("network").asList()) {
			rxTotal += nic.get("rx").asDouble();
			txTotal += nic.get("tx").asDouble();
		}
		ds.addData("Network|net_rx_bytes", rxTotal);
		ds.addData("Network|net_tx_bytes", txTotal);

		// NIC count
		SimpleJson nics = api.networkInterfaceList();
		ds.addData("Network|nic_count", (double) nics.data().size());

		// Fan
		addProperty(ds, "Fan|fan_status", fan.data().get("cool_fan").asString("unknown"));
		addProperty(ds, "Fan|fan_speed_mode", fan.data().get("dual_fan_speed").asString("unknown"));

		// NFS service
		addProperty(ds, "NFS|nfs_enabled", nfs.data().get("enable_nfs").asBoolean() ? "true" : "false");
		addProperty(ds, "NFS|nfs_v4_enabled", nfs.data().get("enable_nfs_v4").asBoolean() ? "true" : "false");

		SimpleJson nfsUtil = util.data().get("nfs");
		if (!nfsUtil.isNull() && nfsUtil.size() > 0) {
			SimpleJson nfsRow = nfsUtil.get(0);
			ds.addData("NFS|nfs_total_ops", nfsRow.get("total_OPS").asDouble());
			ds.addData("NFS|nfs_read_ops", nfsRow.get("read_OPS").asDouble());
			ds.addData("NFS|nfs_write_ops", nfsRow.get("write_OPS").asDouble());
			ds.addData("NFS|nfs_max_latency", nfsRow.get("total_max_latency").asDouble());
		}

		// NFS client count (from CurrentConnection)
		SimpleJson conns = api.currentConnections();
		int nfsClients = 0;
		int nfsExportCount = 0;
		for (SimpleJson conn : conns.data().get("items").asList()) {
			if ("NFS".equals(conn.get("protocol").asString())) {
				nfsClients++;
			}
		}
		ds.addData("NFS|nfs_client_count", (double) nfsClients);

		result.add(ds);
	}

	// -----------------------------------------------------------------------
	// Collection: Storage Pools, Volumes, Disks (with IO join)
	// -----------------------------------------------------------------------

	private SimpleJson collectStorageTopology(ResourceCollection result) throws Exception {
		SimpleJson storage = api.storageLoadInfo();
		SimpleJson util = api.utilization();

		// Build IO lookup maps from Utilization response
		// Disk IO: keyed by disk device name (e.g., "sda")
		Map<String, SimpleJson> diskIoByDevice = new HashMap<>();
		SimpleJson diskUtil = util.data().get("disk");
		if (!diskUtil.isNull()) {
			for (SimpleJson d : diskUtil.get("disk").asList()) {
				diskIoByDevice.put(d.get("device").asString(), d);
			}
		}

		// Volume IO: keyed by display_name (e.g., "volume1")
		Map<String, SimpleJson> volIoByName = new HashMap<>();
		SimpleJson spaceUtil = util.data().get("space");
		if (!spaceUtil.isNull()) {
			for (SimpleJson v : spaceUtil.get("volume").asList()) {
				volIoByName.put(v.get("display_name").asString(), v);
			}
		}

		// --- Storage Pools ---
		for (SimpleJson pool : storage.data().get("storagePools").asList()) {
			String poolId = pool.get("id").asString();
			String poolName = poolDisplayName(pool);
			Resource r = findOrCreate(result, "SynologyStoragePool", poolName, "pool_id", poolId);

			SimpleJson size = pool.get("size");
			double total = size.get("total").asDouble();
			double used = size.get("used").asDouble();
			r.addData("Capacity|total_bytes", total);
			r.addData("Capacity|used_bytes", used);
			r.addData("Capacity|usage_pct", total > 0 ? (used / total) * 100.0 : 0.0);

			addProperty(r, "Configuration|raid_type", pool.get("raidType").asString(""));
			addProperty(r, "Configuration|status", pool.get("status").asString(""));
			addProperty(r, "Configuration|pool_path", pool.get("pool_path").asString(""));
			addProperty(r, "Configuration|device_type", pool.get("device_type").asString(""));

			SimpleJson disks = pool.get("disks");
			r.addData("Configuration|disk_count", (double) (disks.isNull() ? 0 : disks.size()));

			result.add(r);
		}

		// --- Volumes ---
		for (SimpleJson vol : storage.data().get("volumes").asList()) {
			String volPath = vol.get("vol_path").asString();
			String volId = vol.get("volume_id").asString(volPath);
			String volName = volumeDisplayName(vol);
			Resource r = findOrCreate(result, "SynologyVolume", volName, "volume_id", volId);

			SimpleJson size = vol.get("size");
			double total = size.get("total").asDouble();
			double free = size.get("free").asDouble();
			r.addData("Capacity|total_bytes", total);
			r.addData("Capacity|free_bytes", free);
			r.addData("Capacity|usage_pct", total > 0 ? ((total - free) / total) * 100.0 : 0.0);

			addProperty(r, "Configuration|volume_path", volPath);
			addProperty(r, "Configuration|fs_type", vol.get("fs_type").asString(""));
			addProperty(r, "Configuration|status", vol.get("status").asString(""));
			addProperty(r, "Configuration|description", vol.get("deploy_path").asString(""));

			// JOIN: Volume IO from Utilization (keyed by vol_path stripped of leading /)
			String volIoKey = volPath.startsWith("/") ? volPath.substring(1) : volPath;
			SimpleJson io = volIoByName.get(volIoKey);
			if (io != null) {
				r.addData("IO|read_bytes", io.get("read_byte").asDouble());
				r.addData("IO|write_bytes", io.get("write_byte").asDouble());
				r.addData("IO|read_iops", io.get("read_access").asDouble());
				r.addData("IO|write_iops", io.get("write_access").asDouble());
				r.addData("IO|utilization_pct", io.get("utilization").asDouble());
			}

			// JOIN: Cache hit rates on Volume (from ssdCaches[] matched by path == vol_path)
			SimpleJson ssdCaches = storage.data().get("ssdCaches");
			if (!ssdCaches.isNull()) {
				for (SimpleJson cache : ssdCaches.asList()) {
					String mountPath = cache.get("path").asString("");
					if (volPath.equals(mountPath)) {
						addProperty(r, "Cache|cache_enabled", "true");
						addProperty(r, "Cache|cache_status", cache.get("status").asString(""));
						r.addData("Cache|cache_read_hit_rate", cache.get("hit_rate").asDouble());
						r.addData("Cache|cache_write_hit_rate", cache.get("hit_rate_write").asDouble());
						break;
					}
				}
			}

			result.add(r);
		}

		// --- Disks ---
		for (SimpleJson disk : storage.data().get("disks").asList()) {
			String diskId = disk.get("id").asString();
			String diskName = disk.get("name").asString(diskId);
			Resource r = findOrCreate(result, "SynologyDisk", diskName, "disk_id", diskId);

			addProperty(r, "Hardware|display_name", diskName);
			addProperty(r, "Hardware|model", disk.get("model").asString(""));
			addProperty(r, "Hardware|firmware", disk.get("firm").asString(""));
			addProperty(r, "Hardware|serial", disk.get("serial").asString(""));
			addProperty(r, "Hardware|vendor", disk.get("vendor").asString(""));
			addProperty(r, "Hardware|disk_type", disk.get("diskType").asString(""));
			addProperty(r, "Hardware|disk_code", disk.get("disk_code").asString(""));
			addProperty(r, "Hardware|is_ssd", disk.get("isSsd").asBoolean() ? "true" : "false");
			addProperty(r, "Hardware|slot_id", disk.get("slot_id").asString(""));
			addProperty(r, "Hardware|size_bytes", disk.get("size_total").asString("0"));

			r.addData("Health|temperature", disk.get("temp").asDouble());
			addProperty(r, "Health|smart_status", disk.get("smart_status").asString(""));
			r.addData("Health|unc_sectors", disk.get("unc").asDouble());
			r.addData("Health|remain_life", disk.get("remain_life").asDouble());

			// JOIN: Disk IO from Utilization (keyed by device name, e.g., "sda")
			String device = disk.get("device").asString("");
			if (device.startsWith("/dev/")) device = device.substring(5);
			SimpleJson io = diskIoByDevice.get(device);
			if (io != null) {
				r.addData("IO|read_bytes", io.get("read_byte").asDouble());
				r.addData("IO|write_bytes", io.get("write_byte").asDouble());
				r.addData("IO|read_iops", io.get("read_access").asDouble());
				r.addData("IO|write_iops", io.get("write_access").asDouble());
				r.addData("IO|utilization_pct", io.get("utilization").asDouble());
			}

			result.add(r);
		}

		return storage;
	}

	// -----------------------------------------------------------------------
	// Collection: SSD Cache (hit rates + capacity)
	// -----------------------------------------------------------------------

	private void collectSsdCache(ResourceCollection result, SimpleJson storage) throws Exception {
		SimpleJson caches = storage.data().get("ssdCaches");
		if (caches.isNull() || caches.size() == 0) return;

		for (SimpleJson cache : caches.asList()) {
			String cacheId = cache.get("id").asString();
			String cacheName = cacheDisplayName(cache, storage);
			Resource r = findOrCreate(result, "SynologySsdCache", cacheName, "cache_id", cacheId);

			r.addData("HitRate|read_hit_rate", cache.get("hit_rate").asDouble());
			r.addData("HitRate|write_hit_rate", cache.get("hit_rate_write").asDouble());

			SimpleJson size = cache.get("size");
			r.addData("Capacity|total_bytes", size.get("total").asDouble());
			r.addData("Capacity|occupied_bytes", size.get("occupied").asDouble());
			r.addData("Capacity|reusable_bytes", size.get("reusable").asDouble());
			r.addData("Capacity|memory_used", cache.get("memory").asDouble());

			addProperty(r, "Configuration|mode", cache.get("mode").asString(""));
			addProperty(r, "Configuration|status", cache.get("status").asString(""));
			addProperty(r, "Configuration|mount_volume", cache.get("mountSpaceId").asString(""));
			addProperty(r, "Configuration|device_type", cache.get("device_type").asString(""));
			addProperty(r, "Configuration|skip_seq_io",
					cache.get("skipSeqIO").asBoolean() ? "true" : "false");
			SimpleJson cacheDisks = cache.get("disks");
			int diskCount = cacheDisks.isNull() ? 0 : cacheDisks.size();
			addProperty(r, "Hardware|disk_count", String.valueOf(diskCount));
			StringBuilder members = new StringBuilder();
			if (!cacheDisks.isNull()) {
				for (SimpleJson d : cacheDisks.asList()) {
					if (members.length() > 0) members.append(", ");
					members.append(d.asString());
				}
			}
			addProperty(r, "Hardware|disk_members", members.toString());
			double totalBytes = size.get("total").asDouble();
			addProperty(r, "Hardware|total_capacity",
					String.format("%.1f GB", totalBytes / (1024.0 * 1024.0 * 1024.0)));
			addProperty(r, "Hardware|disk_failure_count",
					String.valueOf(cache.get("disk_failure_number").asLong()));

			result.add(r);
		}
	}

	// -----------------------------------------------------------------------
	// Collection: iSCSI LUNs (with IO join)
	// -----------------------------------------------------------------------

	private void collectIscsiLuns(ResourceCollection result) throws Exception {
		SimpleJson luns = api.iscsiLunList();
		SimpleJson targets = api.iscsiTargetList();
		SimpleJson util = api.utilization();

		// Build LUN IO lookup from Utilization
		Map<String, SimpleJson> lunIoByUuid = new HashMap<>();
		SimpleJson lunUtil = util.data().get("lun");
		if (!lunUtil.isNull()) {
			for (SimpleJson l : lunUtil.asList()) {
				lunIoByUuid.put(l.get("uuid").asString(), l);
			}
		}

		// Build target lookup maps by name
		Map<String, String> targetIqnByName = new HashMap<>();
		Map<String, String> targetEnabledByName = new HashMap<>();
		Map<String, String> targetPortalsByName = new HashMap<>();
		for (SimpleJson t : targets.data().get("targets").asList()) {
			String tName = t.get("name").asString();
			targetIqnByName.put(tName, t.get("iqn").asString());
			targetEnabledByName.put(tName, t.get("is_enabled").asBoolean() ? "true" : "false");
			StringBuilder portals = new StringBuilder();
			SimpleJson np = t.get("network_portals");
			if (!np.isNull()) {
				for (SimpleJson p : np.asList()) {
					if (portals.length() > 0) portals.append(", ");
					portals.append(p.asString());
				}
			}
			targetPortalsByName.put(tName, portals.toString());
		}

		for (SimpleJson lun : luns.data().get("luns").asList()) {
			String uuid = lun.get("uuid").asString();
			String name = lun.get("name").asString();
			String lunDisplayName = name.isEmpty() ? uuid : name;
			Resource r = findOrCreate(result, "SynologyIscsiLun", lunDisplayName, "lun_uuid", uuid);

			addProperty(r, "Configuration|name", name);
			addProperty(r, "Configuration|size_bytes", String.valueOf(lun.get("size").asLong()));
			addProperty(r, "Configuration|location", lun.get("location").asString(""));
			addProperty(r, "Configuration|type", lun.get("type_str").asString(""));

			// Join target properties by naming convention
			String iqn = targetIqnByName.get(name);
			addProperty(r, "Configuration|target_iqn", iqn != null ? iqn : "");
			String enabled = targetEnabledByName.get(name);
			addProperty(r, "Configuration|target_enabled", enabled != null ? enabled : "");
			String portals = targetPortalsByName.get(name);
			addProperty(r, "Configuration|network_portals", portals != null ? portals : "");

			// JOIN: LUN IO from Utilization
			SimpleJson io = lunIoByUuid.get(uuid);
			if (io != null) {
				r.addData("IO|read_iops", io.get("read_iops").asDouble());
				r.addData("IO|write_iops", io.get("write_iops").asDouble());
				r.addData("IO|read_throughput", io.get("read_throughput").asDouble());
				r.addData("IO|write_throughput", io.get("write_throughput").asDouble());
				r.addData("IO|read_latency", io.get("read_latency").asDouble());
				r.addData("IO|write_latency", io.get("write_latency").asDouble());
			}

			result.add(r);
		}
	}

	// -----------------------------------------------------------------------
	// Collection: NFS Exports
	// -----------------------------------------------------------------------

	private void collectNfsExports(ResourceCollection result) throws Exception {
		SimpleJson shares = api.shareList();
		SimpleJson conns = api.currentConnections();

		// Build NFS client count by share name
		Map<String, Integer> clientsByShare = new HashMap<>();
		for (SimpleJson conn : conns.data().get("items").asList()) {
			if ("NFS".equals(conn.get("protocol").asString())) {
				String descr = conn.get("descr").asString("");
				if (!"-".equals(descr) && !descr.isEmpty()) {
					clientsByShare.merge(descr, 1, Integer::sum);
				}
			}
		}

		for (SimpleJson share : shares.data().get("shares").asList()) {
			String name = share.get("name").asString();

			// Check NFS rules (identifies this as an NFS export)
			SimpleJson rules;
			try {
				rules = api.nfsSharePrivilege(name);
			} catch (Exception e) {
				continue;
			}
			int ruleCount = rules.data().get("rule").size();
			if (ruleCount == 0) continue;

			Resource r = findOrCreate(result, "SynologyNfsExport", name, "share_name", name);

			String volPath = share.get("vol_path").asString("");
			addProperty(r, "Configuration|export_path", volPath + "/" + name);
			addProperty(r, "Configuration|volume_path", volPath);
			addProperty(r, "Configuration|description", share.get("desc").asString(""));
			addProperty(r, "Configuration|quota_value_mib", String.valueOf(share.get("quota_value").asLong()));
			addProperty(r, "Access|cow_enabled", share.get("enable_share_cow").asBoolean() ? "true" : "false");
			addProperty(r, "Access|compress_enabled", share.get("enable_share_compress").asBoolean() ? "true" : "false");
			addProperty(r, "Access|rule_count", String.valueOf(ruleCount));

			// Build allowed_clients string
			StringBuilder clients = new StringBuilder();
			for (SimpleJson rule : rules.data().get("rule").asList()) {
				if (clients.length() > 0) clients.append(", ");
				clients.append(rule.get("client").asString(""));
			}
			addProperty(r, "Access|allowed_clients", clients.toString());

			// Capacity metrics
			r.addData("Capacity|size_used_mib", share.get("share_quota_used").asDouble());
			r.addData("Capacity|size_logical_mib", share.get("share_quota_logical_size").asDouble());
			long quota = share.get("quota_value").asLong();
			double used = share.get("share_quota_used").asDouble();
			r.addData("Capacity|quota_usage_pct", quota > 0 ? (used / quota) * 100.0 : 0.0);

			// Active client count
			r.addData("Clients|active_client_count",
					(double) clientsByShare.getOrDefault(name, 0));

			result.add(r);
		}
	}

	// -----------------------------------------------------------------------
	// Collection: UPS
	// -----------------------------------------------------------------------

	private void collectUps(ResourceCollection result) throws Exception {
		SimpleJson ups;
		try {
			ups = api.upsGet();
		} catch (Exception e) {
			return;
		}

		boolean connected = ups.data().get("usb_ups_connect").asBoolean();
		if (!connected) return;

		String model = ups.data().get("model").asString("UPS");
		Resource r = findOrCreate(result, "SynologyUps", model, "ups_model", model);

		r.addData("Battery|charge_pct", ups.data().get("charge").asDouble());
		r.addData("Battery|runtime_seconds", ups.data().get("runtime").asDouble());
		addProperty(r, "Status|status", ups.data().get("status").asString(""));
		addProperty(r, "Status|mode", ups.data().get("mode").asString(""));
		addProperty(r, "Status|connected", connected ? "true" : "false");

		result.add(r);
	}

	// -----------------------------------------------------------------------
	// Relationships: internal parent/child + ARIA_OPS Datastore stitching
	// -----------------------------------------------------------------------

	private void buildRelationships(ResourceCollection rel) throws Exception {
		SimpleJson storage = api.storageLoadInfo();
		SimpleJson dsmInfo = api.dsmInfo();
		String serial = dsmInfo.data().get("serial").asString("unknown");
		String dsModel = dsmInfo.data().get("model").asString("");
		String dsName = dsModel.isEmpty() ? serial : dsModel + " " + serial;

		// Build disk name lookup (disk id → human name)
		Map<String, String> diskNames = new HashMap<>();
		for (SimpleJson disk : storage.data().get("disks").asList()) {
			diskNames.put(disk.get("id").asString(),
					disk.get("name").asString(disk.get("id").asString()));
		}

		// World → Diskstation
		Resource world = createResource("SynologyWorld", "Synology World",
				"world_id", "synology_world");
		Resource diskstation = createResource("SynologyDiskstation", dsName, "serial", serial);
		world.addChild(diskstation);

		// Storage Pool → child of Diskstation
		for (SimpleJson pool : storage.data().get("storagePools").asList()) {
			String poolId = pool.get("id").asString();
			String poolPath = pool.get("pool_path").asString();
			String poolName = poolDisplayName(pool);
			Resource poolRes = createResource("SynologyStoragePool", poolName, "pool_id", poolId);
			diskstation.addChild(poolRes);

			// Volume → child of Storage Pool (joined by pool_path)
			for (SimpleJson vol : storage.data().get("volumes").asList()) {
				if (poolPath.equals(vol.get("pool_path").asString())) {
					String volId = vol.get("volume_id").asString(vol.get("vol_path").asString());
					String volName = volumeDisplayName(vol);
					Resource volRes = createResource("SynologyVolume", volName, "volume_id", volId);
					poolRes.addChild(volRes);
				}
			}

			// Disk → child of Storage Pool (joined by disk id in pool's disks array)
			SimpleJson poolDisks = pool.get("disks");
			if (!poolDisks.isNull()) {
				for (SimpleJson diskRef : poolDisks.asList()) {
					String diskId = diskRef.asString();
					if (diskId != null && !diskId.isEmpty()) {
						String dName = diskNames.getOrDefault(diskId, diskId);
						Resource diskRes = createResource("SynologyDisk", dName, "disk_id", diskId);
						poolRes.addChild(diskRes);
					}
				}
			}

			// Cache disks → child of Storage Pool (from cache_disks array)
			SimpleJson cacheDiskIds = pool.get("cache_disks");
			if (!cacheDiskIds.isNull()) {
				for (SimpleJson diskRef : cacheDiskIds.asList()) {
					String diskId = diskRef.asString();
					if (diskId != null && !diskId.isEmpty()) {
						String dName = diskNames.getOrDefault(diskId, diskId);
						Resource diskRes = createResource("SynologyDisk", dName, "disk_id", diskId);
						poolRes.addChild(diskRes);
					}
				}
			}
		}

		// iSCSI LUN → child of Volume (joined by location == vol_path)
		SimpleJson luns = api.iscsiLunList();
		for (SimpleJson lun : luns.data().get("luns").asList()) {
			String uuid = lun.get("uuid").asString();
			String lunName = lun.get("name").asString(uuid);
			String location = lun.get("location").asString();
			Resource lunRes = createResource("SynologyIscsiLun", lunName, "lun_uuid", uuid);

			for (SimpleJson vol : storage.data().get("volumes").asList()) {
				if (location.equals(vol.get("vol_path").asString())) {
					String volId = vol.get("volume_id").asString(vol.get("vol_path").asString());
					String volName = volumeDisplayName(vol);
					Resource volRes = createResource("SynologyVolume", volName, "volume_id", volId);
					volRes.addChild(lunRes);
					rel.add(volRes);
					break;
				}
			}
		}

		// NFS Export → child of Volume (joined by vol_path)
		SimpleJson shares = api.shareList();
		for (SimpleJson share : shares.data().get("shares").asList()) {
			String name = share.get("name").asString();
			try {
				SimpleJson rules = api.nfsSharePrivilege(name);
				if (rules.data().get("rule").size() == 0) continue;
			} catch (Exception e) {
				continue;
			}
			String volPath = share.get("vol_path").asString();
			Resource exportRes = createResource("SynologyNfsExport", name, "share_name", name);

			for (SimpleJson vol : storage.data().get("volumes").asList()) {
				if (volPath.equals(vol.get("vol_path").asString())) {
					String volId = vol.get("volume_id").asString(vol.get("vol_path").asString());
					String volName = volumeDisplayName(vol);
					Resource volRes = createResource("SynologyVolume", volName, "volume_id", volId);
					volRes.addChild(exportRes);
					rel.add(volRes);
					break;
				}
			}
		}

		// SSD Cache → child of Volume, Cache Disks → child of SSD Cache
		SimpleJson ssdCaches = storage.data().get("ssdCaches");
		if (!ssdCaches.isNull()) {
			for (SimpleJson cache : ssdCaches.asList()) {
				String cacheId = cache.get("id").asString();
				String mountSpaceId = cache.get("mountSpaceId").asString("");
				if (cacheId == null || cacheId.isEmpty() || mountSpaceId.isEmpty()) continue;
				String cacheName = cacheDisplayName(cache, storage);
				Resource cacheRes = createResource("SynologySsdCache", cacheName, "cache_id", cacheId);

				// Cache → child of Volume
				for (SimpleJson vol : storage.data().get("volumes").asList()) {
					String volApiId = vol.get("id").asString("");
					if (mountSpaceId.equals(volApiId)) {
						String volId = vol.get("volume_id").asString(vol.get("vol_path").asString());
						String volName = volumeDisplayName(vol);
						Resource volRes = createResource("SynologyVolume", volName, "volume_id", volId);
						volRes.addChild(cacheRes);
						rel.add(volRes);
						break;
					}
				}

				// NVMe Disks → child of SSD Cache
				SimpleJson cacheDisks = cache.get("disks");
				if (!cacheDisks.isNull()) {
					for (SimpleJson diskRef : cacheDisks.asList()) {
						String diskId = diskRef.asString();
						if (diskId != null && !diskId.isEmpty()) {
							String dName = diskNames.getOrDefault(diskId, diskId);
							Resource diskRes = createResource("SynologyDisk", dName, "disk_id", diskId);
							cacheRes.addChild(diskRes);
						}
					}
					rel.add(cacheRes);
				}
			}
		}

		// UPS → child of Diskstation
		try {
			SimpleJson ups = api.upsGet();
			if (ups.data().get("usb_ups_connect").asBoolean()) {
				String upsModel = ups.data().get("model").asString("UPS");
				Resource upsRes = createResource("SynologyUps", upsModel, "ups_model", upsModel);
				diskstation.addChild(upsRes);
			}
		} catch (Exception ignored) {}

		rel.add(world);

		// --- ARIA_OPS stitching: Synology objects → VMWARE Datastore ---
		stitchDatastores(rel, luns, shares, storage);

		logInfo("Relationships built: internal tree + datastore stitching");
	}

	private void stitchDatastores(ResourceCollection rel, SimpleJson luns,
			SimpleJson shares, SimpleJson storage) throws Exception {
		if (datastoreResolver == null) {
			logWarn("SuiteAPI client not available — skipping Datastore stitching");
			return;
		}

		// Load all VMWARE Datastores, indexed by DataStrorePath
		Map<String, ResourceKey> datastoresByPath = datastoreResolver.loadAll(
				"VMWARE", "Datastore", "DataStrorePath");
		logInfo("Loaded " + datastoresByPath.size() + " VMWARE Datastores for stitching");

		// iSCSI LUN → VMWARE Datastore via NAA transform
		for (SimpleJson lun : luns.data().get("luns").asList()) {
			String uuid = lun.get("uuid").asString();
			String lunName = lun.get("name").asString(uuid);
			String naa = synologyUuidToNaa(uuid);
			String stitchKey = "VMFS:|" + naa + "|";

			ResourceKey dsKey = datastoresByPath.get(stitchKey);
			if (dsKey != null) {
				Resource lunRes = createResource("SynologyIscsiLun", lunName, "lun_uuid", uuid);
				lunRes.addParent(new Resource(dsKey));
				rel.add(lunRes);
				logInfo("Stitched iSCSI LUN " + lunName + " → Datastore " + dsKey.getResourceName());
			}
		}

		// NFS Export → VMWARE Datastore via export path
		// Get NAS IPs for path construction
		SimpleJson nics = api.networkInterfaceList();
		List<String> nasIps = new ArrayList<>();
		for (SimpleJson nic : nics.data().asList()) {
			String ip = nic.get("ip").asString("");
			if (!ip.isEmpty() && "connected".equals(nic.get("status").asString(""))) {
				nasIps.add(ip);
			}
		}

		for (SimpleJson share : shares.data().get("shares").asList()) {
			String name = share.get("name").asString();
			try {
				SimpleJson rules = api.nfsSharePrivilege(name);
				if (rules.data().get("rule").size() == 0) continue;
			} catch (Exception e) {
				continue;
			}

			String volPath = share.get("vol_path").asString("");
			String serverPath = (volPath.startsWith("/") ? volPath.substring(1) : volPath) + "/" + name;

			Resource exportRes = createResource("SynologyNfsExport", name, "share_name", name);
			boolean stitched = false;
			for (String ip : nasIps) {
				String stitchKey = ip + "/" + serverPath;
				ResourceKey dsKey = datastoresByPath.get(stitchKey);
				if (dsKey != null) {
					exportRes.addParent(new Resource(dsKey));
					logInfo("Stitched NFS export " + name + " via " + ip + " → Datastore " + dsKey.getResourceName());
					stitched = true;
				}
			}
			if (stitched) {
				rel.add(exportRes);
			}
		}
	}

	/** Synology LUN UUID → ESXi NAA (Type 6, OUI 001405). */
	static String synologyUuidToNaa(String uuid) {
		String[] parts = uuid.split("-");
		StringBuilder sb = new StringBuilder();
		for (int i = 0; i < parts.length; i++) {
			if (i > 0) sb.append("d");
			sb.append(parts[i]);
		}
		return "naa.6001405" + sb.substring(0, Math.min(25, sb.length()));
	}

	// -----------------------------------------------------------------------
	// Display name helpers
	// -----------------------------------------------------------------------

	private static String poolDisplayName(SimpleJson pool) {
		long numId = pool.get("num_id").asLong();
		return "Storage Pool " + numId;
	}

	private void collectWorld(ResourceCollection result) throws Exception {
		Resource world = findOrCreate(result, "SynologyWorld", "Synology World",
				"world_id", "synology_world");
		result.add(world);
	}

	private static String volumeDisplayName(SimpleJson vol) {
		long numId = vol.get("num_id").asLong();
		return "Volume " + numId;
	}

	private static String cacheDisplayName(SimpleJson cache, SimpleJson storage) {
		String mountSpaceId = cache.get("mountSpaceId").asString("");
		for (SimpleJson vol : storage.data().get("volumes").asList()) {
			if (mountSpaceId.equals(vol.get("id").asString(""))) {
				return "SSD Cache (Volume " + vol.get("num_id").asLong() + ")";
			}
		}
		return "SSD Cache";
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	private Resource createResource(String kind, String name, String idKey, String idValue) {
		ResourceKey key = new ResourceKey(name, kind, ADAPTER_KIND);
		key.addIdentifier(new ResourceIdentifierConfig(idKey, idValue, true));
		return new Resource(key);
	}

	private Resource findOrCreate(ResourceCollection coll, String kind,
			String name, String idKey, String idValue) {
		ResourceKey key = new ResourceKey(name, kind, ADAPTER_KIND);
		key.addIdentifier(new ResourceIdentifierConfig(idKey, idValue, true));
		Resource existing = coll.get(key);
		return existing != null ? existing : new Resource(key);
	}

}
