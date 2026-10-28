package com.vcfcf.adapter.stitch;

/**
 * What one batch push did (buildkit 1.0.24), returned by
 * {@link SuiteApiStitchClient#pushPropertiesBatch},
 * {@link SuiteApiStitchClient#pushStatsBatch} and
 * {@link SuiteApiStitchClient#pushBatch} (and the {@link SuiteApiStitcher}
 * methods of the same names), so an adapter can count the outcome rather than
 * only read it from the log. Immutable.
 *
 * <p><strong>{@link #getBatchesOk()} counts accepted requests, not landed
 * data.</strong> The bulk endpoints answer 200 with no body, and an id that
 * matches no resource is dropped silently while the rest of the batch lands
 * (live on 8.18.7, {@code knowledge/context/api-surface/suite_api_batch_push.md}
 * live test 3). Nothing here can tell a stale id from a good one: that is the
 * job of the adapter's {@link ForeignResourceResolver} refresh.
 */
public final class SuiteApiBatchResult {

    /** Nothing sent, nothing skipped. */
    static final SuiteApiBatchResult EMPTY = new SuiteApiBatchResult(0, 0, 0, 0, 0);

    private final int sent;
    private final int batchesOk;
    private final int batchesFailed;
    private final int fellBack;
    private final int skipped;

    SuiteApiBatchResult(int sent, int batchesOk, int batchesFailed, int fellBack,
            int skipped) {
        this.sent = sent;
        this.batchesOk = batchesOk;
        this.batchesFailed = batchesFailed;
        this.fellBack = fellBack;
        this.skipped = skipped;
    }

    /**
     * Resource entries put in a batch request that was sent, whatever its
     * answer. A resource in both the properties and the stats call of
     * {@link SuiteApiStitchClient#pushBatch} counts twice.
     */
    public int getSent() {
        return sent;
    }

    /** Batch requests the Suite API accepted (2xx). */
    public int getBatchesOk() {
        return batchesOk;
    }

    /** Batch requests that failed (non-2xx after the one 401 retry, or no answer). */
    public int getBatchesFailed() {
        return batchesFailed;
    }

    /**
     * Resource entries re-sent one by one on the per-id path after their batch
     * failed with an HTTP status. Each re-send logs its own failure, if any.
     */
    public int getFellBack() {
        return fellBack;
    }

    /**
     * Resource entries never sent: an id that is not a UUID, a resource whose
     * every entry was dropped (null key, null or non-finite stat value, null
     * property value), or resources left when an interrupt or a closed client
     * stopped the call. A resource with an empty map is not counted: it had
     * nothing to send.
     */
    public int getSkipped() {
        return skipped;
    }

    /** True when every batch sent was accepted and nothing was skipped. */
    public boolean isClean() {
        return batchesFailed == 0 && skipped == 0;
    }

    /** Field-wise sum, for {@link SuiteApiStitchClient#pushBatch}. */
    SuiteApiBatchResult plus(SuiteApiBatchResult o) {
        return new SuiteApiBatchResult(sent + o.sent, batchesOk + o.batchesOk,
                batchesFailed + o.batchesFailed, fellBack + o.fellBack,
                skipped + o.skipped);
    }

    @Override
    public String toString() {
        return "sent=" + sent + " batchesOk=" + batchesOk + " batchesFailed="
                + batchesFailed + " fellBack=" + fellBack + " skipped=" + skipped;
    }
}
