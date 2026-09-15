# Bounded SSE draining on the isolated validated application

Three isolated servers ran the exact 114-file06aa application with recover=False and two real HTTP SSE clients each. This harness added only a private signal-trigger endpoint and an observational wrapper around the original EngineService.shutdown; no application source or live server was changed.

The unbounded default still waited after two seconds, then closed when the clients were released. timeout_graceful_shutdown=1 completed in1.257s; the proposed value10 completed in10.222s, with the clients deliberately left open. Both timeout cases cancelled overdue stream tasks, then awaited the ordinary application lifespan. All cases completed EngineService.shutdown, had zero active workers, exited0, released their isolated port, preserved every SQL row and blob, and passed SQLite quick_check.

The signal was a single actual Python SIGINT raised from the server main loop, using Uvicorn's ordinary first-signal handler. This does not test Windows console signal delivery. It does not claim bounded completion of arbitrary lifespan code or safe termination of busy workers: the configured timeout bounds HTTP task draining, and lifespan shutdown is awaited separately. Uvicorn0.52.4 server/config sources and upstream documentation links are retained.

All Store content here is synthetic test data. The live Store and all Hospital files were untouched.
