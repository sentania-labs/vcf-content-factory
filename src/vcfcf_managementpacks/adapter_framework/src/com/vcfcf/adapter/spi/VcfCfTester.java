package com.vcfcf.adapter.spi;

import com.integrien.alive.common.adapter3.TestParam;
import com.vcfcf.adapter.http.ManagedHttpClient;

/**
 * SPI: validates credentials and connectivity for a VCF-CF adapter.
 *
 * <p>Implement this interface and return an instance from
 * {@link com.vcfcf.adapter.VcfCfAdapter#getTester()}.
 *
 * <h3>Contract (spec/19 §5)</h3>
 * <ul>
 *   <li>Verify credentials <em>and</em> connectivity to the target system.</li>
 *   <li>On failure throw any {@link Exception} with a descriptive message.
 *       The orchestrator will call {@link TestParam#setErrorMsg(String)} with
 *       the exception message so the UI's "Test Connection" button shows a
 *       meaningful error. Never return normally on a known failure — that
 *       blank-fails the UI.</li>
 *   <li>Must be side-effect-free: no resource creation, no state mutation on
 *       the adapter instance.</li>
 * </ul>
 *
 * @param <C> the typed configuration POJO of the adapter
 */
public interface VcfCfTester<C> {

    /**
     * Test the connection described by {@code config}.
     *
     * <p>Throw any {@link Exception} to signal failure. The exception's
     * {@link Exception#getMessage()} is the failure message shown in the UI.
     *
     * @param config     the typed configuration (populated by
     *                   {@link com.vcfcf.adapter.VcfCfAdapter#configureAdapter})
     * @param httpClient the managed HTTP client (may be {@code null} for
     *                   non-HTTP adapters)
     * @param param      the {@code TestParam} for setting localized messages;
     *                   call {@link TestParam#setLocalizedMsg} for i18n when
     *                   localized strings are available
     * @throws Exception on any connectivity or authentication failure
     */
    void test(C config, ManagedHttpClient httpClient, TestParam param)
            throws Exception;
}
