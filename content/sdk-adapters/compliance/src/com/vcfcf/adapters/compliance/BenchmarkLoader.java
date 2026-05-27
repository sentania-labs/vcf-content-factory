package com.vcfcf.adapters.compliance;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

public final class BenchmarkLoader {

	private volatile BenchmarkProfile cachedProfile;
	private volatile String cachedProfileKey;

	public BenchmarkProfile load(String profileName, String customPath,
			String confDir) {
		String key = profileName + "|" + customPath + "|" + confDir;
		if (cachedProfile != null && key.equals(cachedProfileKey)) {
			return cachedProfile;
		}

		List<String> lines;
		if ("Custom".equalsIgnoreCase(profileName) && customPath != null
				&& !customPath.isEmpty()) {
			lines = readFile(Paths.get(customPath));
		} else {
			lines = readBundledProfile(profileName, confDir);
		}

		List<BenchmarkProfile.Control> controls = parseCsv(lines);
		BenchmarkProfile profile = new BenchmarkProfile(profileName, controls);
		cachedProfile = profile;
		cachedProfileKey = key;
		return profile;
	}

	public void invalidate() {
		cachedProfile = null;
		cachedProfileKey = null;
	}

	private List<String> readBundledProfile(String profileName, String confDir) {
		String filename;
		switch (profileName) {
			case "VMware_SCG_9.0":
				filename = "vmware_scg_9.0.csv";
				break;
			case "CIS_vSphere_8":
				filename = "cis_vsphere_8.csv";
				break;
			case "VMware_SCG_8.0":
			default:
				filename = "vmware_scg_8.0.csv";
				break;
		}

		if (confDir != null && !confDir.isEmpty()) {
			Path confPath = Paths.get(confDir, "profiles", filename);
			if (Files.exists(confPath)) {
				return readFile(confPath);
			}
		}

		InputStream is = getClass().getResourceAsStream("/profiles/" + filename);
		if (is != null) {
			return readStream(is);
		}

		return new ArrayList<>();
	}

	private List<String> readStream(InputStream is) {
		List<String> lines = new ArrayList<>();
		try (BufferedReader reader = new BufferedReader(
				new InputStreamReader(is, StandardCharsets.UTF_8))) {
			String line;
			while ((line = reader.readLine()) != null) {
				lines.add(line);
			}
		} catch (IOException e) {
			throw new RuntimeException("Failed to read bundled profile", e);
		}
		return lines;
	}

	private List<String> readFile(Path path) {
		List<String> lines = new ArrayList<>();
		try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
			String line;
			while ((line = reader.readLine()) != null) {
				lines.add(line);
			}
		} catch (IOException e) {
			throw new RuntimeException("Failed to read profile: " + path, e);
		}
		return lines;
	}

	static List<BenchmarkProfile.Control> parseCsv(List<String> lines) {
		List<BenchmarkProfile.Control> controls = new ArrayList<>();
		boolean headerSkipped = false;

		for (String line : lines) {
			if (!headerSkipped) {
				headerSkipped = true;
				continue;
			}
			if (line.trim().isEmpty()) continue;

			String[] fields = parseCsvLine(line);
			if (fields.length < 12) continue;

			String scgId = fields[0].trim();
			if (scgId.isEmpty()) continue;

			controls.add(new BenchmarkProfile.Control(
					scgId,
					fields[3].trim(),   // Component
					fields[6].trim(),   // Implementation Priority
					fields[7].trim(),   // Description/Title
					fields[9].trim(),   // Configuration Parameter
					fields[10].trim(),  // Installation Default Value
					fields[11].trim(),  // Baseline Suggested Value
					fields.length > 16 ? fields[16].trim() : ""  // PowerCLI Assessment
			));
		}
		return controls;
	}

	static String[] parseCsvLine(String line) {
		List<String> fields = new ArrayList<>();
		StringBuilder current = new StringBuilder();
		boolean inQuotes = false;

		for (int i = 0; i < line.length(); i++) {
			char c = line.charAt(i);
			if (c == '"') {
				if (inQuotes && i + 1 < line.length() && line.charAt(i + 1) == '"') {
					current.append('"');
					i++;
				} else {
					inQuotes = !inQuotes;
				}
			} else if (c == ',' && !inQuotes) {
				fields.add(current.toString());
				current.setLength(0);
			} else {
				current.append(c);
			}
		}
		fields.add(current.toString());
		return fields.toArray(new String[0]);
	}
}
