package com.vcfcf.adapter.http;

import com.vcfcf.adapter.retry.RetryPolicy;

import com.sun.net.httpserver.HttpServer;

import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * {@link HttpClientBuilder#connectTimeout(Duration)} (issue #222): the
 * default equals the request timeout (the behaviour before the setting
 * existed), an explicit value reaches the underlying
 * {@code java.net.http.HttpClient}, and {@code timeout} stays the
 * per-request read budget, including against a live local server.
 *
 * <p>No JUnit: call via {@code main()}.
 *
 * <p>Run:
 * <pre>
 *   javac -cp adapter_runtime/vrops-adapters-sdk-2.2.jar:adapter_runtime/vcfcf-adapter-base.jar \
 *         adapter_framework/test/com/vcfcf/adapter/http/HttpClientBuilderTest.java \
 *         -d build/test-classes
 *   java -cp build/test-classes:adapter_runtime/vrops-adapters-sdk-2.2.jar:adapter_runtime/vcfcf-adapter-base.jar \
 *         com.vcfcf.adapter.http.HttpClientBuilderTest
 * </pre>
 */
public class HttpClientBuilderTest {

    private static final List<String> FAILURES = new ArrayList<>();
    private static int passed = 0;

    public static void main(String[] args) throws Exception {
        testDefaultConnectTimeoutIsTheTimeout();
        testExplicitConnectTimeout();
        testOrderDoesNotMatterAndNullFallsBack();
        testReadBudgetIsTheTimeoutAgainstASlowServer();
        report();
    }

    private static void testDefaultConnectTimeoutIsTheTimeout() {
        ManagedHttpClient c = HttpClientBuilder.builder().baseUrl("http://127.0.0.1:1").build();
        eq("default: connect timeout 30 s (unchanged)", Optional.of(Duration.ofSeconds(30)),
                c.underlyingClient().connectTimeout());
        eq("default: request timeout 30 s", Duration.ofSeconds(30), c.requestTimeout());

        ManagedHttpClient t = HttpClientBuilder.builder().timeout(Duration.ofSeconds(45)).build();
        eq("timeout only: connect timeout follows it", Optional.of(Duration.ofSeconds(45)),
                t.underlyingClient().connectTimeout());
        eq("timeout only: request timeout", Duration.ofSeconds(45), t.requestTimeout());
    }

    private static void testExplicitConnectTimeout() {
        ManagedHttpClient c = HttpClientBuilder.builder()
                .timeout(Duration.ofSeconds(30))
                .connectTimeout(Duration.ofSeconds(5))
                .build();
        eq("explicit: connect timeout reaches HttpClient", Optional.of(Duration.ofSeconds(5)),
                c.underlyingClient().connectTimeout());
        eq("explicit: request (read) timeout stays 30 s", Duration.ofSeconds(30),
                c.requestTimeout());
    }

    private static void testOrderDoesNotMatterAndNullFallsBack() {
        ManagedHttpClient c = HttpClientBuilder.builder()
                .connectTimeout(Duration.ofSeconds(3))
                .timeout(Duration.ofSeconds(60))
                .build();
        eq("connectTimeout before timeout: still 3 s", Optional.of(Duration.ofSeconds(3)),
                c.underlyingClient().connectTimeout());
        eq("connectTimeout before timeout: request timeout 60 s", Duration.ofSeconds(60),
                c.requestTimeout());

        ManagedHttpClient n = HttpClientBuilder.builder()
                .timeout(Duration.ofSeconds(20))
                .connectTimeout(Duration.ofSeconds(3))
                .connectTimeout(null)
                .build();
        eq("connectTimeout(null): back to the timeout", Optional.of(Duration.ofSeconds(20)),
                n.underlyingClient().connectTimeout());
    }

    /**
     * A local server that answers after 2 s: a 300 ms request timeout with a
     * 10 s connect timeout times out on the read; a 10 s request timeout with
     * a 300 ms connect timeout gets the answer (the connect budget does not
     * cap a slow response).
     */
    private static void testReadBudgetIsTheTimeoutAgainstASlowServer() throws Exception {
        HttpServer s = HttpServer.create(new InetSocketAddress(
                InetAddress.getLoopbackAddress(), 0), 0);
        s.createContext("/", ex -> {
            try {
                Thread.sleep(2000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            byte[] body = "ok".getBytes(StandardCharsets.UTF_8);
            ex.sendResponseHeaders(200, body.length);
            try (OutputStream os = ex.getResponseBody()) {
                os.write(body);
            }
        });
        java.util.concurrent.ExecutorService pool =
                java.util.concurrent.Executors.newCachedThreadPool(r -> {
                    Thread t = new Thread(r, "slow-server");
                    t.setDaemon(true);
                    return t;
                });
        s.setExecutor(pool);
        s.start();
        try {
            String base = "http://127.0.0.1:" + s.getAddress().getPort();
            RetryPolicy once = RetryPolicy.builder().maxAttempts(1).build();
            ManagedHttpClient shortRead = HttpClientBuilder.builder().baseUrl(base)
                    .retryPolicy(once)
                    .timeout(Duration.ofMillis(300))
                    .connectTimeout(Duration.ofSeconds(10))
                    .build();
            long t0 = System.nanoTime();
            try {
                shortRead.get("/", HttpResponse.BodyHandlers.ofString());
                check("short read budget: slow response must time out", false);
            } catch (HttpTimeoutException e) {
                long ms = (System.nanoTime() - t0) / 1_000_000;
                check("short read budget: HttpTimeoutException after " + ms
                        + " ms (well under the 2 s answer)", ms < 1800);
            }

            ManagedHttpClient shortConnect = HttpClientBuilder.builder().baseUrl(base)
                    .retryPolicy(once)
                    .timeout(Duration.ofSeconds(10))
                    .connectTimeout(Duration.ofMillis(300))
                    .build();
            eq("short connect, long read budget: slow answer still arrives", 200,
                    shortConnect.get("/", HttpResponse.BodyHandlers.ofString()).statusCode());
        } finally {
            s.stop(0);
            pool.shutdownNow();
        }
    }

    // ----- assertions ------------------------------------------------------------

    private static void check(String name, boolean cond) {
        if (cond) {
            passed++;
            System.out.println("  PASS: " + name);
        } else {
            FAILURES.add(name);
            System.out.println("  FAIL: " + name);
        }
    }

    private static void eq(String name, Object expected, Object actual) {
        boolean ok = expected == null ? actual == null : expected.equals(actual);
        check(name + " (expected " + expected + ", got " + actual + ")", ok);
    }

    private static void report() {
        System.out.println();
        int total = passed + FAILURES.size();
        if (FAILURES.isEmpty()) {
            System.out.println("OK: " + passed + "/" + total + " tests passed.");
        } else {
            System.out.println("FAIL: " + FAILURES.size() + "/" + total + " tests failed: "
                    + FAILURES);
            System.exit(1);
        }
    }
}
