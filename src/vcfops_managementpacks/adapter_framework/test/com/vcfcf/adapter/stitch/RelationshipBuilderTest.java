package com.vcfcf.adapter.stitch;

import com.integrien.alive.common.adapter3.Relationships;
import com.integrien.alive.common.adapter3.ResourceKey;

import java.util.ArrayList;
import java.util.List;

/**
 * Lightweight unit tests for {@link RelationshipBuilder}.
 *
 * <p>No JUnit required — call via {@code main()}. Covers the additive
 * foreign-parent write-verb split (2026-07-01 —
 * {@code knowledge/context/reviews/synology-stitcher-vs-tvs-corpus.md} R1): edges whose
 * parent belongs to a foreign adapter must be emitted via
 * {@link Relationships#addRelationships} (never full-set
 * {@link Relationships#setRelationships}), while own-adapter parents keep
 * the consolidated one-{@code setRelationships}-per-parent-per-cycle
 * behavior.
 *
 * <p>Verified via {@code Relationships.RelationshipItem.isClearFirst()}
 * (bytecode-confirmed 2026-07-01: {@code setRelationships} constructs the
 * item with {@code isClearFirst=true}; {@code addRelationships} with
 * {@code isClearFirst=false}) — this is the platform-level signal that
 * distinguishes a clobbering full-set replacement from a non-destructive
 * add.
 *
 * <p>Run:
 * <pre>
 *   javac -cp adapter_runtime/vrops-adapters-sdk-2.2.jar:build/vcfcf-adapter-base.jar \
 *         adapter_framework/test/com/vcfcf/adapter/stitch/RelationshipBuilderTest.java \
 *         -d build/test-classes
 *   java -cp build/test-classes:adapter_runtime/vrops-adapters-sdk-2.2.jar:build/vcfcf-adapter-base.jar \
 *         com.vcfcf.adapter.stitch.RelationshipBuilderTest
 * </pre>
 */
public class RelationshipBuilderTest {

    private static final List<String> FAILURES = new ArrayList<>();
    private static int passed = 0;

    public static void main(String[] args) {
        testForeignParentUsesAdditiveVerb();
        testLocalParentUsesFullSetVerb();
        testMixedLocalAndForeignParentsInOneBuild();
        testChildForeignKeepsLocalParentConsolidated();
        report();
    }

    // -----------------------------------------------------------------------
    // Foreign parent → additive
    // -----------------------------------------------------------------------

    private static void testForeignParentUsesAdditiveVerb() {
        RelationshipBuilder rb = new RelationshipBuilder("SYNOLOGY");
        ResourceKey datastore = rb.resource("Datastore", "ds1", "dsPath", "naa.111");
        ResourceKey lun = rb.resource("SynologyLun", "lun1", "lun_id", "lun-1");

        rb.parentForeign(datastore, lun);
        Relationships rels = rb.build();

        Relationships.RelationshipItem item = onlyItem(rels);
        assertTrue("foreign parent edge is an add (isAdd=true)", item.isAdd());
        assertTrue("foreign parent edge is NOT clear-first (additive, not full-set)",
                !item.isClearFirst());
    }

    // -----------------------------------------------------------------------
    // Own-adapter parent → full-set (unchanged consolidated behavior)
    // -----------------------------------------------------------------------

    private static void testLocalParentUsesFullSetVerb() {
        RelationshipBuilder rb = new RelationshipBuilder("SYNOLOGY");
        ResourceKey diskstation = rb.resource("SynologyDiskstation", "ds1", "serial", "S1");
        ResourceKey pool = rb.resource("SynologyStoragePool", "pool1", "pool_id", "P1");

        rb.parent(diskstation, pool);
        Relationships rels = rb.build();

        Relationships.RelationshipItem item = onlyItem(rels);
        assertTrue("local parent edge is an add (isAdd=true; SDK sets this for both verbs)",
                item.isAdd());
        assertTrue("local parent edge IS clear-first (consolidated full-set replacement)",
                item.isClearFirst());
    }

    // -----------------------------------------------------------------------
    // Mixed cycle: local parents stay full-set, foreign parents stay additive
    // -----------------------------------------------------------------------

    private static void testMixedLocalAndForeignParentsInOneBuild() {
        RelationshipBuilder rb = new RelationshipBuilder("SYNOLOGY");
        ResourceKey diskstation = rb.resource("SynologyDiskstation", "ds1", "serial", "S1");
        ResourceKey pool = rb.resource("SynologyStoragePool", "pool1", "pool_id", "P1");
        ResourceKey volume = rb.resource("SynologyVolume", "vol1", "volume_id", "V1");
        ResourceKey datastore = rb.resource("Datastore", "ds1", "dsPath", "naa.111");

        rb.parent(diskstation, pool)
          .parent(pool, volume)
          .parentForeign(datastore, volume);

        Relationships rels = rb.build();
        java.util.Collection<Relationships.RelationshipItem> items = rels.getRelationshipItems();
        assertTrue("mixed build emits 3 relationship items (2 local parents + 1 foreign parent)",
                items.size() == 3);

        int fullSetCount = 0;
        int additiveCount = 0;
        for (Relationships.RelationshipItem item : items) {
            if (item.isClearFirst()) {
                fullSetCount++;
            } else {
                additiveCount++;
            }
        }
        assertTrue("2 local parents emitted full-set (clear-first)", fullSetCount == 2);
        assertTrue("1 foreign parent emitted additive (not clear-first)", additiveCount == 1);
    }

    // -----------------------------------------------------------------------
    // childForeign: parent is still internal — stays local/full-set
    // -----------------------------------------------------------------------

    private static void testChildForeignKeepsLocalParentConsolidated() {
        RelationshipBuilder rb = new RelationshipBuilder("SYNOLOGY");
        ResourceKey diskstation = rb.resource("SynologyDiskstation", "ds1", "serial", "S1");
        ResourceKey foreignHost = rb.resource("HostSystem", "host1", "moid", "host-1");

        rb.childForeign(diskstation, foreignHost);
        Relationships rels = rb.build();

        Relationships.RelationshipItem item = onlyItem(rels);
        assertTrue("childForeign's PARENT is internal, so it stays clear-first/full-set"
                        + " (only parentForeign's parent triggers additive)",
                item.isClearFirst());
    }

    // -----------------------------------------------------------------------
    // Harness
    // -----------------------------------------------------------------------

    private static Relationships.RelationshipItem onlyItem(Relationships rels) {
        java.util.Collection<Relationships.RelationshipItem> items = rels.getRelationshipItems();
        if (items.size() != 1) {
            throw new AssertionError("expected exactly 1 relationship item, got " + items.size());
        }
        return items.iterator().next();
    }

    private static void assertTrue(String label, boolean cond) {
        if (cond) {
            System.out.println("  PASS: " + label);
            passed++;
        } else {
            System.out.println("  FAIL: " + label);
            FAILURES.add(label);
        }
    }

    private static void report() {
        int total = passed + FAILURES.size();
        System.out.println();
        if (FAILURES.isEmpty()) {
            System.out.println("OK: " + passed + "/" + total + " tests passed.");
        } else {
            System.out.println("FAIL: " + FAILURES.size() + "/" + total
                    + " tests failed: " + FAILURES);
            System.exit(1);
        }
    }
}
