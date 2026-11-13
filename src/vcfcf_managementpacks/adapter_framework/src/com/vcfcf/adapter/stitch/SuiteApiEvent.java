package com.vcfcf.adapter.stitch;

/**
 * One event for {@link SuiteApiStitcher#pushEvents}, which sends it to
 * {@code POST /api/events/bulk} as one entry of {@code {"event":[...]}}.
 * Immutable; build it with {@link #builder}.
 *
 * <p>Wire fields (the {@code event} schema of the operations-api specs for
 * 8.18, 9.0 and 9.1; required there: {@code eventType}, {@code message},
 * {@code resourceId}):
 * <ul>
 *   <li>{@code eventType}: {@link Type}.</li>
 *   <li>{@code resourceId}: the Suite API UUID of the target resource. It may
 *       belong to another adapter (a {@code VMWARE} VirtualMachine): a
 *       {@code DIAGNOSTIC} event onto a foreign VM was proven to land on its
 *       timeline about 45 s later (9.x devel, 2026-06-22).</li>
 *   <li>{@code startTimeUTC}: epoch milliseconds, at least
 *       {@link #MIN_TIME_UTC} (2000-01-01, the spec's floor and its default;
 *       sent always, so an event never silently starts in 2000).</li>
 *   <li>{@code cancelTimeUTC}: optional. For a {@code managedExternally}
 *       event the spec says the event is cancelled by sending a new event
 *       with the <em>same message</em> and a cancel time
 *       ({@link #cancelledAt}).</li>
 *   <li>{@code message}: identifies the event in the system (cancel matches
 *       on it).</li>
 *   <li>{@code severity}: optional {@link Severity} (JSON name
 *       {@code severity}, XML name {@code criticality}).</li>
 *   <li>{@code diagnosticSubType}: optional {@link DiagnosticSubType}, for a
 *       {@code DIAGNOSTIC} event only.</li>
 *   <li>{@code managedExternally}: optional. {@code true}: the event persists
 *       across collection cycles until another event changes it (cancel it
 *       explicitly). {@code false}: the spec says it is cancelled during the
 *       next collection cycle if it is not pushed again. Whether that
 *       happens after one cycle, several, or at all for a {@code GENERAL}
 *       adapter's REST event is not established (design experiment G5).</li>
 * </ul>
 *
 * <p><strong>No auto-cancel or watch/cancel cycle counts.</strong> The Python
 * Integration SDK's {@code auto_cancel}, {@code watch_wait_cycle} and
 * {@code cancel_wait_cycle} belong to its collect result; the REST event has
 * no such fields. The REST analogue is {@code managedExternally(false)} and
 * not re-pushing, or {@code managedExternally(true)} with an explicit
 * {@link #cancelledAt} after the pak's own count of quiet cycles.
 *
 * <p><strong>NOTIFICATION is refused by {@code pushEvents}.</strong> Pushed
 * onto another adapter's resource through {@code /api/events/bulk}, a
 * {@code NOTIFICATION} event is answered 200 and silently discarded, with
 * {@code managedExternally} true or false; the same request as
 * {@code DIAGNOSTIC} lands
 * ({@code knowledge/context/investigations/vcommunity-notification-events-foreign-vm.md},
 * 9.x devel, 2026-06-22). A 200 that produces nothing is the failure this
 * framework refuses, so {@code pushEvents} does not send it and counts it
 * dropped. Use {@code DIAGNOSTIC} (for log-derived events,
 * {@code DIAGNOSTIC}/{@code LOG}). The type stays in {@link Type} so that a
 * pak reaching for it gets the explanation, not a missing constant.
 *
 * <p>{@code HARD_THRESHOLD} is not offered: it needs {@code key},
 * {@code htType} and {@code value}, which this type does not carry.
 */
public final class SuiteApiEvent {

    /** Earliest start or cancel time the spec accepts: 2000-01-01T00:00:00Z. */
    public static final long MIN_TIME_UTC = 946684800000L;

    /** {@code eventType} values (the spec enum, without {@code HARD_THRESHOLD}). */
    public enum Type {
        CHANGE,
        /** Refused by {@code pushEvents}: silently discarded on a foreign resource. */
        NOTIFICATION,
        RESOURCE_DOWN,
        SYSTEM_DEGRADATION,
        AVAILABILITY_DOWN,
        AVAILABILITY_EXCEPTION,
        AVAILABILITY_NOT_COLLECTING,
        /** Proven to land on a foreign VMWARE VirtualMachine (9.x devel). */
        DIAGNOSTIC
    }

    /** {@code severity} values (the spec enum, identical on 8.18, 9.0 and 9.1). */
    public enum Severity {
        UNKNOWN, NONE, INFORMATION, WARNING, IMMEDIATE, CRITICAL, AUTO
    }

    /**
     * {@code diagnosticSubType} values listed by all three supported lines'
     * specs. 9.0 adds {@code TROUBLESHOOT}, 9.1 adds more; they are left out
     * so a pak cannot send a value its oldest supported line rejects.
     */
    public enum DiagnosticSubType {
        HEALTH, LOG, HISTORY, SNAPSHOT, WORKLOAD, UNKNOWN
    }

    private final Type type;
    private final String resourceId;
    private final String message;
    private final long startTimeUtc;
    private final Long cancelTimeUtc;
    private final Severity severity;
    private final DiagnosticSubType diagnosticSubType;
    private final Boolean managedExternally;

    private SuiteApiEvent(Builder b) {
        this.type = b.type;
        this.resourceId = b.resourceId;
        this.message = b.message;
        this.startTimeUtc = b.startTimeUtc;
        this.cancelTimeUtc = b.cancelTimeUtc;
        this.severity = b.severity;
        this.diagnosticSubType = b.diagnosticSubType;
        this.managedExternally = b.managedExternally;
    }

    /**
     * Start an event. Only a {@code null} type is refused here (a programming
     * error); the data-dependent checks (UUID, non-blank message, times at
     * or after {@link #MIN_TIME_UTC}) run in {@code pushEvents}, which drops
     * and counts a bad event rather than throwing into the collect cycle.
     *
     * @param type         event type; not {@code null}
     * @param resourceId   target resource UUID
     * @param message      event message (identifies the event; cancel matches on it)
     * @param startTimeUtc start time, epoch milliseconds
     * @throws IllegalArgumentException if {@code type} is {@code null}
     */
    public static Builder builder(Type type, String resourceId, String message,
            long startTimeUtc) {
        if (type == null) {
            throw new IllegalArgumentException("SuiteApiEvent: type must not be null");
        }
        return new Builder(type, resourceId, message, startTimeUtc);
    }

    /** Builder for {@link SuiteApiEvent}. */
    public static final class Builder {
        private final Type type;
        private final String resourceId;
        private final String message;
        private final long startTimeUtc;
        private Long cancelTimeUtc;
        private Severity severity;
        private DiagnosticSubType diagnosticSubType;
        private Boolean managedExternally;

        private Builder(Type type, String resourceId, String message, long startTimeUtc) {
            this.type = type;
            this.resourceId = resourceId;
            this.message = message;
            this.startTimeUtc = startTimeUtc;
        }

        /** {@code severity}; {@code null} (the default) omits the field. */
        public Builder severity(Severity s) {
            this.severity = s;
            return this;
        }

        /**
         * {@code diagnosticSubType}; {@code null} (the default) omits it.
         *
         * @throws IllegalArgumentException if non-null on a type other than
         *                                  {@code DIAGNOSTIC}
         */
        public Builder diagnosticSubType(DiagnosticSubType s) {
            if (s != null && type != Type.DIAGNOSTIC) {
                throw new IllegalArgumentException("SuiteApiEvent: diagnosticSubType is for a"
                        + " DIAGNOSTIC event, not " + type);
            }
            this.diagnosticSubType = s;
            return this;
        }

        /** {@code managedExternally}; {@code null} (the default) omits it. */
        public Builder managedExternally(Boolean m) {
            this.managedExternally = m;
            return this;
        }

        /** {@code cancelTimeUTC}, epoch milliseconds; {@code null} omits it. */
        public Builder cancelTimeUtc(Long t) {
            this.cancelTimeUtc = t;
            return this;
        }

        public SuiteApiEvent build() {
            return new SuiteApiEvent(this);
        }
    }

    /**
     * The same event (same message, resource, type and fields) with a
     * {@code cancelTimeUTC}: how the spec says an externally managed event is
     * cancelled.
     *
     * @param cancelTimeUtc cancel time, epoch milliseconds
     */
    public SuiteApiEvent cancelledAt(long cancelTimeUtc) {
        Builder b = new Builder(type, resourceId, message, startTimeUtc);
        b.severity = severity;
        b.diagnosticSubType = diagnosticSubType;
        b.managedExternally = managedExternally;
        b.cancelTimeUtc = cancelTimeUtc;
        return new SuiteApiEvent(b);
    }

    public Type getType() { return type; }
    public String getResourceId() { return resourceId; }
    public String getMessage() { return message; }
    public long getStartTimeUtc() { return startTimeUtc; }
    /** {@code null} when not set. */
    public Long getCancelTimeUtc() { return cancelTimeUtc; }
    /** {@code null} when not set. */
    public Severity getSeverity() { return severity; }
    /** {@code null} when not set. */
    public DiagnosticSubType getDiagnosticSubType() { return diagnosticSubType; }
    /** {@code null} when not set. */
    public Boolean getManagedExternally() { return managedExternally; }

    /** Never the message: event text can carry guest data. */
    @Override
    public String toString() {
        return "SuiteApiEvent[" + type + " resource=" + resourceId + "]";
    }
}
