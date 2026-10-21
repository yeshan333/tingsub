// Package tingsub contains the desktop assets embedded in the MyGo executable.
package tingsub

import (
	"embed"
	"io/fs"
)

//go:embed src/live_subs/desktop_ui/*.html src/live_subs/desktop_ui/*.js src/live_subs/desktop_ui/*.css src/live_subs/desktop_ui/*.svg
var frontend embed.FS

//go:embed src/live_subs/desktop_ui/menubar.png
var TrayIcon []byte

func Frontend() fs.FS {
	files, err := fs.Sub(frontend, "src/live_subs/desktop_ui")
	if err != nil {
		panic(err)
	}
	return files
}
