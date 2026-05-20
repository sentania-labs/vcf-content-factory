package com.vcfcf.adapters.unifi;

import com.vcfcf.adapter.VcfCfAdapter;
import com.vcfcf.adapter.auth.SessionCookieAuth;
import com.vcfcf.adapter.http.HttpClientBuilder;
import com.vcfcf.adapter.http.ManagedHttpClient;
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

public final class UniFiAdapter extends VcfCfAdapter<UniFiConfig> {

	private static final String ADAPTER_KIND = "unifi_controller";

	private volatile UniFiApiClient api;
	private volatile ForeignResourceResolver hostResolver;

	public UniFiAdapter() {
		super();
	}

	public UniFiAdapter(String adapterDir, Integer adapterInstanceId) {
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

		this.config = new UniFiConfig(host, port, username, password, allowInsecure);

		// Raw client for login (no auth strategy yet)
		ManagedHttpClient rawHttp = HttpClientBuilder.builder()
				.baseUrl(config.baseUrl())
				.allowInsecure(config.allowInsecure)
				.retryPolicy(RetryPolicy.builder()
						.maxAttempts(3)
						.baseDelayMs(1000)
						.build())
				.timeout(Duration.ofSeconds(30))
				.build();

		// Session cookie auth: TOKEN cookie from /api/auth/login
		SessionCookieAuth auth = new SessionCookieAuth("TOKEN",
				() -> UniFiApiClient.login(rawHttp, config.username, config.password));

		this.httpClient = HttpClientBuilder.builder()
				.baseUrl(config.baseUrl())
				.allowInsecure(config.allowInsecure)
				.auth(auth)
				.retryPolicy(RetryPolicy.builder()
						.maxAttempts(3)
						.baseDelayMs(1000)
						.build())
				.timeout(Duration.ofSeconds(30))
				.build();

		this.api = new UniFiApiClient(httpClient);

		if (this.suiteAPIClient != null) {
			this.hostResolver = new ForeignResourceResolver(this.suiteAPIClient, this.logger);
		}

		logInfo("UniFiAdapter configured: host=" + config.host + " port=" + config.port);
	}

	@Override
	public Tester getTester(ResourceStatus status, ResourceConfig resourceConfig) {
		return (TestParam param) -> {
			try {
				SimpleJson sites = api.listSites();
				int count = sites.get("data").size();
				logInfo("Test OK: connected, " + count + " site(s)");
			} catch (Exception e) {
				throw new TestException("Connection test failed: " + e.getMessage(), e);
			}
		};
	}

	// -----------------------------------------------------------------------
	// Discovery
	// -----------------------------------------------------------------------

	@Override
	public Discoverer getDiscoverer(ResourceStatus status, ResourceConfig resourceConfig) {
		return (DiscoveryParam param) -> {
			logInfo("UniFiAdapter discover: starting resource enumeration");
			ResourceCollection collection = new ResourceCollection();

			try {
				// SessionCookieAuth handles session automatically

				Resource world = createResource("UniFiWorld", "UniFi World",
						"world_id", "unifi_world");
				collection.add(world);

				for (SimpleJson site : api.listSites().get("data").asList()) {
					String siteName = site.get("name").asString();
					String siteDesc = site.get("desc").asString(siteName);
					collection.add(createResource("UniFiSite", siteDesc,
							"site_name", siteName));

					SimpleJson devices = api.statDevice(siteName);
					for (SimpleJson dev : devices.get("data").asList()) {
						String type = dev.get("type").asString("");
						String mac = dev.get("mac").asString();
						String name = deviceDisplayName(dev);

						if ("udm".equals(type) || "ugw".equals(type) || "uxg".equals(type)) {
							collection.add(createResource("UniFiGateway", name, "mac", mac));
							// WAN interfaces
							if (!dev.get("wan1").isNull()) {
								collection.add(createResource("UniFiWanInterface",
										"WAN 1", "wan_name", mac + "_wan1"));
							}
							if (!dev.get("wan2").isNull()) {
								collection.add(createResource("UniFiWanInterface",
										"WAN 2", "wan_name", mac + "_wan2"));
							}
						} else if ("usw".equals(type)) {
							collection.add(createResource("UniFiSwitch", name, "mac", mac));
							SimpleJson ports = dev.get("port_table");
							if (!ports.isNull()) {
								for (SimpleJson port : ports.asList()) {
									int idx = (int) port.get("port_idx").asLong();
									String portKey = mac + "_" + idx;
									String portName = portDisplayName(port, idx);
									collection.add(createResource("UniFiSwitchPort",
											portName, "port_key", portKey));
								}
							}
						} else if ("uap".equals(type)) {
							collection.add(createResource("UniFiAccessPoint", name, "mac", mac));
							SimpleJson radios = dev.get("radio_table_stats");
							if (!radios.isNull()) {
								for (SimpleJson radio : radios.asList()) {
									String radioCode = radio.get("radio").asString("");
									String radioKey = mac + "_" + radioCode;
									collection.add(createResource("UniFiRadio",
											radioDisplayName(radioCode),
											"radio_key", radioKey));
								}
							}
						}
					}

					// Wireless aggregate
					collection.add(createResource("UniFiWirelessAggregate",
							"Wireless Summary",
							"aggregate_id", siteName + "_wlan_aggregate"));
				}

				// Protect: NVR + cameras
				try {
					SimpleJson protect = api.protectBootstrap();
					SimpleJson nvr = protect.get("nvr");
					if (!nvr.isNull()) {
						String nvrMac = nvr.get("mac").asString("");
						String nvrName = nvr.get("name").asString("NVR");
						collection.add(createResource("UniFiNvr", nvrName,
								"nvr_mac", nvrMac));

						SimpleJson cameras = protect.get("cameras");
						if (!cameras.isNull()) {
							for (SimpleJson cam : cameras.asList()) {
								String camMac = cam.get("mac").asString();
								String camName = cam.get("name").asString(camMac);
								collection.add(createResource("UniFiCamera", camName,
										"camera_mac", camMac));
							}
						}
					}
				} catch (Exception e) {
					logInfo("Protect not available: " + e.getMessage());
				}

				logInfo("UniFiAdapter discover: resource enumeration complete");
			} catch (Exception e) {
				logError("Discovery failed", e);
			}

			return collection;
		};
	}

	// -----------------------------------------------------------------------
	// Collection
	// -----------------------------------------------------------------------

	@Override
	public LiveCollector getLiveDataCollector(ResourceStatus status, ResourceConfig resourceConfig) {
		return new LiveCollector() {
			@Override
			public ResourceCollection getCurrentMetrics(ResourceConfig rc,
					ResourceCollection acc)
					throws CollectionException, InterruptedException {
				ResourceCollection result = new ResourceCollection();
				try {
					// SessionCookieAuth handles session automatically

					// World keepalive
					Resource world = findOrCreate(result, "UniFiWorld", "UniFi World",
							"world_id", "unifi_world");
					result.add(world);

					for (SimpleJson site : api.listSites().get("data").asList()) {
						String siteName = site.get("name").asString();
						collectSite(result, site);
						collectDevices(result, siteName);
						collectWirelessAggregate(result, siteName);
					}

					collectProtect(result);
				} catch (Exception e) {
					logError("Collection failed", e);
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
					buildRelationships(rel);
				} catch (Exception e) {
					logError("Relationship build failed", e);
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
	// Collection: Site
	// -----------------------------------------------------------------------

	private void collectSite(ResourceCollection result, SimpleJson site) {
		String siteName = site.get("name").asString();
		String siteDesc = site.get("desc").asString(siteName);
		Resource r = findOrCreate(result, "UniFiSite", siteDesc,
				"site_name", siteName);
		addProperty(r, "Configuration|description", site.get("desc").asString(""));
		addProperty(r, "Configuration|device_count",
				String.valueOf(site.get("device_count").asLong()));
		result.add(r);
	}

	// -----------------------------------------------------------------------
	// Collection: Devices (Gateway, Switch, AP + children)
	// -----------------------------------------------------------------------

	private void collectDevices(ResourceCollection result, String siteName)
			throws Exception {
		SimpleJson devices = api.statDevice(siteName);
		SimpleJson sysInfo = null;
		try {
			// stat/sysinfo for version/timezone
			sysInfo = api.listSites();
		} catch (Exception ignored) {}

		for (SimpleJson dev : devices.get("data").asList()) {
			String type = dev.get("type").asString("");
			if ("udm".equals(type) || "ugw".equals(type) || "uxg".equals(type)) {
				collectGateway(result, dev);
			} else if ("usw".equals(type)) {
				collectSwitch(result, dev);
			} else if ("uap".equals(type)) {
				collectAccessPoint(result, dev);
			}
		}
	}

	// -----------------------------------------------------------------------
	// Collection: Gateway
	// -----------------------------------------------------------------------

	private void collectGateway(ResourceCollection result, SimpleJson dev) {
		String mac = dev.get("mac").asString();
		String name = deviceDisplayName(dev);
		Resource r = findOrCreate(result, "UniFiGateway", name, "mac", mac);

		// System metrics — UDM system-stats are STRINGS, must coerce
		SimpleJson ss = dev.get("system-stats");
		if (!ss.isNull()) {
			r.addData("System|cpu_pct", parseDouble(ss.get("cpu").asString("0")));
			r.addData("System|mem_pct", parseDouble(ss.get("mem").asString("0")));
		}
		r.addData("System|uptime", dev.get("uptime").asDouble());
		r.addData("System|num_sta", dev.get("num_sta").asDouble());

		// Temperatures
		SimpleJson temps = dev.get("temperatures");
		if (!temps.isNull()) {
			for (SimpleJson t : temps.asList()) {
				String tName = t.get("name").asString("");
				double tValue = t.get("value").asDouble();
				if ("CPU".equals(tName)) r.addData("Temperature|temp_cpu", tValue);
				else if ("Local".equals(tName)) r.addData("Temperature|temp_local", tValue);
				else if ("PHY".equals(tName)) r.addData("Temperature|temp_phy", tValue);
			}
		}

		// Speedtest
		SimpleJson st = dev.get("speedtest-status");
		if (!st.isNull()) {
			r.addData("Speedtest|xput_up", st.get("xput_upload").asDouble());
			r.addData("Speedtest|xput_down", st.get("xput_download").asDouble());
			r.addData("Speedtest|speedtest_latency", st.get("latency").asDouble());
		}

		// Properties
		addProperty(r, "Configuration|model", dev.get("model").asString(""));
		addProperty(r, "Configuration|firmware", dev.get("version").asString(""));
		addProperty(r, "Configuration|serial", dev.get("serial").asString(""));
		addProperty(r, "Configuration|ip", dev.get("ip").asString(""));
		addProperty(r, "Configuration|mac_address", mac);
		addProperty(r, "Configuration|name", dev.get("name").asString(""));

		result.add(r);

		// WAN interfaces
		collectWanInterface(result, dev, mac, "wan1");
		collectWanInterface(result, dev, mac, "wan2");
	}

	private void collectWanInterface(ResourceCollection result, SimpleJson dev,
			String gwMac, String wanName) {
		SimpleJson wan = dev.get(wanName);
		if (wan.isNull()) return;

		String key = gwMac + "_" + wanName;
		String display = wanName.equals("wan1") ? "WAN 1" : "WAN 2";
		Resource r = findOrCreate(result, "UniFiWanInterface", display,
				"wan_name", key);

		r.addData("Traffic|tx_bytes", wan.get("tx_bytes").asDouble());
		r.addData("Traffic|rx_bytes", wan.get("rx_bytes").asDouble());
		r.addData("Health|latency", wan.get("latency").asDouble());
		r.addData("Health|availability", wan.get("availability").asDouble());
		r.addData("Health|speed", wan.get("speed").asDouble());

		addProperty(r, "Configuration|type", wan.get("type").asString(""));
		addProperty(r, "Configuration|ip", wan.get("ip").asString(""));
		addProperty(r, "Configuration|netmask", wan.get("netmask").asString(""));
		addProperty(r, "Configuration|gateway_ip", wan.get("gateway").asString(""));
		SimpleJson dns = wan.get("dns");
		if (!dns.isNull() && dns.size() > 0) {
			StringBuilder sb = new StringBuilder();
			for (SimpleJson d : dns.asList()) {
				if (sb.length() > 0) sb.append(", ");
				sb.append(d.asString());
			}
			addProperty(r, "Configuration|dns", sb.toString());
		}

		result.add(r);
	}

	// -----------------------------------------------------------------------
	// Collection: Switch + Ports
	// -----------------------------------------------------------------------

	private void collectSwitch(ResourceCollection result, SimpleJson dev) {
		String mac = dev.get("mac").asString();
		String name = deviceDisplayName(dev);
		Resource r = findOrCreate(result, "UniFiSwitch", name, "mac", mac);

		SimpleJson ss = dev.get("system-stats");
		if (!ss.isNull()) {
			r.addData("System|cpu_pct", parseDouble(ss.get("cpu").asString("0")));
			r.addData("System|mem_pct", parseDouble(ss.get("mem").asString("0")));
		}
		r.addData("System|uptime", dev.get("uptime").asDouble());
		r.addData("System|num_sta", dev.get("num_sta").asDouble());
		r.addData("System|satisfaction", dev.get("satisfaction").asDouble());

		// PoE budget
		double maxPower = dev.get("total_max_power").asDouble();
		boolean poeCapable = maxPower > 0;
		r.addData("PoE|total_max_power", maxPower);
		double poeConsumption = 0;

		// Properties
		addProperty(r, "Configuration|model", dev.get("model").asString(""));
		addProperty(r, "Configuration|firmware", dev.get("version").asString(""));
		addProperty(r, "Configuration|serial", dev.get("serial").asString(""));
		addProperty(r, "Configuration|ip", dev.get("ip").asString(""));
		addProperty(r, "Configuration|mac_address", mac);
		addProperty(r, "Configuration|name", dev.get("name").asString(""));
		addProperty(r, "Configuration|poe_capable", poeCapable ? "true" : "false");
		addProperty(r, "Configuration|has_fan",
				dev.get("has_fan").asBoolean() ? "true" : "false");

		// Ports
		SimpleJson ports = dev.get("port_table");
		int portCount = 0;
		if (!ports.isNull()) {
			portCount = ports.size();
			for (SimpleJson port : ports.asList()) {
				double portPoe = collectSwitchPort(result, port, mac);
				poeConsumption += portPoe;
			}
		}
		addProperty(r, "Configuration|port_count", String.valueOf(portCount));
		r.addData("PoE|poe_consumption", poeConsumption);
		r.addData("PoE|poe_budget_remaining", maxPower - poeConsumption);

		result.add(r);
	}

	private double collectSwitchPort(ResourceCollection result, SimpleJson port,
			String switchMac) {
		int idx = (int) port.get("port_idx").asLong();
		String portKey = switchMac + "_" + idx;
		String portName = portDisplayName(port, idx);
		Resource r = findOrCreate(result, "UniFiSwitchPort", portName,
				"port_key", portKey);

		// Traffic (cumulative counters)
		r.addData("Traffic|tx_bytes", port.get("tx_bytes").asDouble());
		r.addData("Traffic|rx_bytes", port.get("rx_bytes").asDouble());
		r.addData("Traffic|tx_errors", port.get("tx_errors").asDouble());
		r.addData("Traffic|rx_errors", port.get("rx_errors").asDouble());

		// Status
		r.addData("Status|satisfaction", port.get("satisfaction").asDouble());
		r.addData("Status|mac_table_count",
				(double) port.get("mac_table").size());
		addProperty(r, "Status|up", port.get("up").asBoolean() ? "true" : "false");
		addProperty(r, "Status|speed", String.valueOf(port.get("speed").asLong()));
		addProperty(r, "Status|duplex",
				port.get("full_duplex").asBoolean() ? "Full" : "Half");
		addProperty(r, "Status|is_uplink",
				port.get("is_uplink").asBoolean() ? "true" : "false");
		addProperty(r, "Status|media", port.get("media").asString(""));
		addProperty(r, "Status|stp_state", port.get("stp_state").asString(""));
		addProperty(r, "Status|port_name", port.get("name").asString(""));

		// PoE (fields only present on PoE-capable ports)
		double poePower = 0;
		if (port.get("port_poe").asBoolean()) {
			// poe_power is a STRING in the API — coerce
			poePower = parseDouble(port.get("poe_power").asString("0"));
			r.addData("PoE|poe_power", poePower);
			r.addData("PoE|poe_voltage", parseDouble(port.get("poe_voltage").asString("0")));
			r.addData("PoE|poe_current", parseDouble(port.get("poe_current").asString("0")));
			addProperty(r, "PoE|poe_enable",
					port.get("poe_enable").asBoolean() ? "true" : "false");
			addProperty(r, "PoE|poe_class", port.get("poe_class").asString(""));
			addProperty(r, "PoE|poe_mode", port.get("poe_mode").asString(""));
		}

		// LLDP
		SimpleJson lldpTable = port.get("lldp_table");
		if (!lldpTable.isNull() && lldpTable.size() > 0) {
			SimpleJson lldp = lldpTable.get(0);
			addProperty(r, "LLDP|lldp_system_name",
					lldp.get("lldp_system_name").asString(""));
			addProperty(r, "LLDP|lldp_port_id",
					lldp.get("lldp_port_id").asString(""));
			addProperty(r, "LLDP|lldp_chassis_id",
					lldp.get("lldp_chassis_id").asString(""));
		}

		result.add(r);
		return poePower;
	}

	// -----------------------------------------------------------------------
	// Collection: Access Point + Radios
	// -----------------------------------------------------------------------

	private void collectAccessPoint(ResourceCollection result, SimpleJson dev) {
		String mac = dev.get("mac").asString();
		String name = deviceDisplayName(dev);
		Resource r = findOrCreate(result, "UniFiAccessPoint", name, "mac", mac);

		SimpleJson ss = dev.get("system-stats");
		if (!ss.isNull()) {
			r.addData("System|cpu_pct", parseDouble(ss.get("cpu").asString("0")));
			r.addData("System|mem_pct", parseDouble(ss.get("mem").asString("0")));
		}
		r.addData("System|uptime", dev.get("uptime").asDouble());
		r.addData("System|num_sta", dev.get("num_sta").asDouble());
		r.addData("System|satisfaction", dev.get("satisfaction").asDouble());

		addProperty(r, "Configuration|model", dev.get("model").asString(""));
		addProperty(r, "Configuration|firmware", dev.get("version").asString(""));
		addProperty(r, "Configuration|serial", dev.get("serial").asString(""));
		addProperty(r, "Configuration|ip", dev.get("ip").asString(""));
		addProperty(r, "Configuration|mac_address", mac);
		addProperty(r, "Configuration|name", dev.get("name").asString(""));

		result.add(r);

		// Build radio name→code map from radio_table (config)
		Map<String, String> radioNameToCode = new HashMap<>();
		SimpleJson radioTable = dev.get("radio_table");
		if (!radioTable.isNull()) {
			for (SimpleJson rt : radioTable.asList()) {
				radioNameToCode.put(rt.get("name").asString(""),
						rt.get("radio").asString(""));
			}
		}

		// Radios from radio_table_stats
		SimpleJson radios = dev.get("radio_table_stats");
		if (!radios.isNull()) {
			for (SimpleJson radio : radios.asList()) {
				collectRadio(result, radio, mac, dev, radioNameToCode);
			}
		}
	}

	private void collectRadio(ResourceCollection result, SimpleJson radio,
			String apMac, SimpleJson dev, Map<String, String> radioNameToCode) {
		String radioCode = radio.get("radio").asString("");
		String radioKey = apMac + "_" + radioCode;
		Resource r = findOrCreate(result, "UniFiRadio",
				radioDisplayName(radioCode), "radio_key", radioKey);

		// RF metrics
		r.addData("RF|channel", radio.get("channel").asDouble());
		r.addData("RF|tx_power", radio.get("tx_power").asDouble());
		r.addData("RF|cu_total", radio.get("cu_total").asDouble());
		r.addData("RF|satisfaction", radio.get("satisfaction").asDouble());
		r.addData("RF|tx_retries_pct",
				radio.get("tx_retries_pct").asDouble());

		// Client count (hyphenated key)
		r.addData("Clients|user_num_sta",
				radio.get("user-num_sta").asDouble());

		// Radio throughput — lives in device-level stat.ap.{radioName}-tx_bytes
		String radioName = radio.get("name").asString("");
		if (!radioName.isEmpty()) {
			SimpleJson statAp = dev.get("stat").get("ap");
			if (!statAp.isNull()) {
				r.addData("Traffic|tx_bytes",
						statAp.get(radioName + "-tx_bytes").asDouble());
				r.addData("Traffic|rx_bytes",
						statAp.get(radioName + "-rx_bytes").asDouble());
			}
		}

		// Config properties (from radio_table, not radio_table_stats)
		addProperty(r, "Configuration|radio_type", radioCode);
		addProperty(r, "Configuration|radio_name", radioName);
		SimpleJson radioTable = dev.get("radio_table");
		if (!radioTable.isNull()) {
			for (SimpleJson rt : radioTable.asList()) {
				if (radioCode.equals(rt.get("radio").asString(""))) {
					addProperty(r, "Configuration|ht", rt.get("ht").asString(""));
					addProperty(r, "Configuration|min_txpower",
							String.valueOf(rt.get("min_txpower").asLong()));
					addProperty(r, "Configuration|max_txpower",
							String.valueOf(rt.get("max_txpower").asLong()));
					break;
				}
			}
		}

		result.add(r);
	}

	// -----------------------------------------------------------------------
	// Collection: Wireless Aggregate
	// -----------------------------------------------------------------------

	private void collectWirelessAggregate(ResourceCollection result,
			String siteName) throws Exception {
		SimpleJson health = api.statHealth(siteName);
		for (SimpleJson sub : health.get("data").asList()) {
			if (!"wlan".equals(sub.get("subsystem").asString(""))) continue;

			Resource r = findOrCreate(result, "UniFiWirelessAggregate",
					"Wireless Summary",
					"aggregate_id", siteName + "_wlan_aggregate");

			r.addData("Clients|num_user", sub.get("num_user").asDouble());
			r.addData("Clients|num_guest", sub.get("num_guest").asDouble());
			r.addData("Clients|num_iot", sub.get("num_iot").asDouble());
			r.addData("Clients|num_disconnected",
					sub.get("num_disconnected").asDouble());
			r.addData("Performance|num_ap", sub.get("num_ap").asDouble());
			r.addData("Performance|tx_bytes_r",
					sub.get("tx_bytes-r").asDouble());
			r.addData("Performance|rx_bytes_r",
					sub.get("rx_bytes-r").asDouble());

			result.add(r);
			break;
		}
	}

	// -----------------------------------------------------------------------
	// Collection: Protect (NVR + Cameras)
	// -----------------------------------------------------------------------

	private void collectProtect(ResourceCollection result) {
		try {
			SimpleJson protect = api.protectBootstrap();
			SimpleJson nvr = protect.get("nvr");
			if (nvr.isNull()) return;

			String nvrMac = nvr.get("mac").asString("");
			String nvrName = nvr.get("name").asString("NVR");
			Resource r = findOrCreate(result, "UniFiNvr", nvrName,
					"nvr_mac", nvrMac);

			// NVR uptime is milliseconds in Protect — normalize to seconds
			r.addData("System|uptime", nvr.get("upSince").asDouble() > 0
					? (System.currentTimeMillis() / 1000.0)
							- (nvr.get("upSince").asDouble() / 1000.0)
					: 0);

			// Storage
			SimpleJson storage = nvr.get("storageInfo");
			if (!storage.isNull()) {
				double total = storage.get("totalSize").asDouble();
				double used = storage.get("usedSize").asDouble();
				r.addData("Storage|total_bytes", total);
				r.addData("Storage|used_bytes", used);
				r.addData("Storage|usage_pct",
						total > 0 ? (used / total) * 100.0 : 0);
			}

			addProperty(r, "Configuration|model",
					nvr.get("modelKey").asString(""));
			addProperty(r, "Configuration|firmware",
					nvr.get("firmwareVersion").asString(""));
			addProperty(r, "Configuration|name", nvrName);
			addProperty(r, "Configuration|host_type",
					nvr.get("type").asString(""));
			addProperty(r, "Configuration|recording_retention_mode",
					nvr.get("recordingRetentionDurationMs").asString(""));

			SimpleJson cameras = protect.get("cameras");
			int camCount = cameras.isNull() ? 0 : cameras.size();
			addProperty(r, "Configuration|camera_count",
					String.valueOf(camCount));

			result.add(r);

			// Cameras
			if (!cameras.isNull()) {
				for (SimpleJson cam : cameras.asList()) {
					collectCamera(result, cam);
				}
			}
		} catch (Exception e) {
			logInfo("Protect collection skipped: " + e.getMessage());
		}
	}

	private void collectCamera(ResourceCollection result, SimpleJson cam) {
		String camMac = cam.get("mac").asString();
		String camName = cam.get("name").asString(camMac);
		Resource r = findOrCreate(result, "UniFiCamera", camName,
				"camera_mac", camMac);

		// Uptime: Protect uses milliseconds — normalize to seconds
		long uptimeMs = cam.get("uptime").asLong();
		r.addData("Status|uptime", uptimeMs / 1000.0);

		long lastMotion = cam.get("lastMotion").asLong();
		if (lastMotion > 0) {
			r.addData("Status|last_motion", lastMotion / 1000.0);
		}

		addProperty(r, "Status|state", cam.get("state").asString(""));
		addProperty(r, "Status|is_connected",
				cam.get("isConnected").asBoolean() ? "true" : "false");
		addProperty(r, "Status|is_recording",
				cam.get("isRecording").asBoolean() ? "true" : "false");

		addProperty(r, "Hardware|model", cam.get("modelKey").asString(""));
		addProperty(r, "Hardware|firmware",
				cam.get("firmwareVersion").asString(""));
		addProperty(r, "Hardware|type", cam.get("type").asString(""));
		// isWireless is null on wired cameras, not false
		Boolean wireless = cam.get("isWireless").isNull() ? false
				: cam.get("isWireless").asBoolean();
		addProperty(r, "Hardware|is_wireless", wireless ? "true" : "false");
		SimpleJson wired = cam.get("wiredConnectionState");
		addProperty(r, "Hardware|phy_rate", !wired.isNull()
				? String.valueOf(wired.get("phyRate").asLong()) : "");

		addProperty(r, "Network|ip", cam.get("host").asString(""));
		addProperty(r, "Network|mac_address", camMac);

		result.add(r);
	}

	// -----------------------------------------------------------------------
	// Relationships
	// -----------------------------------------------------------------------

	private void buildRelationships(ResourceCollection rel) throws Exception {
		Resource world = createResource("UniFiWorld", "UniFi World",
				"world_id", "unifi_world");

		for (SimpleJson site : api.listSites().get("data").asList()) {
			String siteName = site.get("name").asString();
			String siteDesc = site.get("desc").asString(siteName);
			Resource siteRes = createResource("UniFiSite", siteDesc,
					"site_name", siteName);
			world.addChild(siteRes);

			SimpleJson devices = api.statDevice(siteName);

			// Build MAC→Resource lookup for topology
			Map<String, Resource> deviceByMac = new HashMap<>();
			Map<String, String> deviceTypeByMac = new HashMap<>();

			for (SimpleJson dev : devices.get("data").asList()) {
				String type = dev.get("type").asString("");
				String mac = dev.get("mac").asString();
				String name = deviceDisplayName(dev);
				Resource devRes;

				if ("udm".equals(type) || "ugw".equals(type) || "uxg".equals(type)) {
					devRes = createResource("UniFiGateway", name, "mac", mac);

					// WAN interfaces → child of Gateway
					if (!dev.get("wan1").isNull()) {
						Resource wan1 = createResource("UniFiWanInterface",
								"WAN 1", "wan_name", mac + "_wan1");
						devRes.addChild(wan1);
					}
					if (!dev.get("wan2").isNull()) {
						Resource wan2 = createResource("UniFiWanInterface",
								"WAN 2", "wan_name", mac + "_wan2");
						devRes.addChild(wan2);
					}
				} else if ("usw".equals(type)) {
					devRes = createResource("UniFiSwitch", name, "mac", mac);

					// Ports → child of Switch
					SimpleJson ports = dev.get("port_table");
					if (!ports.isNull()) {
						for (SimpleJson port : ports.asList()) {
							int idx = (int) port.get("port_idx").asLong();
							String portKey = mac + "_" + idx;
							String portName = portDisplayName(port, idx);
							Resource portRes = createResource("UniFiSwitchPort",
									portName, "port_key", portKey);
							devRes.addChild(portRes);
						}
					}
				} else if ("uap".equals(type)) {
					devRes = createResource("UniFiAccessPoint", name, "mac", mac);

					// Radios → child of AP
					SimpleJson radios = dev.get("radio_table_stats");
					if (!radios.isNull()) {
						for (SimpleJson radio : radios.asList()) {
							String rc = radio.get("radio").asString("");
							Resource radioRes = createResource("UniFiRadio",
									radioDisplayName(rc),
									"radio_key", mac + "_" + rc);
							devRes.addChild(radioRes);
						}
					}
				} else {
					continue;
				}

				deviceByMac.put(mac, devRes);
				deviceTypeByMac.put(mac, type);
			}

			// Wire topology: assign parent based on uplink_mac
			for (SimpleJson dev : devices.get("data").asList()) {
				String mac = dev.get("mac").asString();
				String type = dev.get("type").asString("");
				String uplinkMac = dev.get("uplink").get("uplink_mac").asString("");
				Resource devRes = deviceByMac.get(mac);
				if (devRes == null) continue;

				Resource parentRes = deviceByMac.get(uplinkMac);
				if (parentRes != null && !uplinkMac.equals(mac)) {
					parentRes.addChild(devRes);
				} else {
					// No uplink parent → direct child of site
					siteRes.addChild(devRes);
				}
			}

			// Wireless aggregate → child of Site
			Resource aggRes = createResource("UniFiWirelessAggregate",
					"Wireless Summary",
					"aggregate_id", siteName + "_wlan_aggregate");
			siteRes.addChild(aggRes);

			// Add all device resources
			for (Resource devRes : deviceByMac.values()) {
				rel.add(devRes);
			}
		}

		// Protect: NVR + cameras
		try {
			SimpleJson protect = api.protectBootstrap();
			SimpleJson nvr = protect.get("nvr");
			if (!nvr.isNull()) {
				String nvrMac = nvr.get("mac").asString("");
				String nvrName = nvr.get("name").asString("NVR");
				Resource nvrRes = createResource("UniFiNvr", nvrName,
						"nvr_mac", nvrMac);

				// NVR → child of first site (heuristic for single-site)
				SimpleJson sites = api.listSites();
				if (sites.get("data").size() > 0) {
					String siteName = sites.get("data").get(0).get("name").asString();
					String siteDesc = sites.get("data").get(0).get("desc").asString(siteName);
					Resource siteRes = createResource("UniFiSite", siteDesc,
							"site_name", siteName);
					siteRes.addChild(nvrRes);
					rel.add(siteRes);
				}

				SimpleJson cameras = protect.get("cameras");
				if (!cameras.isNull()) {
					for (SimpleJson cam : cameras.asList()) {
						String camMac = cam.get("mac").asString();
						String camName = cam.get("name").asString(camMac);
						Resource camRes = createResource("UniFiCamera", camName,
								"camera_mac", camMac);
						nvrRes.addChild(camRes);
					}
					rel.add(nvrRes);
				}
			}
		} catch (Exception e) {
			logInfo("Protect relationships skipped: " + e.getMessage());
		}

		// LLDP → ESXi Host stitching
		stitchLldpToHosts(rel);

		rel.add(world);
		logInfo("Relationships built");
	}

	// -----------------------------------------------------------------------
	// LLDP → ESXi Host stitching
	// -----------------------------------------------------------------------

	private void stitchLldpToHosts(ResourceCollection rel) {
		if (hostResolver == null) return;

		try {
			for (SimpleJson site : api.listSites().get("data").asList()) {
				String siteName = site.get("name").asString();
				SimpleJson devices = api.statDevice(siteName);

				for (SimpleJson dev : devices.get("data").asList()) {
					if (!"usw".equals(dev.get("type").asString(""))) continue;
					String switchMac = dev.get("mac").asString();
					SimpleJson ports = dev.get("port_table");
					if (ports.isNull()) continue;

					for (SimpleJson port : ports.asList()) {
						SimpleJson lldpTable = port.get("lldp_table");
						if (lldpTable.isNull() || lldpTable.size() == 0) continue;

						String sysName = lldpTable.get(0)
								.get("lldp_system_name").asString("");
						if (sysName.isEmpty()) continue;

						try {
							ResourceKey hostKey = hostResolver.findByIdentifier(
									"VMWARE", "HostSystem",
									"VMEntityName", sysName);
							if (hostKey != null) {
								int idx = (int) port.get("port_idx").asLong();
								String portKey = switchMac + "_" + idx;
								Resource portRes = createResource("UniFiSwitchPort",
										portDisplayName(port, idx),
										"port_key", portKey);
								Resource hostRes = new Resource(hostKey);
								portRes.addParent(hostRes);
								rel.add(portRes);
							}
						} catch (Exception ignored) {}
					}
				}
			}
		} catch (Exception e) {
			logInfo("LLDP stitching skipped: " + e.getMessage());
		}
	}

	// -----------------------------------------------------------------------
	// Display name helpers
	// -----------------------------------------------------------------------

	private static String deviceDisplayName(SimpleJson dev) {
		String name = dev.get("name").asString("");
		if (!name.isEmpty()) return name;
		String model = dev.get("model").asString("");
		String mac = dev.get("mac").asString("");
		if (!model.isEmpty()) return model + " " + mac.substring(
				Math.max(0, mac.length() - 8));
		return mac;
	}

	private static String portDisplayName(SimpleJson port, int idx) {
		String name = port.get("name").asString("");
		return name.isEmpty() ? "Port " + idx : name;
	}

	private static String radioDisplayName(String radioCode) {
		switch (radioCode) {
			case "ng": return "2.4 GHz";
			case "na": return "5 GHz";
			case "6e": return "6 GHz";
			default: return radioCode;
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	private static double parseDouble(String s) {
		try {
			return Double.parseDouble(s);
		} catch (NumberFormatException e) {
			return 0;
		}
	}

	private Resource createResource(String kind, String name,
			String idKey, String idValue) {
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
