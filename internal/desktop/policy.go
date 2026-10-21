package desktop

import "net/url"

const EntryURL = "mygo://localhost/"

func TrustedDocument(raw string) bool {
	u, err := url.Parse(raw)
	if err != nil {
		return false
	}
	u.Fragment, u.RawFragment = "", ""
	return u.String() == EntryURL
}
