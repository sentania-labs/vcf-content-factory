package com.vcfcf.adapter.json;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Minimal recursive-descent JSON parser. Zero external dependencies.
 * Provided by vcfcf-adapter-base so every adapter can parse JSON responses
 * without pulling in third-party libraries.
 */
public final class SimpleJson {

	private final Object value;

	private SimpleJson(Object value) {
		this.value = value;
	}

	public static SimpleJson parse(String json) {
		if (json == null || json.isEmpty()) return new SimpleJson(null);
		return new SimpleJson(new Parser(json).parseValue());
	}

	public SimpleJson get(String key) {
		if (value instanceof Map) {
			@SuppressWarnings("unchecked")
			Map<String, Object> map = (Map<String, Object>) value;
			return new SimpleJson(map.get(key));
		}
		return new SimpleJson(null);
	}

	public SimpleJson get(int index) {
		if (value instanceof List) {
			List<?> list = (List<?>) value;
			if (index >= 0 && index < list.size()) {
				return new SimpleJson(list.get(index));
			}
		}
		return new SimpleJson(null);
	}

	/** Navigate a dot-delimited path: "data.cpu.user_load" */
	public SimpleJson path(String dotPath) {
		SimpleJson current = this;
		for (String segment : dotPath.split("\\.")) {
			if (current.isNull()) return current;
			try {
				int idx = Integer.parseInt(segment);
				current = current.get(idx);
			} catch (NumberFormatException e) {
				current = current.get(segment);
			}
		}
		return current;
	}

	public String asString() {
		return value != null ? value.toString() : null;
	}

	public String asString(String fallback) {
		return value != null ? value.toString() : fallback;
	}

	public double asDouble() {
		if (value instanceof Number) return ((Number) value).doubleValue();
		if (value instanceof String) {
			try { return Double.parseDouble((String) value); }
			catch (NumberFormatException e) { return 0.0; }
		}
		return 0.0;
	}

	public long asLong() {
		if (value instanceof Number) return ((Number) value).longValue();
		if (value instanceof String) {
			try { return Long.parseLong((String) value); }
			catch (NumberFormatException e) { return 0L; }
		}
		return 0L;
	}

	public boolean asBoolean() {
		if (value instanceof Boolean) return (Boolean) value;
		if (value instanceof String) return "true".equalsIgnoreCase((String) value);
		if (value instanceof Number) return ((Number) value).intValue() != 0;
		return false;
	}

	public boolean isNull() {
		return value == null;
	}

	public boolean isObject() {
		return value instanceof Map;
	}

	public boolean isList() {
		return value instanceof List;
	}

	public int size() {
		if (value instanceof List) return ((List<?>) value).size();
		if (value instanceof Map) return ((Map<?, ?>) value).size();
		return 0;
	}

	public List<SimpleJson> asList() {
		if (value instanceof List) {
			List<?> raw = (List<?>) value;
			List<SimpleJson> result = new ArrayList<>(raw.size());
			for (Object item : raw) result.add(new SimpleJson(item));
			return result;
		}
		return List.of();
	}

	/** Synology-specific: check data.success == true */
	public boolean isSuccess() {
		SimpleJson s = get("success");
		return s.asBoolean();
	}

	/** Synology-specific: get data payload */
	public SimpleJson data() {
		return get("data");
	}

	// --- Recursive-descent parser ---

	private static final class Parser {
		private final String src;
		private int pos;

		Parser(String src) {
			this.src = src;
			this.pos = 0;
		}

		Object parseValue() {
			skipWhitespace();
			if (pos >= src.length()) return null;
			char c = src.charAt(pos);
			if (c == '{') return parseObject();
			if (c == '[') return parseArray();
			if (c == '"') return parseString();
			if (c == 't' || c == 'f') return parseBoolean();
			if (c == 'n') return parseNull();
			return parseNumber();
		}

		Map<String, Object> parseObject() {
			expect('{');
			Map<String, Object> map = new LinkedHashMap<>();
			skipWhitespace();
			if (pos < src.length() && src.charAt(pos) == '}') {
				pos++;
				return map;
			}
			while (true) {
				skipWhitespace();
				String key = parseString();
				skipWhitespace();
				expect(':');
				Object val = parseValue();
				map.put(key, val);
				skipWhitespace();
				if (pos >= src.length()) break;
				if (src.charAt(pos) == ',') {
					pos++;
				} else {
					break;
				}
			}
			skipWhitespace();
			if (pos < src.length() && src.charAt(pos) == '}') pos++;
			return map;
		}

		List<Object> parseArray() {
			expect('[');
			List<Object> list = new ArrayList<>();
			skipWhitespace();
			if (pos < src.length() && src.charAt(pos) == ']') {
				pos++;
				return list;
			}
			while (true) {
				list.add(parseValue());
				skipWhitespace();
				if (pos >= src.length()) break;
				if (src.charAt(pos) == ',') {
					pos++;
				} else {
					break;
				}
			}
			skipWhitespace();
			if (pos < src.length() && src.charAt(pos) == ']') pos++;
			return list;
		}

		String parseString() {
			skipWhitespace();
			expect('"');
			StringBuilder sb = new StringBuilder();
			while (pos < src.length()) {
				char c = src.charAt(pos);
				if (c == '\\') {
					pos++;
					if (pos < src.length()) {
						char esc = src.charAt(pos);
						switch (esc) {
							case '"': case '\\': case '/': sb.append(esc); break;
							case 'n': sb.append('\n'); break;
							case 't': sb.append('\t'); break;
							case 'r': sb.append('\r'); break;
							case 'b': sb.append('\b'); break;
							case 'f': sb.append('\f'); break;
							case 'u':
								if (pos + 4 < src.length()) {
									String hex = src.substring(pos + 1, pos + 5);
									sb.append((char) Integer.parseInt(hex, 16));
									pos += 4;
								}
								break;
							default: sb.append(esc);
						}
					}
				} else if (c == '"') {
					pos++;
					return sb.toString();
				} else {
					sb.append(c);
				}
				pos++;
			}
			return sb.toString();
		}

		Number parseNumber() {
			skipWhitespace();
			int start = pos;
			boolean isFloat = false;
			if (pos < src.length() && src.charAt(pos) == '-') pos++;
			while (pos < src.length() && Character.isDigit(src.charAt(pos))) pos++;
			if (pos < src.length() && src.charAt(pos) == '.') {
				isFloat = true;
				pos++;
				while (pos < src.length() && Character.isDigit(src.charAt(pos))) pos++;
			}
			if (pos < src.length() && (src.charAt(pos) == 'e' || src.charAt(pos) == 'E')) {
				isFloat = true;
				pos++;
				if (pos < src.length() && (src.charAt(pos) == '+' || src.charAt(pos) == '-')) pos++;
				while (pos < src.length() && Character.isDigit(src.charAt(pos))) pos++;
			}
			String numStr = src.substring(start, pos);
			if (isFloat) return Double.parseDouble(numStr);
			long v = Long.parseLong(numStr);
			if (v >= Integer.MIN_VALUE && v <= Integer.MAX_VALUE) return (int) v;
			return v;
		}

		Boolean parseBoolean() {
			if (src.startsWith("true", pos)) { pos += 4; return true; }
			if (src.startsWith("false", pos)) { pos += 5; return false; }
			throw new IllegalStateException("Expected boolean at pos " + pos);
		}

		Object parseNull() {
			if (src.startsWith("null", pos)) { pos += 4; return null; }
			throw new IllegalStateException("Expected null at pos " + pos);
		}

		void expect(char c) {
			skipWhitespace();
			if (pos < src.length() && src.charAt(pos) == c) {
				pos++;
			}
		}

		void skipWhitespace() {
			while (pos < src.length() && Character.isWhitespace(src.charAt(pos))) pos++;
		}
	}
}
