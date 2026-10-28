package com.vcfcf.adapter.stitch;

/**
 * What one batch push did (buildkit 1.0.24), returned by
 * {@link SuiteApiStitchClient#pushPropertiesBatch},
 * {@link SuiteApiStitchClient#pushStatsBatch} and
 * {@link SuiteApiStitchClient#pushBatch} (and the {@link SuiteApiStitcher}
 * methods of the same names), so an adapter can count the outcome rather than
 * only read it from the log. Immutable.
 *
 * <p>Every resource the caller passed with something to send ends up in at
 * least one of {@link #getSent()} and {@link #getSkipped()}: a resource is
 * skipped whenever its data was delivered by no request.
 *
 * <p><strong>{@link #getBatchesOk()} counts accepted requests, not landed
 * data.</strong> The bulk endpoints answer 200 with no body, and an id that
 * matches no resource is dropped silently while the rest of the batch lands
 * (live on 8.18.7, {@code knowledge/context/api-surface/suite_api_batch_push.md}
 * live test 3). Nothing here can tell a stale id from a good one: that is the
 * job of the adapter's {@link ForeignResourceResolver} refresh.
 */
public final class SuiteApiBatchResult {

    private final int sent;
    private final int batchesOk;
    private final int batchesFailed;
    private final int fellBack;
    private final int skipped;
    private final int dropped;
    private final boolean stopped;

    SuiteApiBatchResult(int sent, int batchesOk, int batchesFailed, int fellBack,
            int skipped, int dropped, boolean stopped) {
        this.sent = sent;
        this.batchesOk = batchesOk;
        this.batchesFailed = batchesFailed;
        this.fellBack = fellBack;
        this.skipped = skipped;
        this.dropped = dropped;
        this.stopped = stopped;
    }

    /**
     * Resource entries in a batch request that actually went out (a token was
     * in hand and the request was written), whatever its answer. A resource
     * in both the properties and the stats call of
     * {@link SuiteApiStitchClient#pushBatch} counts twice.
     */
    public int getSent() {
        return sent;
    }

    /** Batch requests the Suite API accepted (2xx). */
    public int getBatchesOk() {
        return batchesOk;
    }

    /** Batch requests sent that failed (non-2xx after the one 401 retry, or no answer). */
    public int getBatchesFailed() {
        return batchesFailed;
    }

    /**
     * Resource entries actually re-sent one by one on the per-id path after
     * their batch was refused with a 4xx other than 401 and 429. Each re-send
     * logs its own failure, if any.
     */
    public int getFellBack() {
        return fellBack;
    }

    /**
     * Resource entries whose data no request delivered: an id that is not a
     * UUID, a resource whose every entry was dropped, a resource left unsent
     * or not re-sent when the call stopped (token failure, 5xx, 429, a
     * persistent 401, no HTTP status, an interrupt, a closed client), and a
     * resource in a batch that failed that way. A resource with an empty map
     * is not counted: it had nothing to send.
     */
    public int getSkipped() {
        return skipped;
    }

    /**
     * Entries (statKey and value pairs, not resources) dropped before
     * sending: a {@code null} key, a {@code null} value, or a NaN or infinite
     * stat.
     */
    public int getDropped() {
        return dropped;
    }

    /**
     * True when the call stopped early and sent nothing more (see
     * {@link #getSkipped()} for the causes). In
     * {@link SuiteApiStitchClient#pushBatch} a stopped properties call means
     * the stats call sent nothing.
     */
    public boolean isStopped() {
        return stopped;
    }

    /** True when every batch sent was accepted and nothing was skipped, dropped or stopped. */
    public boolean isClean() {
        return batchesFailed == 0 && skipped == 0 && dropped == 0 && !stopped;
    }

    /** Field-wise sum (stopped if either stopped), for {@link SuiteApiStitchClient#pushBatch}. */
    SuiteApiBatchResult plus(SuiteApiBatchResult o) {
        return new SuiteApiBatchResult(sent + o.sent, batchesOk + o.batchesOk,
                batchesFailed + o.batchesFailed, fellBack + o.fellBack,
                skipped + o.skipped, dropped + o.dropped, stopped || o.stopped);
    }

    @Override
    public String toString() {
        return "sent=" + sent + " batchesOk=" + batchesOk + " batchesFailed="
                + batchesFailed + " fellBack=" + fellBack + " skipped=" + skipped
                + " dropped=" + dropped + " stopped=" + stopped;
    }
}
