package com.vcfcf.adapter.stitch;

import java.io.IOException;

/**
 * A Suite API call answered with a non-2xx HTTP status (issue #201).
 *
 * <p>Thrown by {@link SuiteApiStitchClient#get(String)} and
 * {@link SuiteApiStitchClient#get(String, String)} (and so by the
 * {@link SuiteApiStitcher} facade) when the server answers but refuses. It is
 * an {@link IOException}, so existing {@code catch (IOException e)} call sites
 * keep working; catch this type first when the status or the Suite API
 * {@code apiErrorCode} decides what to do. Example: the configuration-file
 * store answers HTTP 400 with {@code apiErrorCode} 1501 for "no such file",
 * which a caller can now tell apart from any other bad request.
 *
 * <p>The message keeps the transport's shape, {@code "Suite API <method>
 * <url> HTTP <status>"}, with {@code " apiErrorCode <n>"} appended when the
 * body carries one. The body itself is not in the message (it is server
 * text); read it with {@link #getBodyExcerpt()}.
 */
public class SuiteApiHttpException extends IOException {

    private static final long serialVersionUID = 1L;

    private final int statusCode;
    private final Integer apiErrorCode;
    private final String bodyExcerpt;

    /**
     * @param message      the exception message
     * @param statusCode   the HTTP status the server answered
     * @param apiErrorCode the {@code apiErrorCode} from the JSON error body,
     *                     or {@code null} when the body has none
     * @param bodyExcerpt  the start of the error body, sanitized for logging
     *                     and capped; empty when the server sent none
     */
    public SuiteApiHttpException(String message, int statusCode, Integer apiErrorCode,
            String bodyExcerpt) {
        super(message);
        this.statusCode = statusCode;
        this.apiErrorCode = apiErrorCode;
        this.bodyExcerpt = bodyExcerpt == null ? "" : bodyExcerpt;
    }

    /** The HTTP status code the Suite API answered (for example 400). */
    public int getStatusCode() {
        return statusCode;
    }

    /**
     * The Suite API {@code apiErrorCode} from the JSON error body (for
     * example 1501), or {@code null} when the body was absent, not JSON, or
     * carried no numeric {@code apiErrorCode}.
     */
    public Integer getApiErrorCode() {
        return apiErrorCode;
    }

    /**
     * The start of the error body (at most
     * {@link SuiteApiStitchClient#ERROR_BODY_EXCERPT_MAX} characters, control
     * and format characters replaced with {@code ?}), or {@code ""} when the
     * server sent no body. Server text: log it with care.
     */
    public String getBodyExcerpt() {
        return bodyExcerpt;
    }
}
