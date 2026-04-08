package postgres

import "testing"

func TestNullableGeoJSONText_ReturnsNil_WhenValueEmpty(t *testing.T) {
	if got := nullableGeoJSONText(nil); got != nil {
		t.Fatalf("expected nil, got %#v", got)
	}
}

func TestNullableGeoJSONText_ReturnsString_WhenValuePresent(t *testing.T) {
	got := nullableGeoJSONText([]byte(`{"type":"Point","coordinates":[1,2]}`))

	text, ok := got.(string)
	if !ok {
		t.Fatalf("expected string, got %T", got)
	}
	if text != `{"type":"Point","coordinates":[1,2]}` {
		t.Fatalf("unexpected value: %s", text)
	}
}
