package tingsub

import (
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/egoist/mygo"
	"github.com/yeshan333/tingsub/internal/desktop"
)

func TestBundledDesktopEntryLoadsWithoutRedirectingAwayFromTrustedDocument(t *testing.T) {
	response := httptest.NewRecorder()
	mygo.FileServer(Frontend()).ServeHTTP(response, httptest.NewRequest("GET", desktop.EntryURL, nil))
	if response.Code != 200 || !strings.Contains(response.Body.String(), `src="bridge.js"`) {
		t.Fatalf("desktop entry did not serve its UI: status=%d body=%s", response.Code, response.Body.String())
	}
	for _, path := range []string{"bridge.js", "app.js", "style.css", "brand.svg"} {
		asset := httptest.NewRecorder()
		mygo.FileServer(Frontend()).ServeHTTP(asset, httptest.NewRequest("GET", desktop.EntryURL+path, nil))
		if asset.Code != 200 {
			t.Errorf("missing bundled resource %s: %d", path, asset.Code)
		}
	}
}
