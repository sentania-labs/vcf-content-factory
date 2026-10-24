package com.vcfcf.adapter.http;

import java.io.ByteArrayOutputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Flow;
import java.util.concurrent.TimeUnit;

/**
 * Tests for {@link ManagedHttpClient#copyWithUri}, the DNS round-robin
 * request copy (issue #252: it replaced a Java 16 call that the 8.18
 * collector's Java 11 cannot serve).
 *
 * <p>No JUnit required: call via {@code main()}, exit status 1 on any
 * failure. Run with {@code -Djdk.httpclient.allowRestrictedHeaders=host,connection}
 * so the original request can carry restricted headers the copy must drop.
 * {@code tests/managementpacks/test_managed_http_client_copy.py} compiles
 * this with {@code --release 11} and runs it.
 */
public final class ManagedHttpClientCopyTest {

	private static int failures = 0;

	private static void check(boolean ok, String what) {
		System.out.println((ok ? "PASS " : "FAIL ") + what);
		if (!ok) {
			failures++;
		}
	}

	private static byte[] bodyBytes(HttpRequest req) throws Exception {
		Optional<HttpRequest.BodyPublisher> pub = req.bodyPublisher();
		if (pub.isEmpty()) {
			return null;
		}
		ByteArrayOutputStream out = new ByteArrayOutputStream();
		CompletableFuture<Void> done = new CompletableFuture<>();
		pub.get().subscribe(new Flow.Subscriber<ByteBuffer>() {
			public void onSubscribe(Flow.Subscription s) { s.request(Long.MAX_VALUE); }
			public void onNext(ByteBuffer b) {
				byte[] chunk = new byte[b.remaining()];
				b.get(chunk);
				out.write(chunk, 0, chunk.length);
			}
			public void onError(Throwable t) { done.completeExceptionally(t); }
			public void onComplete() { done.complete(null); }
		});
		done.get(10, TimeUnit.SECONDS);
		return out.toByteArray();
	}

	public static void main(String[] args) throws Exception {
		URI host = URI.create("https://nas.example:5001/webapi/entry.cgi?api=SYNO.API&v=1");
		URI ip = URI.create("https://10.0.0.5:5001/webapi/entry.cgi?api=SYNO.API&v=1");
		String json = "{\"name\":\"probe\",\"n\":1}";

		HttpRequest post = HttpRequest.newBuilder(host)
				.header("Accept", "application/json")
				.header("Content-Type", "application/json")
				.header("X-Multi", "one")
				.header("X-Multi", "two")
				.header("Host", "nas.example")
				.header("Connection", "keep-alive")
				.timeout(Duration.ofSeconds(17))
				.version(HttpClient.Version.HTTP_1_1)
				.expectContinue(true)
				.POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8))
				.build();
		HttpRequest copy = ManagedHttpClient.copyWithUri(post, ip);
		check(copy.uri().equals(ip), "POST: URI is the IP URI");
		check("POST".equals(copy.method()), "POST: method kept");
		check(copy.timeout().equals(Optional.of(Duration.ofSeconds(17))), "POST: timeout kept");
		check(copy.version().equals(Optional.of(HttpClient.Version.HTTP_1_1)), "POST: version kept");
		check(copy.expectContinue(), "POST: expect-continue kept");
		Map<String, List<String>> h = copy.headers().map();
		check(List.of("application/json").equals(h.get("Accept")), "POST: Accept kept");
		check(List.of("application/json").equals(h.get("Content-Type")), "POST: Content-Type kept");
		check(List.of("one", "two").equals(h.get("X-Multi")), "POST: multi-valued header kept in order");
		check(copy.headers().firstValue("Host").isEmpty(), "POST: restricted Host dropped");
		check(copy.headers().firstValue("Connection").isEmpty(), "POST: restricted Connection dropped");
		check(h.size() == 3, "POST: no other header added (" + h.keySet() + ")");
		byte[] body = bodyBytes(copy);
		check(body != null && json.equals(new String(body, StandardCharsets.UTF_8)), "POST: body bytes equal");
		check(copy.bodyPublisher().get().contentLength() == post.bodyPublisher().get().contentLength(),
				"POST: content length equal");

		HttpRequest put = HttpRequest.newBuilder(host)
				.PUT(HttpRequest.BodyPublishers.ofString("x=1")).build();
		HttpRequest putCopy = ManagedHttpClient.copyWithUri(put, ip);
		check("PUT".equals(putCopy.method()), "PUT: method kept");
		check("x=1".equals(new String(bodyBytes(putCopy), StandardCharsets.UTF_8)), "PUT: body bytes equal");
		check(putCopy.timeout().isEmpty() && putCopy.version().isEmpty() && !putCopy.expectContinue(),
				"PUT: unset timeout, version and expect-continue stay unset");

		HttpRequest get = HttpRequest.newBuilder(host).header("Cookie", "id=abc").GET().build();
		HttpRequest getCopy = ManagedHttpClient.copyWithUri(get, ip);
		check("GET".equals(getCopy.method()), "GET: method kept");
		check(getCopy.bodyPublisher().isEmpty(), "GET: still no body publisher");
		check(List.of("id=abc").equals(getCopy.headers().map().get("Cookie")), "GET: header kept");

		HttpRequest del = HttpRequest.newBuilder(host).DELETE().build();
		HttpRequest delCopy = ManagedHttpClient.copyWithUri(del, ip);
		check("DELETE".equals(delCopy.method()), "DELETE: method kept");
		check(delCopy.bodyPublisher().equals(del.bodyPublisher().isPresent()
				? delCopy.bodyPublisher() : Optional.empty()), "DELETE: body publisher presence kept");

		System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILURE(S)");
		System.exit(failures == 0 ? 0 : 1);
	}
}
