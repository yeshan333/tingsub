package desktop

import "testing"

func TestDesktopAllowsOnlyBundledDocumentAndItsFragments(t *testing.T) {
	for _, raw := range []string{EntryURL, EntryURL + "#models"} {
		if !TrustedDocument(raw) {
			t.Errorf("blocked bundled page %q", raw)
		}
	}
	for _, raw := range []string{
		"https://example.com", "file:///tmp/page.html", "about:blank", "data:text/html,foreign",
		"mygo://localhost/foreign.html", "mygo://foreign/index.html", EntryURL + "?foreign",
		"mygo://localhost:123/index.html", "mygo://user@localhost/index.html",
	} {
		if TrustedDocument(raw) {
			t.Errorf("allowed foreign document %q", raw)
		}
	}
}
