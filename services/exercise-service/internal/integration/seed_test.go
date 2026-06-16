//go:build integration

package integration

import "testing"

// TestSeedIdempotency: running the seed twice must leave node and
// relationship counts unchanged (exercises MERGE by name, taxonomy MERGEs).
func TestSeedIdempotency(t *testing.T) {
	svc, _ := newService(t)
	ctx := ctxT(t)
	driver := rawDriver(t)

	n1, err := svc.Seed(ctx)
	if err != nil {
		t.Fatalf("first seed: %v", err)
	}
	if n1 == 0 {
		t.Fatal("seed reported 0 exercises")
	}
	nodes1, rels1 := counts(t, driver)

	n2, err := svc.Seed(ctx)
	if err != nil {
		t.Fatalf("second seed: %v", err)
	}
	nodes2, rels2 := counts(t, driver)

	if n1 != n2 {
		t.Errorf("seed count changed: %d -> %d", n1, n2)
	}
	if nodes1 != nodes2 {
		t.Errorf("node count changed across seeds: %d -> %d", nodes1, nodes2)
	}
	if rels1 != rels2 {
		t.Errorf("relationship count changed across seeds: %d -> %d", rels1, rels2)
	}
}
