# Device acceptance (pending)

The build has not been tested on physical Android. Complete these steps on your actual Termux device:

1. Install current Termux from a maintained distribution, then `pkg update && pkg install git python`.
2. Clone/extract into `$HOME`, `cd OsintCLI`, `bash install.sh`, `bash start.sh`.
3. `osintcli doctor`: verify report packages READY. Optional tools may remain UNAVAILABLE until explicitly installed.
4. `osintcli demo --report`: open the resulting PDF and check Arabic/long URLs using the included test suite if needed.
5. `osintcli scan example.com --modules dns --yes`: inspect sources and real states, not just exit messages.
6. Run a username you own using one selected engine; candidate profiles need manual review.
7. Scan a local image; verify expected dimensions/hash/EXIF and no upload.
8. Interrupt a selected scan, restart, inspect case status and use Resume. Existing evidence must remain.
9. Run `termux-setup-storage`, grant permission, export a report to `android` from menu 09 and open it in Downloads/OsintCLI.
10. Record Android/Termux/Python versions, installation log, screenshot at 40 columns and export result. Do not publish credentials or sensitive evidence.

If Pillow compilation fails, install clang, make, pkg-config, libjpeg-turbo, zlib, freetype and libpng, then repeat installer. `--core-only` remains available but does not include PDF/image extras. If an optional tool fails on ARM native dependencies, use the built-in engine and retain the install error for investigation.
