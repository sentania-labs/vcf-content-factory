package com.vcfcf.adapter.retry;

import java.io.IOException;
import java.net.http.HttpResponse;
import java.util.Random;
import java.util.Set;
import java.util.logging.Logger;

/**
 * Exponential-backoff-with-jitter retry policy for HTTP calls.
 *
 * <p>The platform does NOT retry failed {@code collect()} cycles (Pass 23
 * empirical finding). Errors in {@code onCollect()} are swallow-and-logged
 * at the platform level; the adapter must own retry inside the cycle.
 *
 * <p>This class wraps an HTTP call ({@link HttpCallable}) and retries it up
 * to {@link #maxAttempts} times when:
 * <ul>
 *   <li>The HTTP status code is in {@link #retryStatuses} (default: 5xx + 429)</li>
 *   <li>An {@link IOException} is thrown (network-level failure)</li>
 * </ul>
 *
 * <p>Backoff between attempts: {@code baseDelayMs * 2^attempt + jitter(0..jitterMs)}.
 *
 * <p>Use {@link #DEFAULT} for the recommended policy (3 attempts, 500ms base, 200ms jitter).
 * Call {@link #builder()} to customize.
 */
public final class RetryPolicy {

	/** Supplier-like interface that can throw checked exceptions. */
	@FunctionalInterface
	public interface HttpCallable<T> {
		T call() throws IOException, InterruptedException;
	}

	private static final Logger LOG = Logger.getLogger(RetryPolicy.class.getName());

	/** Default policy: 3 attempts, exponential backoff starting at 500ms, 200ms jitter. */
	public static final RetryPolicy DEFAULT = builder().build();

	private final int maxAttempts;
	private final long baseDelayMs;
	private final long jitterMs;
	private final Set<Integer> retryStatuses;
	private final Random rng = new Random();

	private RetryPolicy(Builder b) {
		this.maxAttempts = b.maxAttempts;
		this.baseDelayMs = b.baseDelayMs;
		this.jitterMs = b.jitterMs;
		this.retryStatuses = Set.copyOf(b.retryStatuses);
	}

	/**
	 * Execute the given call, retrying on transient failures per this policy.
	 *
	 * @param callable the HTTP call to execute
	 * @param <T>      the return type (typically {@link HttpResponse})
	 * @return the first successful response
	 * @throws IOException          if all attempts fail with a network error
	 * @throws InterruptedException if the thread is interrupted during backoff sleep
	 * @throws RuntimeException     wrapping the last IOException if exhausted
	 */
	public <T extends HttpResponse<?>> T execute(HttpCallable<T> callable)
			throws IOException, InterruptedException {
		IOException lastIoe = null;
		T lastResponse = null;

		for (int attempt = 0; attempt < maxAttempts; attempt++) {
			if (attempt > 0) {
				long delay = baseDelayMs * (1L << (attempt - 1))
						+ (jitterMs > 0 ? (long)(rng.nextDouble() * jitterMs) : 0);
				final int a = attempt;
				final long d = delay;
				LOG.fine(() -> "RetryPolicy: attempt " + (a + 1)
						+ "/" + maxAttempts + " after " + d + "ms");
				Thread.sleep(delay);
			}
			try {
				T response = callable.call();
				if (!retryStatuses.contains(response.statusCode())) {
					return response;
				}
				lastResponse = response;
				final int a2 = attempt;
				final int statusCode = response.statusCode();
				LOG.warning(() -> "RetryPolicy: HTTP " + statusCode
						+ ", will retry (attempt " + (a2 + 1) + "/" + maxAttempts + ")");
			} catch (IOException ioe) {
				lastIoe = ioe;
				final int a = attempt;
				LOG.warning(() -> "RetryPolicy: IOException on attempt " + (a + 1)
						+ "/" + maxAttempts + ": " + ioe.getMessage());
			}
		}

		if (lastIoe != null) {
			throw lastIoe;
		}
		// All attempts returned a retry-eligible status; return last response.
		return lastResponse;
	}

	/** Returns a new builder pre-loaded with default values. */
	public static Builder builder() {
		return new Builder();
	}

	/** Builder for {@link RetryPolicy}. */
	public static final class Builder {
		private int maxAttempts = 3;
		private long baseDelayMs = 500;
		private long jitterMs = 200;
		private Set<Integer> retryStatuses = defaultRetryStatuses();

		private Builder() {}

		/** Number of total attempts (including the first). Default: 3. */
		public Builder maxAttempts(int n) { this.maxAttempts = n; return this; }

		/** Base delay in milliseconds for exponential backoff. Default: 500ms. */
		public Builder baseDelayMs(long ms) { this.baseDelayMs = ms; return this; }

		/** Maximum random jitter added to each backoff delay. Default: 200ms. */
		public Builder jitterMs(long ms) { this.jitterMs = ms; return this; }

		/** HTTP status codes that trigger a retry. Default: 429 + 500-599. */
		public Builder retryStatuses(Set<Integer> statuses) {
			this.retryStatuses = Set.copyOf(statuses);
			return this;
		}

		public RetryPolicy build() { return new RetryPolicy(this); }

		private static Set<Integer> defaultRetryStatuses() {
			java.util.HashSet<Integer> s = new java.util.HashSet<>();
			s.add(429); // Too Many Requests
			for (int i = 500; i <= 599; i++) s.add(i);
			return s;
		}
	}
}
