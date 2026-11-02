// Briefer's PocketBase build.
//
// This mirrors PocketBase's official examples/base binary (JS hooks, JS
// migrations, static public dir) but omits the self-update command: releases
// are built from this pinned module in CI and deployed by deploy/*.sh, so the
// binary must never replace itself.
package main

import (
	"log"
	"net/http"
	"os"

	"github.com/pocketbase/pocketbase"
	"github.com/pocketbase/pocketbase/apis"
	"github.com/pocketbase/pocketbase/core"
	"github.com/pocketbase/pocketbase/plugins/jsvm"
	"github.com/pocketbase/pocketbase/plugins/migratecmd"
	"github.com/pocketbase/pocketbase/tools/hook"
)

func main() {
	app := pocketbase.New()

	var hooksDir, migrationsDir, publicDir string
	var hooksWatch, automigrate, indexFallback bool
	var hooksPool int

	flags := app.RootCmd.PersistentFlags()
	flags.StringVar(&hooksDir, "hooksDir", "./pb_hooks", "the directory with the JS app hooks")
	flags.BoolVar(&hooksWatch, "hooksWatch", false, "auto restart the app on pb_hooks file change")
	flags.IntVar(&hooksPool, "hooksPool", 4, "the total prewarm goja.Runtime instances for the JS app hooks execution")
	flags.StringVar(&migrationsDir, "migrationsDir", "./pb_migrations", "the directory with the user defined migrations")
	flags.BoolVar(&automigrate, "automigrate", false, "enable/disable auto migrations (dev only)")
	flags.StringVar(&publicDir, "publicDir", "./pb_public", "the directory to serve static files")
	flags.BoolVar(&indexFallback, "indexFallback", true, "fallback to index.html on missing static path (SPA routing)")

	app.RootCmd.ParseFlags(os.Args[1:])

	jsvm.MustRegister(app, jsvm.Config{
		MigrationsDir: migrationsDir,
		HooksDir:      hooksDir,
		HooksWatch:    hooksWatch,
		HooksPoolSize: hooksPool,
	})

	migratecmd.MustRegister(app, app.RootCmd, migratecmd.Config{
		TemplateLang: migratecmd.TemplateLangJS,
		Automigrate:  automigrate,
		Dir:          migrationsDir,
	})

	app.OnServe().Bind(&hook.Handler[*core.ServeEvent]{
		Func: func(e *core.ServeEvent) error {
			if !e.Router.HasRoute(http.MethodGet, "/{path...}") {
				e.Router.GET("/{path...}", apis.Static(os.DirFS(publicDir), indexFallback))
			}
			return e.Next()
		},
		Priority: 999,
	})

	if err := app.Start(); err != nil {
		log.Fatal(err)
	}
}
